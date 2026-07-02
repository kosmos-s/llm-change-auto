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


def compare(input_csv: Path, output_csv: Path, confidence_threshold: float = 0.70) -> None:
    df = pd.read_csv(input_csv)
    rows = []
    for _, row in df.iterrows():
        original_change = as_int(row.get("original_change", 0))
        llm_change = as_int(row.get("llm_change", 0))
        confidence = float(row.get("confidence", 0.0) or 0.0)

        # 기존 JSON 라벨과 LLM 세부 라벨 비교
        detail_mismatch_keys = []
        for key in LABEL_KEYS:
            original_value = as_int(row.get(f"original_{key}", row.get(key, 0)))
            llm_value = as_int(row.get(key, 0))
            if original_value != llm_value:
                detail_mismatch_keys.append(key)

        mismatch = original_change != llm_change
        low_confidence = confidence < confidence_threshold
        empty_class_when_change = llm_change == 1 and not any(as_int(row.get(k, 0)) for k in LABEL_KEYS)

        new_row = row.to_dict()
        new_row["label_mismatch"] = mismatch
        new_row["detail_mismatch_keys"] = ",".join(detail_mismatch_keys)
        new_row["detail_mismatch"] = bool(detail_mismatch_keys)
        new_row["low_confidence"] = low_confidence
        new_row["empty_class_when_change"] = empty_class_when_change
        new_row["review_required_final"] = bool(
            row.get("review_required", True) or mismatch or low_confidence or empty_class_when_change
        )
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
