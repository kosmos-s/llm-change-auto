"""Compare original label hints and LLM outputs."""

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


def label_hint_to_change(label: str) -> int:
    label = str(label).lower()
    if "no" in label and "change" in label:
        return 0
    if "unchange" in label:
        return 0
    return 1


def compare(input_csv: Path, output_csv: Path, confidence_threshold: float = 0.70) -> None:
    df = pd.read_csv(input_csv)
    rows = []
    for _, row in df.iterrows():
        original_change = label_hint_to_change(row.get("original_label", ""))
        llm_change = int(row.get("llm_change", 0) or 0)
        confidence = float(row.get("confidence", 0.0) or 0.0)

        mismatch = original_change != llm_change
        low_confidence = confidence < confidence_threshold
        empty_class_when_change = llm_change == 1 and not any(int(row.get(k, 0) or 0) for k in LABEL_KEYS)

        new_row = row.to_dict()
        new_row["original_change"] = original_change
        new_row["label_mismatch"] = mismatch
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
