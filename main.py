from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

from agents import CleanerAgent, ProfilerAgent, QualityAgent, ReportAgent, StrategyAgent, ValidatorAgent
from utils.data_generator import generate_dirty_orders
from utils.llm_client import llm_strategy_enabled
from utils.visualization import generate_quality_comparison_chart


def _build_chinese_summary(validation_result: Dict, cleaning_stats: Dict) -> Dict:
    before = validation_result["before"]
    after = validation_result["after"]
    return {
        "质量分数": {"清洗前": before["quality_score"], "清洗后": after["quality_score"]},
        "缺失值数量": {"清洗前": before["missing_values_total"], "清洗后": after["missing_values_total"]},
        "重复行数量": {"清洗前": before["duplicate_rows"], "清洗后": after["duplicate_rows"]},
        "日期错误数量": {"清洗前": before["invalid_date_count"], "清洗后": after["invalid_date_count"]},
        "金额异常数量": {"清洗前": before["invalid_amount_count"], "清洗后": after["invalid_amount_count"]},
        "年龄异常数量": {"清洗前": before["invalid_age_count"], "清洗后": after["invalid_age_count"]},
        "手机号异常数量": {"清洗前": before["invalid_phone_count"], "清洗后": after["invalid_phone_count"]},
        "执行统计": {
            "删除完全重复行": cleaning_stats.get("removed_full_duplicates", 0),
            "删除重复order_id行": cleaning_stats.get("removed_order_id_duplicates", 0),
            "标准化日期值": cleaning_stats.get("standardized_dates", 0),
            "修复金额异常": cleaning_stats.get("fixed_amount_values", 0),
            "修复年龄异常": cleaning_stats.get("fixed_age_values", 0),
            "标记手机号异常": cleaning_stats.get("fixed_phone_values", 0),
            "统一城市字段": cleaning_stats.get("standardized_city_values", 0),
            "统一状态字段": cleaning_stats.get("standardized_status_values", 0),
        },
    }


def _apply_llm_runtime_env(llm_runtime: Optional[Dict[str, str]]) -> Dict[str, Optional[str]]:
    previous = {
        "DATACLEAN_ENABLE_LLM": os.getenv("DATACLEAN_ENABLE_LLM"),
        "DATACLEAN_API_KEY": os.getenv("DATACLEAN_API_KEY"),
        "DATACLEAN_API_URL": os.getenv("DATACLEAN_API_URL"),
        "DATACLEAN_MODEL": os.getenv("DATACLEAN_MODEL"),
    }
    if not llm_runtime:
        return previous

    for key, value in llm_runtime.items():
        if value is None:
            continue
        os.environ[key] = value
    return previous


def _restore_llm_runtime_env(previous: Dict[str, Optional[str]]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def run_pipeline(
    project_root: Optional[Path] = None,
    row_count: int = 80,
    verbose: bool = True,
    input_csv_path: Optional[Path] = None,
    outputs_dir: Optional[Path] = None,
    llm_runtime: Optional[Dict[str, str]] = None,
    quality_scope_fields: Optional[Iterable[str]] = None,
) -> Dict:
    root = Path(project_root) if project_root else Path(__file__).resolve().parent
    data_path = Path(input_csv_path) if input_csv_path else (root / "data" / "dirty_orders.csv")
    pipeline_outputs_dir = Path(outputs_dir) if outputs_dir else (root / "outputs")
    pipeline_outputs_dir.mkdir(parents=True, exist_ok=True)

    if input_csv_path and not data_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {data_path.as_posix()}")

    if not data_path.exists():
        generate_dirty_orders(data_path, rows=row_count)
        if verbose:
            print("[系统] 未找到 data/dirty_orders.csv，已自动生成模拟脏数据。")

    previous_env = _apply_llm_runtime_env(llm_runtime)
    try:
        profiler = ProfilerAgent(verbose=verbose)
        quality_agent = QualityAgent(verbose=verbose)
        strategy_agent = StrategyAgent(verbose=verbose)
        cleaner_agent = CleanerAgent(verbose=verbose)
        validator_agent = ValidatorAgent(verbose=verbose)
        report_agent = ReportAgent(verbose=verbose)

        raw_df, profile = profiler.run(data_path)
        quality_result = quality_agent.run(raw_df, quality_scope_fields=quality_scope_fields)
        strategies = strategy_agent.run(quality_result)

        clean_csv_path = pipeline_outputs_dir / "clean_orders.csv"
        clean_df, cleaning_stats = cleaner_agent.run(
            raw_df,
            strategies,
            clean_csv_path,
            quality_scope_fields=quality_scope_fields,
        )

        validation_result = validator_agent.run(
            raw_df,
            clean_df,
            quality_scope_fields=quality_scope_fields,
        )

        chart_path = pipeline_outputs_dir / "quality_comparison.png"
        generate_quality_comparison_chart(validation_result, chart_path)
        if verbose:
            print(f"[系统] 质量对比图已保存：{chart_path.as_posix()}")

        quality_metrics_path = pipeline_outputs_dir / "quality_metrics.json"
        metrics_payload = {
            "生成时间": datetime.now().isoformat(timespec="seconds"),
            "是否提升": validation_result["is_improved"],
            "是否启用LLM策略API": llm_strategy_enabled(),
            "评分字段范围": validation_result["before"].get("quality_scope_fields", []),
            "before": validation_result["before"],
            "after": validation_result["after"],
            "comparison": validation_result["comparison"],
            "cleaning_actions": cleaning_stats,
            "中文摘要": _build_chinese_summary(validation_result, cleaning_stats),
        }
        quality_metrics_path.write_text(
            json.dumps(metrics_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if verbose:
            print(f"[系统] 质量指标已保存：{quality_metrics_path.as_posix()}")

        report_md_path = pipeline_outputs_dir / "data_quality_report.md"
        report_html_path = pipeline_outputs_dir / "data_quality_report.html"
        report_agent.run(
            profile=profile,
            quality_result=quality_result,
            strategies=strategies,
            validation_result=validation_result,
            raw_df=raw_df,
            clean_df=clean_df,
            cleaning_stats=cleaning_stats,
            output_path=report_md_path,
            html_output_path=report_html_path,
            chart_relative_path=chart_path.name,
        )

        if verbose:
            print("[系统] 全流程执行完成。")

        return {
            "project_root": str(root),
            "dirty_data_path": str(data_path),
            "clean_data_path": str(clean_csv_path),
            "metrics_path": str(quality_metrics_path),
            "report_md_path": str(report_md_path),
            "report_html_path": str(report_html_path),
            "chart_path": str(chart_path),
            "outputs_dir": str(pipeline_outputs_dir),
        }
    finally:
        _restore_llm_runtime_env(previous_env)


if __name__ == "__main__":
    run_pipeline()
