from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from utils.metrics import is_missing


class ProfilerAgent:
    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.name = "ProfilerAgent"

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[{self.name}] {message}")

    def _infer_column_type(self, series: pd.Series) -> str:
        non_missing = series[~series.map(is_missing)]
        if non_missing.empty:
            return "unknown"

        numeric_ratio = pd.to_numeric(non_missing, errors="coerce").notna().mean()
        if numeric_ratio > 0.8:
            return "numeric"
        return "string"

    def run(self, data_path: Path) -> Tuple[pd.DataFrame, Dict]:
        df = pd.read_csv(data_path, encoding="utf-8-sig")
        rows, cols = df.shape

        missing_by_column = {col: int(df[col].map(is_missing).sum()) for col in df.columns}
        inferred_types = {col: self._infer_column_type(df[col]) for col in df.columns}

        profile = {
            "total_rows": int(rows),
            "total_columns": int(cols),
            "missing_by_column": missing_by_column,
            "inferred_types": inferred_types,
        }

        self._log(f"已加载数据：{rows} 行，{cols} 列")
        self._log(f"缺失值统计：{missing_by_column}")
        return df, profile
