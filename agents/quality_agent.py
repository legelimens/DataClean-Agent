from __future__ import annotations

from typing import Dict, Iterable, Optional

import pandas as pd

from utils.metrics import (
    compute_quality_metrics,
    is_missing,
    is_valid_phone,
    is_valid_or_unknown_date,
    parse_age,
    parse_amount,
    strip_text,
)


class QualityAgent:
    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.name = "QualityAgent"

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[{self.name}] {message}")

    def run(self, df: pd.DataFrame, quality_scope_fields: Optional[Iterable[str]] = None) -> Dict:
        metrics = compute_quality_metrics(df, quality_scope_fields=quality_scope_fields)

        missing_by_column = {k: v for k, v in metrics["missing_by_column"].items() if v > 0}

        duplicate_row_indices = df[df.duplicated(keep=False)].index.tolist()
        duplicate_order_ids = []
        if "order_id" in df.columns:
            duplicate_order_ids = df[df["order_id"].duplicated(keep=False)]["order_id"].astype(str).tolist()

        invalid_date_indices = []
        if "order_date" in df.columns and "order_date" in metrics["quality_scope_fields"]:
            invalid_date_indices = df[
                df["order_date"].map(lambda x: (not is_missing(x)) and (not is_valid_or_unknown_date(x)))
            ].index.tolist()

        invalid_phone_indices = []
        if "phone" in df.columns and "phone" in metrics["quality_scope_fields"]:
            invalid_phone_indices = df[
                df["phone"].map(lambda x: (not is_missing(x)) and (not is_valid_phone(x, allow_placeholder=False)))
            ].index.tolist()

        invalid_amount_indices = []
        if "amount" in df.columns and "amount" in metrics["quality_scope_fields"]:
            amount_numeric = df["amount"].map(parse_amount)
            amount_non_missing = ~df["amount"].map(is_missing)
            invalid_amount_indices = df[
                amount_non_missing & (amount_numeric.isna() | (amount_numeric < 0) | (amount_numeric > 100000))
            ].index.tolist()

        invalid_age_indices = []
        if "age" in df.columns and "age" in metrics["quality_scope_fields"]:
            age_numeric = df["age"].map(parse_age)
            age_non_missing = ~df["age"].map(is_missing)
            invalid_age_indices = df[
                age_non_missing & (age_numeric.isna() | (age_numeric < 0) | (age_numeric > 120))
            ].index.tolist()

        invalid_city_indices = []
        if "city" in df.columns and "city" in metrics["quality_scope_fields"]:
            city_raw = df["city"].map(strip_text)
            invalid_city_indices = df[
                city_raw.map(lambda x: x is not None and x not in {"上海", "北京", "广州", "深圳", "杭州", "unknown"})
            ].index.tolist()

        invalid_status_indices = []
        if "status" in df.columns and "status" in metrics["quality_scope_fields"]:
            status_raw = df["status"].map(strip_text)
            invalid_status_indices = df[
                status_raw.map(lambda x: x is not None and x.lower() not in {"paid", "refund", "cancelled", "unknown"})
            ].index.tolist()

        issue_counts = {
            "missing_values_total": metrics["missing_values_total"],
            "duplicate_rows": metrics["duplicate_rows"],
            "duplicate_order_id": metrics["duplicate_order_id"],
            "invalid_date_count": metrics["invalid_date_count"],
            "invalid_phone_count": metrics["invalid_phone_count"],
            "invalid_amount_count": metrics["invalid_amount_count"],
            "invalid_age_count": metrics["invalid_age_count"],
            "inconsistent_city_count": metrics["inconsistent_city_count"],
            "inconsistent_status_count": metrics["inconsistent_status_count"],
        }

        result = {
            "issue_counts": issue_counts,
            "issue_total": metrics["issue_total"],
            "issue_details": {
                "missing_by_column": missing_by_column,
                "duplicate_row_indices": duplicate_row_indices,
                "duplicate_order_ids": duplicate_order_ids,
                "invalid_date_indices": invalid_date_indices,
                "invalid_phone_indices": invalid_phone_indices,
                "invalid_amount_indices": invalid_amount_indices,
                "invalid_age_indices": invalid_age_indices,
                "invalid_city_indices": invalid_city_indices,
                "invalid_status_indices": invalid_status_indices,
            },
            "metrics_snapshot": metrics,
        }

        self._log(f"发现 {metrics['issue_total']} 个数据质量问题")
        return result
