from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from utils.metrics import (
    is_valid_phone,
    normalize_city,
    normalize_date,
    normalize_status,
    parse_age,
    parse_amount,
)


class CleanerAgent:
    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.name = "CleanerAgent"

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[{self.name}] {message}")

    def run(
        self,
        df: pd.DataFrame,
        strategies: List[Dict],
        output_path: Path,
        quality_scope_fields: Optional[Iterable[str]] = None,
    ) -> Tuple[pd.DataFrame, Dict]:
        _ = strategies  # Keep for readability: strategy generation and execution are intentionally decoupled.
        clean_df = df.copy()
        cleaning_stats: Dict[str, int] = {}
        scope = set(quality_scope_fields or df.columns.tolist())

        # 1) Remove fully duplicated rows
        before_rows = len(clean_df)
        clean_df = clean_df.drop_duplicates(keep="first").copy()
        removed_full_duplicates = before_rows - len(clean_df)
        cleaning_stats["removed_full_duplicates"] = int(removed_full_duplicates)
        self._log(f"删除了 {removed_full_duplicates} 行完全重复数据")

        # 2) Remove duplicated order_id rows (keep first)
        before_rows = len(clean_df)
        clean_df = clean_df.drop_duplicates(subset=["order_id"], keep="first").copy()
        removed_order_id_duplicates = before_rows - len(clean_df)
        cleaning_stats["removed_order_id_duplicates"] = int(removed_order_id_duplicates)
        self._log(f"删除了 {removed_order_id_duplicates} 行重复 order_id 数据")

        # 3) Normalize date format
        if "order_date" in scope:
            normalized_dates = clean_df["order_date"].map(normalize_date)
            invalid_date_mask = normalized_dates.isna()
            date_fill_value = "unknown"

            old_dates = clean_df["order_date"].astype(str)
            clean_df["order_date"] = normalized_dates.fillna(date_fill_value)
            standardized_dates = int((old_dates != clean_df["order_date"].astype(str)).sum())
            cleaning_stats["standardized_dates"] = standardized_dates
            cleaning_stats["filled_invalid_dates"] = int(invalid_date_mask.sum())
            self._log(f"标准化了 {standardized_dates} 个日期值")
        else:
            cleaning_stats["standardized_dates"] = 0
            cleaning_stats["filled_invalid_dates"] = 0

        # 4) Clean amount and keep outlier mark
        if "amount" in scope:
            amount_numeric = clean_df["amount"].map(parse_amount)
            amount_is_negative = amount_numeric < 0
            amount_is_outlier = amount_numeric > 100000
            amount_invalid_mask = amount_numeric.isna() | amount_is_negative | amount_is_outlier
            amount_median = amount_numeric[~amount_invalid_mask].median()
            if pd.isna(amount_median):
                amount_median = 0.0
            clean_df["amount_is_outlier"] = amount_is_outlier.fillna(False).astype(bool)
            clean_df["amount"] = amount_numeric.where(~amount_invalid_mask, other=amount_median).round(2)
            cleaning_stats["fixed_amount_values"] = int(amount_invalid_mask.sum())
            self._log(f"修复了 {int(amount_invalid_mask.sum())} 个金额异常值")
        else:
            cleaning_stats["fixed_amount_values"] = 0

        # 5) Clean age and keep invalid mark
        if "age" in scope:
            age_numeric = clean_df["age"].map(parse_age)
            age_invalid_mask = age_numeric.isna() | (age_numeric < 0) | (age_numeric > 120)
            age_median = age_numeric[~age_invalid_mask].median()
            if pd.isna(age_median):
                age_median = 30
            clean_df["age_is_invalid"] = age_invalid_mask.fillna(False).astype(bool)
            clean_df["age"] = np.round(age_numeric.where(~age_invalid_mask, other=age_median)).astype(int)
            cleaning_stats["fixed_age_values"] = int(age_invalid_mask.sum())
            self._log(f"修复了 {int(age_invalid_mask.sum())} 个年龄异常值")
        else:
            cleaning_stats["fixed_age_values"] = 0

        # 6) Normalize phone
        if "phone" in scope:
            clean_df["phone"] = clean_df["phone"].astype(object)
            phone_invalid_mask = ~clean_df["phone"].map(lambda x: is_valid_phone(x, allow_placeholder=False))
            clean_df["phone_is_invalid"] = phone_invalid_mask.astype(bool)
            clean_df.loc[phone_invalid_mask, "phone"] = "missing_phone"
            cleaning_stats["fixed_phone_values"] = int(phone_invalid_mask.sum())
            self._log(f"标记了 {int(phone_invalid_mask.sum())} 个异常手机号")
        else:
            cleaning_stats["fixed_phone_values"] = 0

        # 7) Normalize city
        if "city" in scope:
            old_city = clean_df["city"].astype(str)
            clean_df["city"] = clean_df["city"].map(normalize_city)
            city_changed = int((old_city != clean_df["city"].astype(str)).sum())
            cleaning_stats["standardized_city_values"] = city_changed
            self._log(f"统一了 {city_changed} 个城市值")
        else:
            cleaning_stats["standardized_city_values"] = 0

        # 8) Normalize status
        if "status" in scope:
            old_status = clean_df["status"].astype(str)
            clean_df["status"] = clean_df["status"].map(normalize_status)
            status_changed = int((old_status != clean_df["status"].astype(str)).sum())
            cleaning_stats["standardized_status_values"] = status_changed
            self._log(f"统一了 {status_changed} 个状态值")
        else:
            cleaning_stats["standardized_status_values"] = 0

        output_path.parent.mkdir(parents=True, exist_ok=True)
        clean_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        self._log(f"清洗数据已保存至 {output_path.as_posix()}")
        return clean_df, cleaning_stats
