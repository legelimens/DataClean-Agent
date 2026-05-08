from __future__ import annotations

import json
import re
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

STANDARD_COLUMNS = [
    "order_id",
    "user_id",
    "name",
    "phone",
    "city",
    "order_date",
    "amount",
    "product",
    "age",
    "status",
]

ALIAS_MAP = {
    "order_id": [
        "order_id",
        "订单编号",
        "订单号",
        "transaction id",
        "transaction_id",
        "invoice id",
        "invoice_id",
        "sale id",
        "receipt id",
    ],
    "user_id": [
        "user_id",
        "用户编号",
        "客户编号",
        "customer id",
        "customer_id",
        "client id",
        "member id",
    ],
    "name": [
        "name",
        "姓名",
        "客户姓名",
        "customer name",
        "customer_name",
        "client name",
    ],
    "phone": [
        "phone",
        "手机号",
        "手机",
        "电话号码",
        "mobile",
        "mobile number",
        "phone number",
        "contact number",
    ],
    "city": [
        "city",
        "城市",
        "地区",
        "location",
        "store location",
        "branch city",
    ],
    "order_date": [
        "order_date",
        "订单日期",
        "日期",
        "transaction date",
        "transaction_date",
        "sale date",
        "purchase date",
        "date",
    ],
    "amount": [
        "amount",
        "金额",
        "订单金额",
        "总金额",
        "total",
        "total spent",
        "total_spent",
        "total amount",
        "revenue",
        "sales amount",
    ],
    "product": [
        "product",
        "商品",
        "商品名称",
        "item",
        "menu item",
        "product name",
    ],
    "age": [
        "age",
        "年龄",
        "customer age",
        "user age",
    ],
    "status": [
        "status",
        "状态",
        "订单状态",
        "payment status",
        "order status",
    ],
}


def normalize_header(text: str) -> str:
    return re.sub(r"[\s_\-./\\:()\[\]{}]+", "", str(text).strip().lower())


def _build_alias_norm_map() -> Dict[str, set]:
    return {k: {normalize_header(v) for v in vals + [k]} for k, vals in ALIAS_MAP.items()}


ALIAS_NORM_MAP = _build_alias_norm_map()


def auto_detect_mapping(columns: Iterable[str]) -> Dict[str, str]:
    columns = [str(c) for c in columns]
    used_cols = set()
    mapping: Dict[str, str] = {}

    # 1) Exact normalized standard-name match
    for std in STANDARD_COLUMNS:
        std_norm = normalize_header(std)
        for col in columns:
            if col in used_cols:
                continue
            if normalize_header(col) == std_norm:
                mapping[std] = col
                used_cols.add(col)
                break

    # 2) Alias exact match
    for std in STANDARD_COLUMNS:
        if std in mapping:
            continue
        aliases = ALIAS_NORM_MAP[std]
        for col in columns:
            if col in used_cols:
                continue
            if normalize_header(col) in aliases:
                mapping[std] = col
                used_cols.add(col)
                break

    # 3) Lightweight fuzzy contains
    contains_tokens = {
        "order_id": ["order", "transaction", "invoice", "receipt"],
        "user_id": ["user", "customer", "client", "member"],
        "name": ["name"],
        "phone": ["phone", "mobile", "contact"],
        "city": ["city", "location", "branch"],
        "order_date": ["date", "time", "transactiondate", "purchasedate"],
        "amount": ["amount", "total", "spent", "revenue", "sales"],
        "product": ["product", "item", "menu"],
        "age": ["age"],
        "status": ["status", "state", "payment"],
    }
    for std in STANDARD_COLUMNS:
        if std in mapping:
            continue
        tokens = contains_tokens[std]
        for col in columns:
            if col in used_cols:
                continue
            norm_col = normalize_header(col)
            if any(token in norm_col for token in tokens):
                mapping[std] = col
                used_cols.add(col)
                break
    return mapping


def parse_manual_mapping_json(mapping_json: Optional[str]) -> Dict[str, str]:
    if not mapping_json or mapping_json.strip() == "":
        return {}
    obj = json.loads(mapping_json)
    if not isinstance(obj, dict):
        raise ValueError("字段映射 JSON 必须是对象，例如 {\"amount\":\"Total Spent\"}")
    result: Dict[str, str] = {}
    for std, src in obj.items():
        std_key = str(std).strip()
        if std_key not in STANDARD_COLUMNS:
            raise ValueError(f"字段映射 key 不合法: {std_key}")
        src_name = str(src).strip()
        if src_name:
            result[std_key] = src_name
    return result


def apply_schema_mapping(
    df: pd.DataFrame,
    manual_mapping: Optional[Dict[str, str]] = None,
) -> Tuple[pd.DataFrame, Dict]:
    input_df = df.copy()
    input_df.columns = [str(c).strip() for c in input_df.columns]
    auto_mapping = auto_detect_mapping(input_df.columns)
    manual_mapping = manual_mapping or {}

    final_mapping = auto_mapping.copy()
    final_mapping.update(manual_mapping)

    for std, src in list(final_mapping.items()):
        if src not in input_df.columns:
            final_mapping.pop(std, None)

    transformed = input_df.copy()
    for std in STANDARD_COLUMNS:
        src = final_mapping.get(std)
        if src:
            transformed[std] = input_df[src]
        elif std not in transformed.columns:
            transformed[std] = np.nan

    missing_standards = [std for std in STANDARD_COLUMNS if std not in final_mapping]
    mapped_count = len(final_mapping)
    city_source = final_mapping.get("city", "")
    status_source = final_mapping.get("status", "")
    city_norm = normalize_header(city_source) if city_source else ""
    status_norm = normalize_header(status_source) if status_source else ""

    semantic_hints = {
        "city_from_location": "location" in city_norm,
        "status_from_payment_method": ("payment" in status_norm and "status" not in status_norm),
    }

    info = {
        "auto_mapping": auto_mapping,
        "manual_mapping": manual_mapping,
        "final_mapping": final_mapping,
        "missing_standard_fields": missing_standards,
        "mapped_count": mapped_count,
        "total_input_columns": len(input_df.columns),
        "semantic_hints": semantic_hints,
    }
    return transformed, info
