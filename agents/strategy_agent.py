from __future__ import annotations

from typing import Dict, List

from utils.llm_client import generate_strategy_advice, llm_strategy_enabled


class StrategyAgent:
    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.name = "StrategyAgent"
        self.enable_llm = llm_strategy_enabled()

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[{self.name}] {message}")

    def run(self, quality_result: Dict) -> List[Dict]:
        issues = quality_result["issue_counts"]
        strategies: List[Dict] = []

        if issues["duplicate_rows"] > 0:
            strategies.append(
                {"issue": "完全重复行", "strategy": "删除完全重复行（keep=first）", "field": "all_columns"}
            )
        if issues["duplicate_order_id"] > 0:
            strategies.append(
                {"issue": "order_id 重复", "strategy": "按 order_id 去重，保留第一条", "field": "order_id"}
            )
        if issues["invalid_date_count"] > 0:
            strategies.append(
                {"issue": "日期格式不统一/非法", "strategy": "统一转为 YYYY-MM-DD，非法日期填充为 unknown", "field": "order_date"}
            )
        if issues["invalid_amount_count"] > 0:
            strategies.append(
                {
                    "issue": "金额异常",
                    "strategy": "非法值转 NaN；负数和极端值标记后用中位数填充",
                    "field": "amount",
                }
            )
        if issues["invalid_age_count"] > 0:
            strategies.append(
                {"issue": "年龄异常", "strategy": "非法值转 NaN，使用中位数填充并约束到 0~120", "field": "age"}
            )
        if issues["invalid_phone_count"] > 0:
            strategies.append(
                {"issue": "手机号异常", "strategy": "非法手机号标记并替换为 missing_phone", "field": "phone"}
            )
        if issues["inconsistent_city_count"] > 0 or issues["missing_values_total"] > 0:
            strategies.append(
                {"issue": "城市字段不统一", "strategy": "统一映射为中文城市名，缺失填 unknown", "field": "city"}
            )
        if issues["inconsistent_status_count"] > 0:
            strategies.append(
                {"issue": "状态字段不统一", "strategy": "统一映射为 paid/refund/cancelled/unknown", "field": "status"}
            )

        if self.enable_llm:
            llm_advice = generate_strategy_advice(issues)
            if llm_advice:
                strategies.append(
                    {
                        "issue": "API补充建议",
                        "strategy": llm_advice.replace("\n", "；"),
                        "field": "多字段",
                    }
                )
                self._log("已通过 API 生成补充策略建议")
            else:
                self._log("API 已启用，但未返回可用建议，继续使用规则策略")

        self._log(f"已生成 {len(strategies)} 条清洗策略")
        return strategies
