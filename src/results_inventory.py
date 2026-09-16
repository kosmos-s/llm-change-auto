"""Helpers for loading and de-duplicating OpenAI result CSVs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

KEY_COLUMNS = ["group", "split", "relative_folder", "image_id"]


def _clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _normalize_folder(value: Any) -> str:
    text = _clean_text(value).replace("\\", "/").strip("/")
    return text or "."


def deduplicate_result_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest row for each logical sample key inside one dataframe."""
    if df.empty or "image_id" not in df.columns:
        return df.copy()

    result = df.copy()
    for column in KEY_COLUMNS:
        if column not in result.columns:
            result[column] = "." if column == "relative_folder" else ""
    result["relative_folder"] = result["relative_folder"].map(_normalize_folder)

    if "processed_at" in result.columns:
        result["_processed_order"] = pd.to_datetime(result["processed_at"], errors="coerce")
        result["_row_order"] = range(len(result))
        result = result.sort_values(["_processed_order", "_row_order"], na_position="first")
        result = result.drop(columns=["_processed_order", "_row_order"])

    return result.drop_duplicates(KEY_COLUMNS, keep="last").reset_index(drop=True)


def _filter_openai_rows(df: pd.DataFrame, csv_path: Path) -> pd.DataFrame:
    if df.empty:
        return df
    if "llm_provider" in df.columns:
        provider = df["llm_provider"].fillna("").astype(str).str.strip().str.lower()
        explicit = df[provider == "openai"].copy()
        if not explicit.empty:
            return explicit
        if provider.ne("").any():
            return df.iloc[0:0].copy()
    name = csv_path.name.lower()
    if "gemini" in name:
        return df.iloc[0:0].copy()
    if name.startswith("openai_") or name.startswith("prod_openai_") or name.startswith("test_openai_"):
        return df.copy()
    return df.iloc[0:0].copy()


def unique_openai_results(results_dir: Path) -> pd.DataFrame:
    """Load all OpenAI CSVs and return one latest row per logical sample."""
    if not results_dir.exists():
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for csv_path in sorted(results_dir.glob("*.csv")):
        try:
            frame = pd.read_csv(csv_path)
        except Exception:
            continue
        frame = _filter_openai_rows(frame, csv_path)
        if frame.empty or "image_id" not in frame.columns:
            continue
        frame = deduplicate_result_rows(frame)
        frame["_file"] = str(csv_path)
        frame["_mtime"] = csv_path.stat().st_mtime
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True, sort=False)
    for column in KEY_COLUMNS:
        if column not in merged.columns:
            merged[column] = "." if column == "relative_folder" else ""
    merged["relative_folder"] = merged["relative_folder"].map(_normalize_folder)

    sort_columns = ["_mtime"]
    if "processed_at" in merged.columns:
        merged["_processed_order"] = pd.to_datetime(merged["processed_at"], errors="coerce")
        sort_columns.append("_processed_order")
    merged = merged.sort_values(sort_columns, na_position="first")
    merged = merged.drop_duplicates(KEY_COLUMNS, keep="last")
    if "_processed_order" in merged.columns:
        merged = merged.drop(columns=["_processed_order"])
    return merged.reset_index(drop=True)
