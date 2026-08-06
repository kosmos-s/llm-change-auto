"""Evaluate OpenAI labeling results against original JSON labels."""

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


def evaluate_dataframe(df: pd.DataFrame, target: float = 0.85) -> dict[str, object]:
    if "error" in df.columns:
        valid = df[df["error"].fillna("").astype(str).str.strip().eq("")].copy()
    else:
        valid = df.copy()

    total_rows = len(df)
    valid_rows = len(valid)
    api_errors = total_rows - valid_rows

    if valid.empty:
        return {
            "total_rows": total_rows,
            "valid_rows": 0,
            "api_errors": api_errors,
            "change_accuracy": 0.0,
            "detail_macro_accuracy": 0.0,
            "detail_exact_match": 0.0,
            "target": target,
            "target_met": False,
            "per_label_accuracy": {},
        }

    original_change = valid["original_change"].map(as_int)
    llm_change = valid["llm_change"].map(as_int)
    change_accuracy = float((original_change == llm_change).mean())

    per_label_accuracy: dict[str, float] = {}
    exact_matches = []
    for _, row in valid.iterrows():
        row_matches = []
        for key in LABEL_KEYS:
            original_value = as_int(row.get(f"original_{key}", 0))
            llm_value = as_int(row.get(key, 0))
            row_matches.append(original_value == llm_value)
        exact_matches.append(all(row_matches))

    for key in LABEL_KEYS:
        original_values = valid[f"original_{key}"].map(as_int)
        llm_values = valid[key].map(as_int)
        per_label_accuracy[key] = float((original_values == llm_values).mean())

    detail_macro_accuracy = float(sum(per_label_accuracy.values()) / len(per_label_accuracy))
    detail_exact_match = float(sum(exact_matches) / len(exact_matches))

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "api_errors": api_errors,
        "change_accuracy": change_accuracy,
        "detail_macro_accuracy": detail_macro_accuracy,
        "detail_exact_match": detail_exact_match,
        "target": target,
        "target_met": change_accuracy >= target,
        "per_label_accuracy": per_label_accuracy,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--target", type=float, default=0.85)
    args = parser.parse_args()

    result = evaluate_dataframe(pd.read_csv(Path(args.csv)), target=args.target)
    print(f"rows={result['total_rows']} valid={result['valid_rows']} errors={result['api_errors']}")
    print(f"change_accuracy={result['change_accuracy']:.4f}")
    print(f"detail_macro_accuracy={result['detail_macro_accuracy']:.4f}")
    print(f"detail_exact_match={result['detail_exact_match']:.4f}")
    print(f"target={result['target']:.2f} target_met={result['target_met']}")
    for key, accuracy in result["per_label_accuracy"].items():
        print(f"{key}_accuracy={accuracy:.4f}")


if __name__ == "__main__":
    main()
