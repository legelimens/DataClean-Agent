from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_quality_comparison_chart(validation_result: Dict, output_path: Path) -> None:
    """Generate a bar chart comparing key data quality indicators before and after cleaning."""
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    metrics = [
        ("missing_values_total", "缺失值"),
        ("duplicate_rows", "重复行"),
        ("invalid_date_count", "日期错误"),
        ("invalid_amount_count", "金额异常"),
        ("invalid_age_count", "年龄异常"),
        ("invalid_phone_count", "手机号异常"),
    ]

    before = [validation_result["before"][key] for key, _ in metrics]
    after = [validation_result["after"][key] for key, _ in metrics]
    labels = [label for _, label in metrics]
    x = list(range(len(labels)))

    plt.figure(figsize=(8, 4))
    width = 0.36
    plt.bar([i - width / 2 for i in x], before, width=width, label="清洗前", color="#D1495B")
    plt.bar([i + width / 2 for i in x], after, width=width, label="清洗后", color="#2A9D8F")

    plt.title("数据质量指标对比：清洗前 vs 清洗后")
    plt.xticks(x, labels, rotation=15)
    plt.ylabel("数量")
    plt.legend()
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150)
    plt.close()
