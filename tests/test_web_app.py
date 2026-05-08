from __future__ import annotations

import time
import json

from fastapi.testclient import TestClient

from web_app import app

client = TestClient(app)


def _sample_csv_text() -> str:
    return """order_id,user_id,name,phone,city,order_date,amount,product,age,status
ORD900001,U1001,张三,13800000001,shanghai,2026/05/01,1999,Laptop,28,Paid
ORD900002,U1002,李四,invalid_phone,北京,invalid_date,-30,Phone,200,cancel
ORD900003,U1003,王五,,Guangzhou,2026年05月02日,unknown,Tablet,unknown,refunded
"""


def _cafe_sales_csv_text() -> str:
    return """Transaction ID,Customer Name,Phone Number,Location,Transaction Date,Total Spent,Item,Payment Status
TX1001,Alice,13800001111,shanghai,2026/05/03,88.5,Latte,Paid
TX1002,Bob,invalid_phone,Guangzhou,invalid_date,-8,Mocha,cancel
TX1003,Carol,,Beijing,2026年05月05日,unknown,Espresso,refunded
"""


def _wait_job_done(job_id: str, timeout_sec: int = 90) -> dict:
    cursor = 0
    deadline = time.time() + timeout_sec
    latest = {}
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}", params={"cursor": cursor})
        assert resp.status_code == 200
        latest = resp.json()
        cursor = latest.get("next_cursor", cursor)
        if latest.get("status") in {"done", "error"}:
            return latest
        time.sleep(0.5)
    raise TimeoutError(f"Job timeout: {job_id}")


def test_create_job_and_finish() -> None:
    resp = client.post(
        "/api/jobs",
        data={
            "csv_text": _sample_csv_text(),
            "enable_llm": "0",
            "model": "gpt-4.1-mini",
        },
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    done = _wait_job_done(job_id)
    assert done["status"] == "done"
    assert done["result"] is not None
    assert done["result"]["summary"]["质量分数"]["清洗后"] >= done["result"]["summary"]["质量分数"]["清洗前"]


def test_download_zip_artifact() -> None:
    create_resp = client.post(
        "/api/jobs",
        data={"csv_text": _sample_csv_text(), "enable_llm": "0"},
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]
    done = _wait_job_done(job_id)
    assert done["status"] == "done"

    download_resp = client.get(f"/api/jobs/{job_id}/download/zip")
    assert download_resp.status_code == 200
    assert len(download_resp.content) > 100


def test_history_keeps_recent_five() -> None:
    for _ in range(6):
        create_resp = client.post("/api/jobs", data={"csv_text": _sample_csv_text(), "enable_llm": "0"})
        assert create_resp.status_code == 200
        _wait_job_done(create_resp.json()["job_id"])

    history_resp = client.get("/api/history")
    assert history_resp.status_code == 200
    jobs = history_resp.json()["jobs"]
    assert len(jobs) <= 5


def test_auto_mapping_for_non_standard_headers() -> None:
    create_resp = client.post(
        "/api/jobs",
        data={"csv_text": _cafe_sales_csv_text(), "enable_llm": "0"},
    )
    assert create_resp.status_code == 200
    done = _wait_job_done(create_resp.json()["job_id"])
    assert done["status"] == "done"
    mapping = done["result"]["schema_mapping"]["final_mapping"]
    assert mapping["order_id"] == "Transaction ID"
    assert mapping["amount"] == "Total Spent"
    assert mapping["order_date"] == "Transaction Date"


def test_manual_mapping_override() -> None:
    custom_csv = """ID,Spent,Date,ItemName
A1,99,2026-05-01,Coffee
A2,-6,invalid_date,Tea
"""
    mapping_json = json.dumps(
        {
            "order_id": "ID",
            "amount": "Spent",
            "order_date": "Date",
            "product": "ItemName",
        },
        ensure_ascii=False,
    )
    create_resp = client.post(
        "/api/jobs",
        data={
            "csv_text": custom_csv,
            "enable_llm": "0",
            "column_mapping_json": mapping_json,
        },
    )
    assert create_resp.status_code == 200
    done = _wait_job_done(create_resp.json()["job_id"])
    assert done["status"] == "done"
    mapping = done["result"]["schema_mapping"]["final_mapping"]
    assert mapping["order_id"] == "ID"
    assert mapping["amount"] == "Spent"
    assert done["result"]["after_score"] is not None
    assert done["result"]["after_score"] > 0


def test_mapping_preview_endpoint() -> None:
    resp = client.post(
        "/api/mapping/preview",
        data={"csv_text": _cafe_sales_csv_text()},
    )
    assert resp.status_code == 200
    data = resp.json()
    final_mapping = data["schema_mapping"]["final_mapping"]
    assert final_mapping["order_id"] == "Transaction ID"
    assert "mapped_preview" in data
