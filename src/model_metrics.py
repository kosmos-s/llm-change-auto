"""Load and compare baseline vs cleaned-model evaluation metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

METRIC_KEYS = ["precision", "recall", "f1", "f2"]


def _normalize_metric_dict(data: dict[str, Any]) -> dict[str, float]:
    result: dict[str, float] = {}
    lowered = {str(k).strip().lower(): v for k, v in data.items()}
    aliases = {
        "precision": ["precision"],
        "recall": ["recall"],
        "f1": ["f1", "f1_score", "f1-score"],
        "f2": ["f2", "f2_score", "f2-score"],
    }
    for key, names in aliases.items():
        for name in names:
            if name in lowered:
                try:
                    result[key] = float(lowered[name])
                except Exception:
                    pass
                break
    return result


def load_metrics_file(path: Path) -> dict[str, float]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON은 metric:value 객체여야 합니다.")
        return _normalize_metric_dict(data)

    frame = pd.read_csv(path)
    if frame.empty:
        return {}

    lower_cols = {str(c).strip().lower(): c for c in frame.columns}
    if "metric" in lower_cols and "value" in lower_cols:
        metric_col = lower_cols["metric"]
        value_col = lower_cols["value"]
        data = {str(row[metric_col]): row[value_col] for _, row in frame.iterrows()}
        return _normalize_metric_dict(data)

    return _normalize_metric_dict(frame.iloc[0].to_dict())


def compare_metrics(before: dict[str, float], after: dict[str, float]) -> pd.DataFrame:
    rows = []
    for key in METRIC_KEYS:
        before_value = before.get(key)
        after_value = after.get(key)
        delta = None if before_value is None or after_value is None else after_value - before_value
        rows.append({"metric": key, "before": before_value, "after": after_value, "delta": delta})
    return pd.DataFrame(rows)
