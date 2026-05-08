from __future__ import annotations

import json
import shutil
import threading
import traceback
import uuid
import zipfile
from contextlib import redirect_stdout
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from main import run_pipeline
from utils.schema_mapper import apply_schema_mapping, parse_manual_mapping_json

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
RUNS_DIR = BASE_DIR / "outputs" / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

MAX_ROWS = 2000
MAX_HISTORY = 5

JOB_LOCK = threading.Lock()
JOBS: Dict[str, Dict] = {}
JOB_ORDER: List[str] = []

app = FastAPI(title="DataClean-Agent Web Demo", version="1.0.0")


class _RealtimeLogWriter:
    def __init__(self, write_line):
        self._write_line = write_line
        self._buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                self._write_line(line)
        return len(text)

    def flush(self) -> None:
        if self._buffer.strip():
            self._write_line(self._buffer.strip())
        self._buffer = ""


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_bool_text(text: Optional[str], default: bool = False) -> bool:
    if text is None:
        return default
    value = str(text).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _append_log(job_id: str, message: str) -> None:
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job["logs"].append({"time": _now_text(), "message": message})


def _job_artifacts(run_dir: Path) -> Dict[str, Path]:
    return {
        "dirty_csv": run_dir / "input_original.csv",
        "mapped_csv": run_dir / "input_mapped_for_pipeline.csv",
        "clean_csv": run_dir / "clean_orders.csv",
        "metrics_json": run_dir / "quality_metrics.json",
        "report_md": run_dir / "data_quality_report.md",
        "report_html": run_dir / "data_quality_report.html",
        "chart_png": run_dir / "quality_comparison.png",
        "schema_mapping": run_dir / "schema_mapping.json",
        "zip": run_dir / "dataclean_outputs.zip",
    }


def _to_table_payload(df: pd.DataFrame) -> Dict:
    safe_df = df.fillna("")
    columns = [str(c) for c in safe_df.columns.tolist()]
    rows = safe_df.astype(str).values.tolist()
    return {"columns": columns, "rows": rows}


def _normalize_input_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _validate_input_df(df: pd.DataFrame) -> None:
    if len(df) == 0:
        raise ValueError("CSV 为空，请提供至少一行数据。")
    if len(df) > MAX_ROWS:
        raise ValueError(f"当前数据行数为 {len(df)}，超过上限 {MAX_ROWS} 行。")


def _prune_history_locked() -> None:
    while len(JOB_ORDER) > MAX_HISTORY:
        removable_index = None
        for idx, job_id in enumerate(JOB_ORDER):
            status = JOBS.get(job_id, {}).get("status")
            if status != "running":
                removable_index = idx
                break
        if removable_index is None:
            return
        old_job_id = JOB_ORDER.pop(removable_index)
        old_job = JOBS.pop(old_job_id, None)
        if old_job:
            run_dir = Path(old_job["run_dir"])
            if run_dir.exists():
                shutil.rmtree(run_dir, ignore_errors=True)


def _finalize_zip(run_dir: Path) -> Path:
    artifacts = _job_artifacts(run_dir)
    zip_path = artifacts["zip"]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key, path in artifacts.items():
            if key == "zip":
                continue
            if path.exists():
                zf.write(path, arcname=path.name)
    return zip_path


def _build_job_result(job_id: str, run_dir: Path) -> Dict:
    artifacts = _job_artifacts(run_dir)
    metrics = json.loads(artifacts["metrics_json"].read_text(encoding="utf-8"))
    raw_df = pd.read_csv(artifacts["dirty_csv"], encoding="utf-8-sig")
    clean_df = pd.read_csv(artifacts["clean_csv"], encoding="utf-8-sig")

    downloads = {
        key: f"/api/jobs/{job_id}/download/{key}" for key in artifacts.keys()
    }
    schema_meta_path = run_dir / "schema_mapping.json"
    schema_mapping = {}
    if schema_meta_path.exists():
        schema_mapping = json.loads(schema_meta_path.read_text(encoding="utf-8"))

    return {
        "summary": metrics.get("中文摘要", {}),
        "before_score": metrics.get("before", {}).get("quality_score"),
        "after_score": metrics.get("after", {}).get("quality_score"),
        "downloads": downloads,
        "raw_table": _to_table_payload(raw_df),
        "clean_table": _to_table_payload(clean_df),
        "schema_mapping": schema_mapping,
    }


