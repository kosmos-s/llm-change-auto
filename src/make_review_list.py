"""Create review-required sample list."""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def make_review_list(compare_csv: Path, output_csv: Path) -> None:
    df = pd.read_csv(compare_csv)
    if "review_required_final" not in df.columns:
        raise ValueError("review_required_final column not found. Run compare_labels.py first.")
    review_df = df[df["review_required_final"].astype(bool)].copy()
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    review_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"review_count={len(review_df)} saved={output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", default="outputs/compare_results/compare_results.csv")
    parser.add_argument("--output", default="outputs/review_lists/review_required.csv")
    args = parser.parse_args()

    make_review_list(Path(args.compare), Path(args.output))


if __name__ == "__main__":
    main()
