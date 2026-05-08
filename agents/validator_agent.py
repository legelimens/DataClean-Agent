from __future__ import annotations

from typing import Dict, Iterable, Optional

import pandas as pd

from utils.metrics import compute_quality_metrics


class ValidatorAgent:
    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.name = "ValidatorAgent"

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[{self.name}] {message}")

    def run(
        self,
        raw_df: pd.DataFrame,
        clean_df: pd.DataFrame,
        quality_scope_fields: Optional[Iterable[str]] = None,
    ) -> Dict:
        before = compute_quality_metrics(raw_df, quality_scope_fields=quality_scope_fields)
        after = compute_quality_metrics(clean_df, quality_scope_fields=quality_scope_fields)

        compare_keys = [
            "missing_values_total",
            "duplicate_rows",
            "duplicate_order_id",
            "invalid_date_count",
            "invalid_amount_count",
            "invalid_age_count",
            "invalid_phone_count",
            "inconsistent_city_count",
            "inconsistent_status_count",
        ]

        comparison = {}
        for key in compare_keys:
            comparison[key] = {
                "before": before[key],
                "after": after[key],
                "delta": after[key] - before[key],
            }
        comparison["quality_score"] = {
            "before": before["quality_score"],
            "after": after["quality_score"],
            "delta": round(after["quality_score"] - before["quality_score"], 2),
        }

        is_improved = after["quality_score"] > before["quality_score"]
        self._log(f"质量分：{before['quality_score']} -> {after['quality_score']}")
        self._log(f"清洗是否有效：{'是' if is_improved else '否'}")

        return {
            "before": before,
            "after": after,
            "comparison": comparison,
            "is_improved": is_improved,
        }
