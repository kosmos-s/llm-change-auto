"""Freeze and validate the exact production sample plan before OpenAI execution."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

KEY_COLUMNS = ["group", "split", "relative_folder", "image_id"]
DEFAULT_SPLIT_COUNTS = {"train": 1000, "val": 1000, "test": 1000}


def _norm_folder(value: object) -> str:
    text = str(value or "").replace("\\", "/").strip().strip("/")
    return text if text and text.lower() != "nan" else "."


def logical_key_frame(df: pd.DataFrame) -> pd.Series:
    copy = df.copy()
    for col in KEY_COLUMNS:
        if col not in copy.columns:
            copy[col] = "." if col == "relative_folder" else ""
    copy["relative_folder"] = copy["relative_folder"].map(_norm_folder)
    return (
        copy["group"].fillna("").astype(str).str.lower().str.strip()
        + "|" + copy["split"].fillna("").astype(str).str.lower().str.strip()
        + "|" + copy["relative_folder"].fillna(".").astype(str).str.lower().str.strip()
        + "|" + copy["image_id"].fillna("").astype(str).str.strip()
    )


def dataframe_sha256(df: pd.DataFrame) -> str:
    payload = df.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_work_plan(
    index_csv: Path,
    output_csv: Path,
    *,
    source: str = "errors",
    split_counts: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Create a deterministic frozen plan using index order for each split."""
    split_counts = split_counts or DEFAULT_SPLIT_COUNTS
    index = pd.read_csv(index_csv)
    if "group" not in index.columns or "split" not in index.columns or "image_id" not in index.columns:
        raise ValueError("dataset_index.csv에 group/split/image_id가 필요합니다.")

    selected: list[pd.DataFrame] = []
    for split, count in split_counts.items():
        part = index[
            (index["group"].fillna("").astype(str).str.lower() == source.lower())
            & (index["split"].fillna("").astype(str).str.lower() == split.lower())
        ].copy()
        part = part.reset_index(drop=True)
        if len(part) < int(count):
            raise ValueError(f"{source}/{split} 샘플이 부족합니다: 필요 {count}, 실제 {len(part)}")
        part = part.head(int(count)).copy()
        part["plan_order"] = range(sum(split_counts[s] for s in split_counts if list(split_counts).index(s) < list(split_counts).index(split)) + 1, sum(split_counts[s] for s in split_counts if list(split_counts).index(s) <= list(split_counts).index(split)) + 1)
        selected.append(part)

    plan = pd.concat(selected, ignore_index=True, sort=False)
    plan["relative_folder"] = plan.get("relative_folder", ".").map(_norm_folder)
    plan["logical_key"] = logical_key_frame(plan)
    duplicate = plan["logical_key"].duplicated(keep=False)
    if duplicate.any():
        examples = plan.loc[duplicate, "logical_key"].head(10).tolist()
        raise ValueError(f"work plan 내부 logical key 중복이 있습니다: {examples}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return plan


def load_work_plan(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError("work plan이 비어 있습니다.")
    if "logical_key" not in frame.columns:
        frame["logical_key"] = logical_key_frame(frame)
    if frame["logical_key"].duplicated().any():
        raise ValueError("work plan logical key 중복이 있습니다.")
    return frame


def split_plan(path: Path, split: str) -> pd.DataFrame:
    frame = load_work_plan(path)
    return frame[frame["split"].fillna("").astype(str).str.lower() == split.lower()].copy().reset_index(drop=True)