def _run_job(job_id: str) -> None:
    with JOB_LOCK:
        job = JOBS[job_id]
        job["status"] = "running"
        job["started_at"] = _now_text()

    run_dir = Path(job["run_dir"])
    input_csv_path = Path(job["input_csv_path"])
    llm_runtime = job.get("llm_runtime", {})
    schema_info = job.get("schema_info", {})
    quality_scope_fields = list((schema_info or {}).get("final_mapping", {}).keys())
    semantic_hints = (schema_info or {}).get("semantic_hints", {})
    if not semantic_hints:
        final_mapping = (schema_info or {}).get("final_mapping", {})
        city_src = str(final_mapping.get("city", "")).strip().lower().replace("_", " ")
        status_src = str(final_mapping.get("status", "")).strip().lower().replace("_", " ")
        semantic_hints = {
            "city_from_location": "location" in city_src,
            "status_from_payment_method": ("payment" in status_src and "status" not in status_src),
        }
    if semantic_hints.get("city_from_location"):
        quality_scope_fields = [f for f in quality_scope_fields if f != "city"]
    if semantic_hints.get("status_from_payment_method"):
        quality_scope_fields = [f for f in quality_scope_fields if f != "status"]

    def _log(message: str) -> None:
        _append_log(job_id, message)

    _log("任务开始执行。")
    if schema_info:
        mapped_count = schema_info.get("mapped_count", 0)
        total_input_cols = schema_info.get("total_input_columns", 0)
        _log(f"字段映射完成：{mapped_count}/{total_input_cols} 列已映射到标准字段。")
        missing_fields = schema_info.get("missing_standard_fields", [])
        if missing_fields:
            _log(f"未映射标准字段：{missing_fields}（将按默认规则补齐）")

    try:
        writer = _RealtimeLogWriter(_log)
        with redirect_stdout(writer):
            run_pipeline(
                project_root=BASE_DIR,
                verbose=True,
                input_csv_path=input_csv_path,
                outputs_dir=run_dir,
                llm_runtime=llm_runtime,
                quality_scope_fields=quality_scope_fields,
            )
            writer.flush()

        _finalize_zip(run_dir)
        result = _build_job_result(job_id, run_dir)
        run_meta = {
            "job_id": job_id,
            "created_at": job["created_at"],
            "started_at": job["started_at"],
            "finished_at": _now_text(),
            "status": "done",
            "before_score": result.get("before_score"),
            "after_score": result.get("after_score"),
            "downloads": result.get("downloads", {}),
        }
        (run_dir / "run_meta.json").write_text(json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8")

        with JOB_LOCK:
            job = JOBS[job_id]
            job["status"] = "done"
            job["finished_at"] = run_meta["finished_at"]
            job["result"] = result
            job["error"] = None
        _log("任务执行完成。")
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        _log(f"任务失败：{error_message}")
        _log(traceback.format_exc())
        with JOB_LOCK:
            job = JOBS[job_id]
            job["status"] = "error"
            job["finished_at"] = _now_text()
            job["error"] = error_message
            job["result"] = None


def _read_csv_input(file: Optional[UploadFile], csv_text: Optional[str]) -> pd.DataFrame:
    if file is None and (csv_text is None or csv_text.strip() == ""):
        raise ValueError("请上传 CSV 文件或粘贴 CSV 文本。")

    if file is not None and csv_text and csv_text.strip():
        raise ValueError("上传文件和粘贴文本请二选一。")

    if file is not None:
        raw_bytes = file.file.read()
        if not raw_bytes:
            raise ValueError("上传文件为空。")
        df = pd.read_csv(BytesIO(raw_bytes))
        return _normalize_input_df(df)

    df = pd.read_csv(StringIO(csv_text))
    return _normalize_input_df(df)


def _save_input_csv(raw_df: pd.DataFrame, mapped_df: pd.DataFrame, run_dir: Path) -> Dict[str, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "input_original.csv"
    mapped_path = run_dir / "input_mapped_for_pipeline.csv"
    raw_df.to_csv(raw_path, index=False, encoding="utf-8-sig")
    mapped_df.to_csv(mapped_path, index=False, encoding="utf-8-sig")
    return {"raw_path": raw_path, "mapped_path": mapped_path}


@app.get("/")
def index() -> FileResponse:
    html_path = WEB_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="前端页面不存在。")
    return FileResponse(html_path)


@app.get("/api/history")
def get_history() -> JSONResponse:
    with JOB_LOCK:
        history = []
        for job_id in reversed(JOB_ORDER):
            job = JOBS[job_id]
            entry = {
                "job_id": job_id,
                "status": job["status"],
                "created_at": job["created_at"],
                "started_at": job.get("started_at"),
                "finished_at": job.get("finished_at"),
                "before_score": None,
                "after_score": None,
                "error": job.get("error"),
            }
            if job.get("result"):
                entry["before_score"] = job["result"].get("before_score")
                entry["after_score"] = job["result"].get("after_score")
            history.append(entry)
        return JSONResponse({"jobs": history[:MAX_HISTORY]})


@app.post("/api/jobs")
def create_job(
    file: Optional[UploadFile] = File(default=None),
    csv_text: Optional[str] = Form(default=None),
    enable_llm: Optional[str] = Form(default="0"),
    model: Optional[str] = Form(default="gpt-4.1-mini"),
    api_key: Optional[str] = Form(default=None),
    api_url: Optional[str] = Form(default="https://api.openai.com/v1/responses"),
    column_mapping_json: Optional[str] = Form(default=None),
    provider: Optional[str] = Form(default="auto"),
) -> JSONResponse:
    try:
        df = _read_csv_input(file=file, csv_text=csv_text)
        _validate_input_df(df)
        manual_mapping = parse_manual_mapping_json(column_mapping_json)
        mapped_df, schema_info = apply_schema_mapping(df, manual_mapping=manual_mapping)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / job_id
    saved_paths = _save_input_csv(df, mapped_df, run_dir)
    (run_dir / "schema_mapping.json").write_text(
        json.dumps(schema_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    llm_runtime = {
        "DATACLEAN_ENABLE_LLM": "1" if _parse_bool_text(enable_llm) else "0",
        "DATACLEAN_MODEL": (model or "gpt-4.1-mini").strip(),
        "DATACLEAN_PROVIDER": (provider or "auto").strip().lower(),
    }
    if api_key and api_key.strip():
        llm_runtime["DATACLEAN_API_KEY"] = api_key.strip()
    if api_url and api_url.strip():
        llm_runtime["DATACLEAN_API_URL"] = api_url.strip()

    with JOB_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "created_at": _now_text(),
            "started_at": None,
            "finished_at": None,
            "logs": [],
            "error": None,
            "result": None,
            "run_dir": str(run_dir),
            "input_csv_path": str(saved_paths["mapped_path"]),
            "llm_runtime": llm_runtime,
            "schema_info": schema_info,
        }
        JOB_ORDER.append(job_id)
        _prune_history_locked()

    thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    thread.start()
    return JSONResponse({"job_id": job_id})


@app.post("/api/mapping/preview")
def preview_mapping(
    file: Optional[UploadFile] = File(default=None),
    csv_text: Optional[str] = Form(default=None),
    column_mapping_json: Optional[str] = Form(default=None),
) -> JSONResponse:
    try:
        df = _read_csv_input(file=file, csv_text=csv_text)
        _validate_input_df(df)
        manual_mapping = parse_manual_mapping_json(column_mapping_json)
        mapped_df, schema_info = apply_schema_mapping(df, manual_mapping=manual_mapping)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sample_rows = mapped_df.head(5).fillna("").astype(str).values.tolist()
    return JSONResponse(
        {
            "schema_mapping": schema_info,
            "mapped_preview": {
                "columns": [str(c) for c in mapped_df.columns.tolist()],
                "rows": sample_rows,
            },
        }
    )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, cursor: int = Query(default=0, ge=0)) -> JSONResponse:
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在。")
        logs = job["logs"][cursor:]
        payload = {
            "job_id": job_id,
            "status": job["status"],
            "created_at": job["created_at"],
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "error": job.get("error"),
            "logs": logs,
            "next_cursor": len(job["logs"]),
            "result": job.get("result"),
        }
    return JSONResponse(payload)


@app.get("/api/jobs/{job_id}/download/{artifact}")
def download_artifact(job_id: str, artifact: str) -> FileResponse:
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在。")
        run_dir = Path(job["run_dir"])

    artifacts = _job_artifacts(run_dir)
    if artifact not in artifacts:
        raise HTTPException(status_code=404, detail=f"不支持的文件类型: {artifact}")
    file_path = artifacts[artifact]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="目标文件不存在。")
    return FileResponse(file_path, filename=file_path.name)


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=False)
