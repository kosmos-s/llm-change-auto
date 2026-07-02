"""Summarize dataset, LLM, or comparison CSV files."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def print_count_table(df: pd.DataFrame, columns: list[str], title: str) -> None:
    existing = [col for col in columns if col in df.columns]
    if not existing:
        return
    print(f"\n[{title}]")
    print(df.groupby(existing, dropna=False).size().reset_index(name="count").to_string(index=False))


def summarize(csv_path: Path) -> None:
    df = pd.read_csv(csv_path)
    print(f"file={csv_path}")
    print(f"rows={len(df)} columns={len(df.columns)}")

    print_count_table(df, ["group", "split"], "group/split count")
    print_count_table(df, ["review_required_final"], "review required count")
    print_count_table(df, ["review_reasons"], "review reason count")
    print_count_table(df, ["error"], "LLM error count")

    if "confidence" in df.columns:
        conf = pd.to_numeric(df["confidence"], errors="coerce")
        print("\n[confidence]")
        print(conf.describe().to_string())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="요약할 CSV 경로")
    args = parser.parse_args()
    summarize(Path(args.csv))


if __name__ == "__main__":
    main()
