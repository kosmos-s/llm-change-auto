"""Analyze OpenAI labeling results against original or human-confirmed labels.

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
        text = str(value).strip().lower()
        return 1 if text in {"o", "true", "yes", "y"} else 0


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _empty_result(total_rows: int, valid_rows: int, api_errors: int) -> dict[str, object]:
    return {
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


def evaluate_pair_dataframe(
    df: pd.DataFrame,
    *,
    truth_change_col: str,
    pred_change_col: str,
    truth_label_prefix: str,
    pred_label_prefix: str,
    error_col: str | None = None,
) -> dict[str, object]:
    """Evaluate binary change + detail labels for configurable column prefixes."""
    if error_col and error_col in df.columns:
        valid = df[df[error_col].fillna("").astype(str).str.strip().eq("")].copy()
    else:
        valid = df.copy()

    if truth_change_col in valid.columns and pred_change_col in valid.columns:
        truth_present = valid[truth_change_col].notna() & valid[truth_change_col].astype(str).str.strip().ne("")
        pred_present = valid[pred_change_col].notna() & valid[pred_change_col].astype(str).str.strip().ne("")
        valid = valid[truth_present & pred_present].copy()

    total_rows = len(df)
    valid_rows = len(valid)
    api_errors = total_rows - valid_rows if error_col else 0
    if valid.empty or truth_change_col not in valid.columns or pred_change_col not in valid.columns:
        return _empty_result(total_rows, valid_rows, api_errors)

    truth_change = valid[truth_change_col].map(as_int)
    pred_change = valid[pred_change_col].map(as_int)

    tp = int(((truth_change == 1) & (pred_change == 1)).sum())
    tn = int(((truth_change == 0) & (pred_change == 0)).sum())
    fp = int(((truth_change == 0) & (pred_change == 1)).sum())
    fn = int(((truth_change == 1) & (pred_change == 0)).sum())

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
            truth_col = f"{truth_label_prefix}{key}"
            pred_col = f"{pred_label_prefix}{key}"
            if truth_col not in valid.columns or pred_col not in valid.columns:
                continue
            row_matches.append(as_int(row.get(truth_col, 0)) == as_int(row.get(pred_col, 0)))
        if row_matches:
            exact_matches.append(all(row_matches))

    for key in LABEL_KEYS:
        truth_col = f"{truth_label_prefix}{key}"
        pred_col = f"{pred_label_prefix}{key}"
        if truth_col not in valid.columns or pred_col not in valid.columns:
            continue
        truth_values = valid[truth_col].map(as_int)
        pred_values = valid[pred_col].map(as_int)
        per_label_accuracy[key] = float((truth_values == pred_values).mean())

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


def evaluate_dataframe(df: pd.DataFrame) -> dict[str, object]:
    return evaluate_pair_dataframe(
        df,
        truth_change_col="original_change",
        pred_change_col="llm_change",
        truth_label_prefix="original_",
        pred_label_prefix="",
        error_col="error",
    )


def evaluate_history_dataframe(history: pd.DataFrame) -> dict[str, object]:
    """Evaluate GPT against human-confirmed labels for reviewed rows only."""
    return evaluate_pair_dataframe(
        history,
        truth_change_col="human_change",
        pred_change_col="llm_change",
        truth_label_prefix="human_",
        pred_label_prefix="llm_",
        error_col="llm_error",
    )


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
