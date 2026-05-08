from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import run_pipeline


@pytest.fixture(scope="session")
def clean_df() -> pd.DataFrame:
    run_pipeline(project_root=PROJECT_ROOT, row_count=80, verbose=False)
    clean_path = PROJECT_ROOT / "outputs" / "clean_orders.csv"
    return pd.read_csv(clean_path, encoding="utf-8-sig")


def test_clean_file_generated() -> None:
    clean_path = PROJECT_ROOT / "outputs" / "clean_orders.csv"
    run_pipeline(project_root=PROJECT_ROOT, row_count=80, verbose=False)
    assert clean_path.exists(), "clean_orders.csv should be generated."


def test_no_full_duplicate_rows(clean_df: pd.DataFrame) -> None:
    assert int(clean_df.duplicated().sum()) == 0


def test_order_date_format(clean_df: pd.DataFrame) -> None:
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    assert clean_df["order_date"].map(
        lambda x: bool(pattern.match(str(x))) or str(x).strip().lower() == "unknown"
    ).all()


def test_age_range(clean_df: pd.DataFrame) -> None:
    assert ((clean_df["age"] >= 0) & (clean_df["age"] <= 120)).all()


def test_amount_non_negative(clean_df: pd.DataFrame) -> None:
    assert (clean_df["amount"] >= 0).all()


def test_status_domain(clean_df: pd.DataFrame) -> None:
    allowed_status = {"paid", "refund", "cancelled", "unknown"}
    assert set(clean_df["status"]).issubset(allowed_status)


def test_city_domain(clean_df: pd.DataFrame) -> None:
    allowed_cities = {"上海", "北京", "广州", "深圳", "杭州", "unknown"}
    assert set(clean_df["city"]).issubset(allowed_cities)
