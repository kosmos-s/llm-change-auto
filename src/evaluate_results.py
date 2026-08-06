"""Analyze OpenAI labeling results against the current JSON labels.

These metrics describe the LLM-assisted review tool. They are not the final
change-detection model F2-Score target of the industry project.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

LABEL_KEYS = [
    "arti",
    "arti_bu",
    "arti_bu_t",
    "arti_binil",
    "arti_road",
    "arti_roa_m",
    "arti_other",
    "tree",
    "fore",
    "farm",
    "water",
]


def as_int(value: object) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_dataframe(df: pd.DataFrame) -> dict[str, object]:
    if "error" in df.columns:
        valid = df[df["error"].fillna("").astype(str).str.strip().eq("")].copy()
    else:
        valid = df.copy()

    total_rows = len(df)
    valid_rows = len(valid)
    api_errors = total_rows - valid_rows

    empty_result = {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "api_errors": api_errors,
        "change_accuracy": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "f2": 0.0,
        "tp": 0,
        "tn": 0,
        "fp": 0,
        "fn": 0,
        "detail_macro_accuracy": 0.0,
        "detail_exact_match": 0.0,
        "per_label_accuracy": {},
    }
    if valid.empty:
        return empty_result

    original_change = valid["original_change"].map(as_int)
    llm_change = valid["llm_change"].map(as_int)

    tp = int(((original_change == 1) & (llm_change == 1)).sum())
    tn = int(((original_change == 0) & (llm_change == 0)).sum())
    fp = int(((original_change == 0) & (llm_change == 1)).sum())
    fn = int(((original_change == 1) & (llm_change == 0)).sum())

    accuracy = safe_div(tp + tn, valid_rows)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    beta_squared = 4.0
    f2 = safe_div((1 + beta_squared) * precision * recall, beta_squared * precision + recall)

    per_label_accuracy: dict[str, float] = {}
    exact_matches: list[bool] = []

    for _, row in valid.iterrows():
        row_matches = []
        for key in LABEL_KEYS:
            original_value = as_int(row.get(f"original_{key}", 0))
            llm_value = as_int(row.get(key, 0))
            row_matches.append(original_value == llm_value)
        exact_matches.append(all(row_matches))

    for key in LABEL_KEYS:
        original_column = f"original_{key}"
        if original_column not in valid.columns or key not in valid.columns:
            continue
        original_values = valid[original_column].map(as_int)
        llm_values = valid[key].map(as_int)
        per_label_accuracy[key] = float((original_values == llm_values).mean())

    detail_macro_accuracy = (
        float(sum(per_label_accuracy.values()) / len(per_label_accuracy))
        if per_label_accuracy
        else 0.0
    )
    detail_exact_match = float(sum(exact_matches) / len(exact_matches)) if exact_matches else 0.0

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "api_errors": api_errors,
        "change_accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "f2": f2,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "detail_macro_accuracy": detail_macro_accuracy,
        "detail_exact_match": detail_exact_match,
        "per_label_accuracy": per_label_accuracy,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    args = parser.parse_args()

    result = evaluate_dataframe(pd.read_csv(Path(args.csv)))
    print(f"rows={result['total_rows']} valid={result['valid_rows']} errors={result['api_errors']}")
    print(f"change_accuracy={result['change_accuracy']:.4f}")
    print(f"precision={result['precision']:.4f}")
    print(f"recall={result['recall']:.4f}")
    print(f"f1={result['f1']:.4f}")
    print(f"f2={result['f2']:.4f}")
    print(f"tp={result['tp']} tn={result['tn']} fp={result['fp']} fn={result['fn']}")
    print(f"detail_macro_accuracy={result['detail_macro_accuracy']:.4f}")
    print(f"detail_exact_match={result['detail_exact_match']:.4f}")
    for key, accuracy in result["per_label_accuracy"].items():
        print(f"{key}_accuracy={accuracy:.4f}")


if __name__ == "__main__":
    main()
