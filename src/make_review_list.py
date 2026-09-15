"""Create prioritized human-review sample lists."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "o"}


def build_priority_score(row: pd.Series) -> float:
    """Higher scores are reviewed first.

    API failure > change mismatch > detail mismatch > low confidence > model-requested review.
    """
    score = 0.0
    error = str(row.get("error", "") or "").strip()
    if error and error.lower() != "nan":
        score += 300.0
    if as_bool(row.get("label_mismatch", False)):
        score += 160.0
    if as_bool(row.get("detail_mismatch", False)):
        score += 100.0
    if as_bool(row.get("empty_class_when_change", False)):
        score += 80.0
    if as_bool(row.get("low_confidence", False)):
        score += 60.0
    if as_bool(row.get("review_required", False)):
        score += 30.0

    try:
        confidence = float(row.get("confidence", 1.0))
        if pd.isna(confidence):
            confidence = 1.0
    except Exception:
        confidence = 1.0
    score += max(0.0, min(1.0, 1.0 - confidence)) * 50.0
    return round(score, 3)


def make_review_list(compare_csv: Path, output_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(compare_csv)
    if "review_required_final" not in df.columns:
        raise ValueError("review_required_final column not found. Run compare_labels.py first.")

    mask = df["review_required_final"].apply(as_bool)
    review_df = df[mask].copy()
    if not review_df.empty:
        review_df["priority_score"] = review_df.apply(build_priority_score, axis=1)
        secondary = [col for col in ["group", "split", "error_type", "image_name"] if col in review_df.columns]
        review_df = review_df.sort_values(
            ["priority_score", *secondary],
            ascending=[False, *([True] * len(secondary))],
            kind="stable",
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    review_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"review_count={len(review_df)} saved={output_csv}")
    return review_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", default="outputs/compare_results/compare_results.csv")
    parser.add_argument("--output", default="outputs/review_lists/review_required.csv")
    args = parser.parse_args()

    make_review_list(Path(args.compare), Path(args.output))


if __name__ == "__main__":
    main()
