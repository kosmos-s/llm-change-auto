"""Build a safe cleaned-dataset snapshot from original data + human-reviewed JSONs.

The exporter does not duplicate aerial images by default. Instead it:
1) builds a manifest for every indexed sample,
2) selects reviewed_json when a human-reviewed version exists,
3) otherwise keeps the original JSON,
4) optionally copies the selected JSON into outputs/clean_dataset while preserving
   dataset/errors, train/val/test, and errors subfolder structure.

This avoids large image duplication and prevents train/val/test leakage.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import pandas as pd


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def reviewed_json_path_for_row(row: pd.Series, reviewed_root: Path) -> Path:
    source = clean_text(row.get("group")) or "unknown"
    split = clean_text(row.get("split")) or "unknown"
    relative_folder = clean_text(row.get("relative_folder")) or "."
    original_json = Path(clean_text(row.get("json_path")))

    target = reviewed_root / source / split
    if relative_folder not in {"", "."}:
        target = target / Path(relative_folder)
    return target / original_json.name


def clean_json_output_path(row: pd.Series, clean_root: Path) -> Path:
    source = clean_text(row.get("group")) or "unknown"
    split = clean_text(row.get("split")) or "unknown"
    relative_folder = clean_text(row.get("relative_folder")) or "."
    original_json = Path(clean_text(row.get("json_path")))

    target = clean_root / source / split
    if relative_folder not in {"", "."}:
        target = target / Path(relative_folder)
    return target / original_json.name


def build_clean_manifest(
    index_csv: Path,
    reviewed_root: Path,
    output_csv: Path,
    clean_root: Path | None = None,
    copy_selected_json: bool = False,
) -> pd.DataFrame:
    if not index_csv.exists():
        raise FileNotFoundError(f"dataset_index.csv를 찾을 수 없습니다: {index_csv}")

    df = pd.read_csv(index_csv)
    required = {"image_id", "group", "split", "image_path", "json_path"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"dataset_index.csv 필수 컬럼이 없습니다: {', '.join(missing)}")

    if clean_root is None:
        clean_root = output_csv.parent

    rows: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        source = clean_text(row.get("group"))
        split = clean_text(row.get("split"))
        relative_folder = clean_text(row.get("relative_folder")) or "."
        error_type = clean_text(row.get("error_type"))
        original_json_path = Path(clean_text(row.get("json_path")))
        reviewed_path = reviewed_json_path_for_row(row, reviewed_root)
        reviewed_exists = reviewed_path.exists()

        selected_json_path = reviewed_path if reviewed_exists else original_json_path
        copied_json_path = ""

        if copy_selected_json:
            if not selected_json_path.exists():
                raise FileNotFoundError(f"선택된 JSON을 찾을 수 없습니다: {selected_json_path}")
            target = clean_json_output_path(row, clean_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(selected_json_path, target)
            copied_json_path = str(target)

        rows.append(
            {
                "image_id": clean_text(row.get("image_id")),
                "source": source,
                "split": split,
                "relative_folder": relative_folder,
                "error_type": error_type,
                "image_path": clean_text(row.get("image_path")),
                "left_image_path": clean_text(row.get("left_image_path")),
                "right_image_path": clean_text(row.get("right_image_path")),
                "original_json_path": str(original_json_path),
                "reviewed_json_path": str(reviewed_path) if reviewed_exists else "",
                "effective_json_path": str(selected_json_path),
                "label_source": "reviewed" if reviewed_exists else "original",
                "reviewed": reviewed_exists,
                "clean_json_path": copied_json_path,
            }
        )

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["source", "split", "relative_folder", "image_id"],
            kind="stable",
        ).reset_index(drop=True)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="outputs/dataset_index.csv")
    parser.add_argument("--reviewed-root", default="outputs/reviewed_json")
    parser.add_argument("--output", default="outputs/clean_dataset/clean_dataset_manifest.csv")
    parser.add_argument("--clean-root", default="outputs/clean_dataset")
    parser.add_argument("--copy-json", action="store_true")
    args = parser.parse_args()

    result = build_clean_manifest(
        index_csv=Path(args.index),
        reviewed_root=Path(args.reviewed_root),
        output_csv=Path(args.output),
        clean_root=Path(args.clean_root),
        copy_selected_json=bool(args.copy_json),
    )
    reviewed_count = int(result["reviewed"].sum()) if "reviewed" in result.columns else 0
    print(
        f"rows={len(result)} reviewed={reviewed_count} "
        f"saved={args.output} copy_json={args.copy_json}"
    )


if __name__ == "__main__":
    main()
