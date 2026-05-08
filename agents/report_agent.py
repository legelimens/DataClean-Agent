from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


class ReportAgent:
    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.name = "ReportAgent"

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[{self.name}] {message}")

    @staticmethod
    def _table(headers: List[str], rows: List[List[str]]) -> str:
        header_line = "| " + " | ".join(headers) + " |"
        split_line = "| " + " | ".join(["---"] * len(headers)) + " |"
        body_lines = ["| " + " | ".join(map(str, row)) + " |" for row in rows]
        return "\n".join([header_line, split_line] + body_lines)

    @staticmethod
    def _html_table(headers: List[str], rows: List[List[str]]) -> str:
        head = "".join([f"<th>{escape(str(h))}</th>" for h in headers])
        body = []
        for row in rows:
            tds = "".join([f"<td>{escape(str(v))}</td>" for v in row])
            body.append(f"<tr>{tds}</tr>")
        return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"

    @staticmethod
    def _rule_catalog_rows() -> List[List[str]]:
        return [
            ["完全重复行", "删除完全重复行（keep=first）", "否", "固定启用"],
            ["order_id 重复", "按 order_id 去重，保留第一条", "否", "固定启用"],
            ["日期格式异常", "统一转 YYYY-MM-DD，非法填 unknown", "是", "填充值=unknown"],
            ["金额异常", "非法/负数/极端值转中位数，并标记异常", "是", "极端阈值=100000"],
            ["年龄异常", "非法年龄转中位数并约束在 0~120", "是", "范围=0~120"],
            ["手机号异常", "非法手机号替换 missing_phone，并打标", "是", "占位=missing_phone"],
            ["城市字段", "统一映射到标准集合（不识别则 unknown）", "是", "标准集合=上海/北京/广州/深圳/杭州/unknown"],
            ["状态字段", "统一映射到 paid/refund/cancelled/unknown", "是", "标准集合固定"],
            ["字段映射", "自动映射 + 手工 JSON 覆盖", "是", "自动映射优先，手工覆盖自动"],
            ["质量评分", "按已映射字段范围计分，避免未映射字段误罚", "是", "默认按映射字段评分"],
            ["LLM 增强策略", "仅补充策略建议，不直接改动清洗执行", "是", "默认关闭，失败自动回退规则"],
        ]

    def _render_html(
        self,
        profile: Dict,
        issue_counts: Dict,
        strategies: List[Dict],
        before: Dict,
        after: Dict,
        raw_rows: List[List[str]],
        clean_rows: List[List[str]],
        sample_headers: List[str],
        cleaning_stats: Dict,
        chart_relative_path: str,
    ) -> str:
        strategy_rows = [[item["issue"], item["field"], item["strategy"]] for item in strategies]
        comparison_rows = [
            ["缺失值数量", before["missing_values_total"], after["missing_values_total"]],
            ["重复行数量", before["duplicate_rows"], after["duplicate_rows"]],
            ["日期格式错误数量", before["invalid_date_count"], after["invalid_date_count"]],
            ["金额异常数量", before["invalid_amount_count"], after["invalid_amount_count"]],
            ["年龄异常数量", before["invalid_age_count"], after["invalid_age_count"]],
            ["手机号异常数量", before["invalid_phone_count"], after["invalid_phone_count"]],
            ["城市格式不统一数量", before["inconsistent_city_count"], after["inconsistent_city_count"]],
            ["状态不统一数量", before["inconsistent_status_count"], after["inconsistent_status_count"]],
            ["数据质量分数", before["quality_score"], after["quality_score"]],
        ]
        actions_rows = [
            ["删除完全重复行", cleaning_stats.get("removed_full_duplicates", 0)],
            ["删除重复 order_id 行", cleaning_stats.get("removed_order_id_duplicates", 0)],
            ["标准化日期值", cleaning_stats.get("standardized_dates", 0)],
            ["修复金额异常", cleaning_stats.get("fixed_amount_values", 0)],
            ["修复年龄异常", cleaning_stats.get("fixed_age_values", 0)],
            ["标记手机号异常", cleaning_stats.get("fixed_phone_values", 0)],
            ["统一城市字段", cleaning_stats.get("standardized_city_values", 0)],
            ["统一状态字段", cleaning_stats.get("standardized_status_values", 0)],
        ]
        rule_catalog_rows = self._rule_catalog_rows()

        strategy_table = self._html_table(["问题类型", "字段", "清洗策略"], strategy_rows)
        rule_catalog_table = self._html_table(["规则项", "处理逻辑", "可配置", "默认值"], rule_catalog_rows)
        comparison_table = self._html_table(["指标", "清洗前", "清洗后"], comparison_rows)
        actions_table = self._html_table(["执行动作", "处理数量"], actions_rows)
        raw_table = self._html_table(sample_headers, raw_rows)
        clean_table = self._html_table(sample_headers, clean_rows)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DataClean-Agent 数据质量报告</title>
  <style>
    :root {{
      --bg: #f7f8fb;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --brand: #1d4ed8;
      --ok: #059669;
      --warn: #d97706;
      --line: #e5e7eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
      background: linear-gradient(180deg, #f7f8fb 0%, #eef2ff 100%);
      color: var(--text);
    }}
    .container {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 20px;
      margin-bottom: 18px;
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      color: var(--brand);
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin: 18px 0;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
    }}
    .card .k {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 6px;
    }}
    .card .v {{
      font-size: 24px;
      font-weight: 700;
    }}
    .section {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 14px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 20px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      font-size: 14px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f8fafc;
      color: #0f172a;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    .img-wrap {{
      background: #fff;
      border: 1px dashed var(--line);
      border-radius: 10px;
      padding: 8px;
    }}
    .img-wrap img {{
      width: 100%;
      display: block;
      border-radius: 8px;
    }}
    .conclusion {{
      color: var(--ok);
      font-weight: 700;
    }}
    @media (max-width: 900px) {{
      .cards {{ grid-template-columns: repeat(2, 1fr); }}
      .two-col {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <section class="hero">
      <h1>DataClean-Agent 数据质量报告（可视化版）</h1>
      <p>面向企业订单数据的多智能体清洗 Demo：自动检测、自动策略、自动清洗、自动验证。</p>
    </section>

    <section class="cards">
      <div class="card"><div class="k">原始行数</div><div class="v">{profile['total_rows']}</div></div>
      <div class="card"><div class="k">列数</div><div class="v">{profile['total_columns']}</div></div>
      <div class="card"><div class="k">质量分（清洗前）</div><div class="v">{before['quality_score']}</div></div>
      <div class="card"><div class="k">质量分（清洗后）</div><div class="v">{after['quality_score']}</div></div>
    </section>

    <section class="section">
      <h2>1. 原始数据问题摘要</h2>
      <ul>
        <li>缺失值总数：{issue_counts['missing_values_total']}</li>
        <li>完全重复行：{issue_counts['duplicate_rows']}</li>
        <li>order_id 重复：{issue_counts['duplicate_order_id']}</li>
        <li>日期格式错误：{issue_counts['invalid_date_count']}</li>
        <li>金额异常：{issue_counts['invalid_amount_count']}</li>
        <li>年龄异常：{issue_counts['invalid_age_count']}</li>
        <li>手机号异常：{issue_counts['invalid_phone_count']}</li>
        <li>城市格式不统一：{issue_counts['inconsistent_city_count']}</li>
        <li>状态不统一：{issue_counts['inconsistent_status_count']}</li>
      </ul>
    </section>

    <section class="section">
      <h2>2. 清洗策略</h2>
      {strategy_table}
    </section>

    <section class="section">
      <h2>3. 清洗规则总表</h2>
      {rule_catalog_table}
    </section>

    <section class="section">
      <h2>4. 清洗前后指标对比</h2>
      {comparison_table}
    </section>

    <section class="section">
      <h2>5. 清洗动作统计</h2>
      {actions_table}
    </section>

    <section class="section">
      <h2>6. 可视化对比图</h2>
      <div class="img-wrap"><img src="{escape(chart_relative_path)}" alt="质量对比图" /></div>
    </section>

    <section class="section">
      <h2>7. 示例数据前后对比（前 5 行）</h2>
      <div class="two-col">
        <div>
          <h3>清洗前</h3>
          {raw_table}
        </div>
        <div>
          <h3>清洗后</h3>
          {clean_table}
        </div>
      </div>
    </section>

    <section class="section">
      <h2>8. 结论</h2>
      <p class="conclusion">数据质量分由 {before['quality_score']} 提升至 {after['quality_score']}，清洗效果显著，可直接用于 BI 分析和数据入库。</p>
    </section>
  </div>
</body>
</html>
"""

    def run(
        self,
        profile: Dict,
        quality_result: Dict,
        strategies: List[Dict],
        validation_result: Dict,
        raw_df: pd.DataFrame,
        clean_df: pd.DataFrame,
        cleaning_stats: Dict,
        output_path: Path,
        html_output_path: Optional[Path] = None,
        chart_relative_path: str = "quality_comparison.png",
    ) -> None:
        issue_counts = quality_result["issue_counts"]
        before = validation_result["before"]
        after = validation_result["after"]

        strategy_rows = [[item["issue"], item["field"], item["strategy"]] for item in strategies]
        strategy_table = self._table(["问题类型", "字段", "清洗策略"], strategy_rows)
        rule_catalog_rows = self._rule_catalog_rows()
        rule_catalog_table = self._table(["规则项", "处理逻辑", "可配置", "默认值"], rule_catalog_rows)

        comparison_rows = [
            ["缺失值数量", before["missing_values_total"], after["missing_values_total"]],
            ["重复行数量", before["duplicate_rows"], after["duplicate_rows"]],
            ["日期格式错误数量", before["invalid_date_count"], after["invalid_date_count"]],
            ["金额异常数量", before["invalid_amount_count"], after["invalid_amount_count"]],
            ["年龄异常数量", before["invalid_age_count"], after["invalid_age_count"]],
            ["手机号异常数量", before["invalid_phone_count"], after["invalid_phone_count"]],
            ["城市格式不统一数量", before["inconsistent_city_count"], after["inconsistent_city_count"]],
            ["状态不统一数量", before["inconsistent_status_count"], after["inconsistent_status_count"]],
            ["数据质量分数", before["quality_score"], after["quality_score"]],
        ]
        comparison_table = self._table(["指标", "清洗前", "清洗后"], comparison_rows)

        sample_raw = raw_df.head(5)[
            ["order_id", "phone", "city", "order_date", "amount", "age", "status"]
        ].copy()
        sample_clean = clean_df.head(5)[
            ["order_id", "phone", "city", "order_date", "amount", "age", "status"]
        ].copy()

        raw_rows = sample_raw.fillna("").astype(str).values.tolist()
        clean_rows = sample_clean.fillna("").astype(str).values.tolist()
        sample_headers = ["订单ID", "手机号", "城市", "订单日期", "订单金额", "年龄", "订单状态"]

        report_content = f"""# DataClean-Agent 数据质量报告

## 1. 项目简介
DataClean-Agent 是一个面向企业订单数据的数据质量检测与自动清洗 Demo，展示 Agentic Coding 在数据治理场景中的应用价值。

## 2. Agent 协作流程
1. ProfilerAgent：读取 CSV 并生成数据画像；
2. QualityAgent：检测缺失值、重复值、格式错误与异常值；
3. StrategyAgent：基于检测结果生成清洗策略；
4. CleanerAgent：执行清洗并输出 clean_orders.csv；
5. ValidatorAgent：对比清洗前后指标并计算质量分；
6. ReportAgent：生成 Markdown 与 HTML 报告。

## 3. 原始数据问题
- 总行数：{profile['total_rows']}
- 总列数：{profile['total_columns']}
- 缺失值总数：{issue_counts['missing_values_total']}
- 完全重复行：{issue_counts['duplicate_rows']}
- order_id 重复：{issue_counts['duplicate_order_id']}
- 日期格式错误：{issue_counts['invalid_date_count']}
- 金额异常：{issue_counts['invalid_amount_count']}
- 年龄异常：{issue_counts['invalid_age_count']}
- 手机号异常：{issue_counts['invalid_phone_count']}
- 城市格式不统一：{issue_counts['inconsistent_city_count']}
- 状态不统一：{issue_counts['inconsistent_status_count']}

## 4. 清洗策略
{strategy_table}

## 5. 清洗规则总表
{rule_catalog_table}

## 6. 清洗前后对比
{comparison_table}

### 执行动作统计
- 删除完全重复行：{cleaning_stats.get('removed_full_duplicates', 0)}
- 删除重复 order_id 行：{cleaning_stats.get('removed_order_id_duplicates', 0)}
- 标准化日期值：{cleaning_stats.get('standardized_dates', 0)}
- 修复金额异常：{cleaning_stats.get('fixed_amount_values', 0)}
- 修复年龄异常：{cleaning_stats.get('fixed_age_values', 0)}
- 标记手机号异常：{cleaning_stats.get('fixed_phone_values', 0)}
- 统一城市字段：{cleaning_stats.get('standardized_city_values', 0)}
- 统一状态字段：{cleaning_stats.get('standardized_status_values', 0)}

## 7. 示例数据前后对比
### 清洗前（示例前 5 行）
{self._table(sample_headers, raw_rows)}

### 清洗后（示例前 5 行）
{self._table(sample_headers, clean_rows)}

## 8. 结果结论
清洗后数据质量分从 {before['quality_score']} 提升到 {after['quality_score']}，重复记录、格式错误和异常值显著下降。该结果说明 DataClean-Agent 可以有效支持后续 BI 分析、报表统计与数据入库，并可扩展到客户数据、销售数据和日志数据场景。
"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report_content, encoding="utf-8")
        self._log(f"Markdown 报告已保存：{output_path.as_posix()}")

        if html_output_path is not None:
            html_output_path.parent.mkdir(parents=True, exist_ok=True)
            html_content = self._render_html(
                profile=profile,
                issue_counts=issue_counts,
                strategies=strategies,
                before=before,
                after=after,
                raw_rows=raw_rows,
                clean_rows=clean_rows,
                sample_headers=sample_headers,
                cleaning_stats=cleaning_stats,
                chart_relative_path=chart_relative_path,
            )
            html_output_path.write_text(html_content, encoding="utf-8")
            self._log(f"HTML 报告已保存：{html_output_path.as_posix()}")
