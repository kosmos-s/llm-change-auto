"""Compare original JSON labels and LLM outputs."""

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


def as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "o"}:
        return True
    if text in {"false", "0", "no", "n", "x", "", "nan"}:
        return False
    return default


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def compare(input_csv: Path, output_csv: Path, confidence_threshold: float = 0.70) -> None:
    df = pd.read_csv(input_csv)
    rows = []
    for _, row in df.iterrows():
        original_change = as_int(row.get("original_change", 0))
        llm_change = as_int(row.get("llm_change", 0))
        confidence = as_float(row.get("confidence", 0.0), 0.0)

        detail_mismatch_keys = []
        for key in LABEL_KEYS:
            original_value = as_int(row.get(f"original_{key}", row.get(key, 0)))
            llm_value = as_int(row.get(key, 0))
            if original_value != llm_value:
                detail_mismatch_keys.append(key)

        label_mismatch = original_change != llm_change
        detail_mismatch = bool(detail_mismatch_keys)
        low_confidence = confidence < confidence_threshold
        empty_class_when_change = llm_change == 1 and not any(as_int(row.get(k, 0)) for k in LABEL_KEYS)
        llm_error = bool(str(row.get("error", "")).strip())
        llm_self_review = as_bool(row.get("review_required", True), default=True)

        review_reasons = []
        if llm_error:
            review_reasons.append("llm_error")
        if llm_self_review:
            review_reasons.append("llm_review_required")
        if label_mismatch:
            review_reasons.append("change_mismatch")
        if detail_mismatch:
            review_reasons.append("detail_mismatch")
        if low_confidence:
            review_reasons.append("low_confidence")
        if empty_class_when_change:
            review_reasons.append("empty_class_when_change")

        new_row = row.to_dict()
        new_row["label_mismatch"] = label_mismatch
        new_row["detail_mismatch_keys"] = ",".join(detail_mismatch_keys)
        new_row["detail_mismatch"] = detail_mismatch
        new_row["low_confidence"] = low_confidence
        new_row["empty_class_when_change"] = empty_class_when_change
        new_row["review_reasons"] = ",".join(review_reasons)
        new_row["review_required_final"] = bool(review_reasons)
        rows.append(new_row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"saved={output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", default="outputs/llm_results/llm_results.csv")
    parser.add_argument("--output", default="outputs/compare_results/compare_results.csv")
    parser.add_argument("--confidence-threshold", type=float, default=0.70)
    args = parser.parse_args()

    compare(Path(args.llm), Path(args.output), args.confidence_threshold)


if __name__ == "__main__":
    main()
