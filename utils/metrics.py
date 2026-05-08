from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日")
CANONICAL_CITIES = {"上海", "北京", "广州", "深圳", "杭州", "unknown"}
CANONICAL_STATUSES = {"paid", "refund", "cancelled", "unknown"}
UNKNOWN_DATE_VALUE = "unknown"
DEFAULT_QUALITY_SCOPE = ["order_id", "order_date", "amount", "status", "phone", "city", "age"]

CITY_MAPPING = {
    "上海": "上海",
    "shanghai": "上海",
    "sh": "上海",
    "beijing": "北京",
    "北京": "北京",
    "guangzhou": "广州",
    "广州": "广州",
    "shenzhen": "深圳",
    "深圳": "深圳",
    "hangzhou": "杭州",
    "杭州": "杭州",
    "unknown": "unknown",
}

STATUS_MAPPING = {
    "paid": "paid",
    "refund": "refund",
    "refunded": "refund",
    "cancelled": "cancelled",
    "cancel": "cancelled",
    "unknown": "unknown",
}


def strip_text(value: Any) -> str | None:
    """Return normalized string or None for blank-ish values."""
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    return text


def is_missing(value: Any) -> bool:
    text = strip_text(value)
    if text is None:
        return True
    return text.lower() in {"nan", "none", "null"}


def normalize_date(value: Any) -> str | None:
    text = strip_text(value)
    if text is None:
        return None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def is_valid_or_unknown_date(value: Any) -> bool:
    text = strip_text(value)
    if text is None:
        return False
    if text.lower() == UNKNOWN_DATE_VALUE:
        return True
    return normalize_date(text) is not None


def parse_amount(value: Any) -> float:
    text = strip_text(value)
    if text is None:
        return np.nan
    if text.lower() in {"unknown", "nan", "none", "null"}:
        return np.nan
    try:
        return float(text)
    except ValueError:
        return np.nan


def parse_age(value: Any) -> float:
    text = strip_text(value)
    if text is None:
        return np.nan
    if text.lower() in {"unknown", "nan", "none", "null"}:
        return np.nan
    try:
        return float(text)
    except ValueError:
        return np.nan


def normalize_city(value: Any) -> str:
    text = strip_text(value)
    if text is None:
        return "unknown"
    return CITY_MAPPING.get(text.lower(), text if text in CANONICAL_CITIES else "unknown")


def normalize_status(value: Any) -> str:
    text = strip_text(value)
    if text is None:
        return "unknown"
    return STATUS_MAPPING.get(text.lower(), "unknown")


def is_valid_phone(value: Any, allow_placeholder: bool = True) -> bool:
    text = strip_text(value)
    if text is None:
        return False
    if allow_placeholder and text == "missing_phone":
        return True
    return bool(re.fullmatch(r"1\d{10}", text))


def _series_from_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=object)
    return df[column]


def _resolve_quality_scope(df: pd.DataFrame, quality_scope_fields: Optional[Iterable[str]]) -> List[str]:
    if quality_scope_fields:
        scope = [col for col in quality_scope_fields if col in df.columns]
        if scope:
            return scope
    default_scope = [col for col in DEFAULT_QUALITY_SCOPE if col in df.columns]
    if default_scope:
        return default_scope
    return list(df.columns)


def calculate_quality_score(issue_total: int) -> float:
    # A lightweight scoring rule for demo usage.
    return round(max(0.0, 100.0 - issue_total * 0.6), 2)


def compute_quality_metrics(df: pd.DataFrame, quality_scope_fields: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    rows, cols = df.shape
    quality_scope = _resolve_quality_scope(df, quality_scope_fields)

    missing_by_column = {}
    for col in df.columns:
        missing_by_column[col] = int(_series_from_column(df, col).map(is_missing).sum())
    missing_values_total = int(sum(missing_by_column[col] for col in quality_scope))

    duplicate_rows = int(df.duplicated().sum())
    duplicate_order_id = 0
    if "order_id" in quality_scope and "order_id" in df.columns:
        duplicate_order_id = int(df["order_id"].duplicated().sum())

    invalid_date_count = 0
    if "order_date" in quality_scope and "order_date" in df.columns:
        date_series = _series_from_column(df, "order_date")
        non_missing_date = date_series[~date_series.map(is_missing)]
        invalid_date_count = int(non_missing_date.map(lambda x: not is_valid_or_unknown_date(x)).sum())

    invalid_phone_count = 0
    if "phone" in quality_scope and "phone" in df.columns:
        phone_series = _series_from_column(df, "phone")
        non_missing_phone = phone_series[~phone_series.map(is_missing)]
        invalid_phone_count = int(non_missing_phone.map(lambda x: not is_valid_phone(x)).sum())

    amount_negative_count = 0
    amount_outlier_count = 0
    invalid_amount_count = 0
    if "amount" in quality_scope and "amount" in df.columns:
        amount_raw = _series_from_column(df, "amount")
        amount_non_missing_mask = ~amount_raw.map(is_missing)
        amount_series = amount_raw.map(parse_amount)
        amount_negative_count = int((amount_series < 0).sum())
        amount_outlier_count = int((amount_series > 100000).sum())
        invalid_amount_count = int(
            (amount_non_missing_mask & (amount_series.isna() | (amount_series < 0) | (amount_series > 100000))).sum()
        )

    invalid_age_count = 0
    if "age" in quality_scope and "age" in df.columns:
        age_raw = _series_from_column(df, "age")
        age_non_missing_mask = ~age_raw.map(is_missing)
        age_series = age_raw.map(parse_age)
        invalid_age_count = int((age_non_missing_mask & (age_series.isna() | (age_series < 0) | (age_series > 120))).sum())

    inconsistent_city_count = 0
    if "city" in quality_scope and "city" in df.columns:
        city_series = _series_from_column(df, "city").map(strip_text)
        inconsistent_city_count = int(city_series.map(lambda x: x is not None and x not in CANONICAL_CITIES).sum())

    inconsistent_status_count = 0
    if "status" in quality_scope and "status" in df.columns:
        status_series = _series_from_column(df, "status").map(strip_text)
        inconsistent_status_count = int(
            status_series.map(lambda x: x is not None and x.lower() not in CANONICAL_STATUSES).sum()
        )

    issue_total = (
        missing_values_total
        + duplicate_rows
        + duplicate_order_id
        + invalid_date_count
        + invalid_phone_count
        + invalid_amount_count
        + invalid_age_count
        + inconsistent_city_count
        + inconsistent_status_count
    )

    return {
        "total_rows": int(rows),
        "total_columns": int(cols),
        "missing_by_column": missing_by_column,
        "missing_values_total": missing_values_total,
        "duplicate_rows": duplicate_rows,
        "duplicate_order_id": duplicate_order_id,
        "invalid_date_count": invalid_date_count,
        "invalid_phone_count": invalid_phone_count,
        "invalid_amount_count": invalid_amount_count,
        "amount_negative_count": amount_negative_count,
        "amount_outlier_count": amount_outlier_count,
        "invalid_age_count": invalid_age_count,
        "inconsistent_city_count": inconsistent_city_count,
        "inconsistent_status_count": inconsistent_status_count,
        "issue_total": issue_total,
        "quality_score": calculate_quality_score(issue_total),
        "quality_scope_fields": quality_scope,
    }
