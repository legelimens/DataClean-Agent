from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _safe_set(df: pd.DataFrame, idx: int, column: str, value) -> None:
    if 0 <= idx < len(df):
        df.at[idx, column] = value


def generate_dirty_orders(output_path: Path, rows: int = 80, random_seed: int = 42) -> pd.DataFrame:
    """Generate a dirty enterprise-style orders dataset for demo usage."""
    rng = np.random.default_rng(random_seed)

    names = [
        "张伟",
        "王芳",
        "李娜",
        "刘洋",
        "陈杰",
        "赵敏",
        "周涛",
        "吴丹",
        "郑凯",
        "孙丽",
    ]
    products = ["Laptop", "Phone", "Tablet", "Headset", "Monitor", "Keyboard", "Camera"]
    cities = ["上海", "北京", "广州", "深圳", "杭州"]
    statuses = ["paid", "refund", "cancelled"]
    date_pool = pd.date_range("2026-04-01", periods=50, freq="D").strftime("%Y-%m-%d").tolist()

    records = []
    for i in range(rows):
        records.append(
            {
                "order_id": f"ORD{100000 + i}",
                "user_id": f"U{1000 + rng.integers(1, 500)}",
                "name": rng.choice(names),
                "phone": f"1{rng.integers(3000000000, 9999999999)}",
                "city": rng.choice(cities),
                "order_date": rng.choice(date_pool),
                "amount": round(float(rng.uniform(50, 5000)), 2),
                "product": rng.choice(products),
                "age": int(rng.integers(18, 60)),
                "status": rng.choice(statuses),
            }
        )

    df = pd.DataFrame(records)
    # Convert selected columns to object so we can safely inject dirty mixed-type values.
    df["amount"] = df["amount"].astype(object)
    df["age"] = df["age"].astype(object)

    # 1) Missing values
    for idx in [2, 11, 34]:
        _safe_set(df, idx, "phone", "")
    for idx in [5, 23, 59]:
        _safe_set(df, idx, "age", "")
    for idx in [7, 40]:
        _safe_set(df, idx, "amount", "")
    for idx in [9, 60]:
        _safe_set(df, idx, "city", "")

    # 2) Duplicate values
    if rows > 76:
        df.loc[75] = df.loc[10]
        df.loc[76] = df.loc[10]
    if rows > 77:
        df.loc[77] = df.loc[20]

    # order_id duplicates with slight differences
    if rows > 78:
        df.loc[78] = df.loc[15]
        _safe_set(df, 78, "order_id", df.loc[15, "order_id"])
        _safe_set(df, 78, "amount", 1888.0)
        _safe_set(df, 78, "status", "Paid")
    if rows > 79:
        df.loc[79] = df.loc[25]
        _safe_set(df, 79, "order_id", df.loc[25, "order_id"])
        _safe_set(df, 79, "city", "Guangzhou")
        _safe_set(df, 79, "phone", "13800AB123")

    # 3) Date format issues
    _safe_set(df, 13, "order_date", "2026/05/01")
    _safe_set(df, 14, "order_date", "2026-05-01")
    _safe_set(df, 15, "order_date", "2026.05.01")
    _safe_set(df, 16, "order_date", "2026年05月01日")
    _safe_set(df, 17, "order_date", "invalid_date")

    # 4) Amount issues
    _safe_set(df, 18, "amount", "unknown")
    _safe_set(df, 19, "amount", -88)
    _safe_set(df, 20, "amount", 999999)
    _safe_set(df, 21, "amount", "")

    # 5) Age issues
    _safe_set(df, 22, "age", -3)
    _safe_set(df, 23, "age", 200)
    _safe_set(df, 24, "age", "")
    _safe_set(df, 25, "age", "unknown")

    # 6) Phone issues
    _safe_set(df, 26, "phone", "")
    _safe_set(df, 27, "phone", "invalid_phone")
    _safe_set(df, 28, "phone", "1234567")
    _safe_set(df, 29, "phone", "13800AB123")

    # 7) City format issues
    _safe_set(df, 30, "city", "上海")
    _safe_set(df, 31, "city", "shanghai")
    _safe_set(df, 32, "city", "Shanghai")
    _safe_set(df, 33, "city", "SH")
    _safe_set(df, 34, "city", "北京")
    _safe_set(df, 35, "city", "beijing")
    _safe_set(df, 36, "city", "Guangzhou")
    _safe_set(df, 37, "city", "广州")

    # 8) Status format issues
    _safe_set(df, 38, "status", "paid")
    _safe_set(df, 39, "status", "Paid")
    _safe_set(df, 40, "status", "PAID")
    _safe_set(df, 41, "status", "refund")
    _safe_set(df, 42, "status", "refunded")
    _safe_set(df, 43, "status", "cancelled")
    _safe_set(df, 44, "status", "cancel")
    _safe_set(df, 45, "status", "unknown")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return df
