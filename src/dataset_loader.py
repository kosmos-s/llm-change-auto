"""Load image/json pairs for the Streamlit verifier UI.

지원 구조:
- dataset_sample/dataset/{test,train,val}
- dataset_sample/errors/{test,train,val}
- 2026/dataset/{test,train,val}
- 2026/dataset/errors/{test,train,val}
- outputs/review_lists/*.csv

`source`로 dataset과 errors를 명확히 구분한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

SPLITS = ("test", "train", "val")
SOURCES = ("dataset", "errors")


@dataclass(frozen=True)
class SampleItem:
    image_id: str
    combined_path: Path
    json_path: Path
    left_path: Path
    right_path: Path
    split: str
    source: str
    relative_folder: str = "."
    error_type: str = ""
    llm_info: dict[str, Any] = field(default_factory=dict)


def find_combined_images(root: str | Path, split: str | None = None, source: str | None = "dataset") -> list[SampleItem]:
    root_path = Path(root)
    split = split or "test"
    source = source or "dataset"
    search_roots = resolve_search_roots(root_path, split, source)
    items: list[SampleItem] = []
    for search_root, source_name, split_name in search_roots:
        if not search_root.exists():
            continue
        for combined_path in sorted(search_root.rglob("*_combined.jpg")):
            stem = combined_path.stem.replace("_combined", "")
            parent = combined_path.parent
            suffix = combined_path.suffix
            relative_folder = get_relative_folder(parent, search_root)
            error_type = infer_error_type(relative_folder) if source_name == "errors" else ""
            items.append(
                SampleItem(
                    image_id=stem,
                    combined_path=combined_path,
                    json_path=parent / f"{stem}_combined.json",
                    left_path=parent / f"{stem}_left{suffix}",
                    right_path=parent / f"{stem}_right{suffix}",
                    split=split_name,
                    source=source_name,
                    relative_folder=relative_folder,
                    error_type=error_type,
                )
            )
    return sorted(items, key=lambda item: (item.source, item.split, item.relative_folder, item.image_id))


def _local_paths(dataset_root: Path, source: str, split: str, relative_folder: str, image_id: str) -> tuple[Path, Path, Path, Path]:
    base = dataset_root / source / split
    if relative_folder and relative_folder != ".":
        base = base / Path(relative_folder)
    combined = base / f"{image_id}_combined.jpg"
    return (
        combined,
        base / f"{image_id}_combined.json",
        base / f"{image_id}_left.jpg",
        base / f"{image_id}_right.jpg",
    )


def find_items_from_review_csv(csv_path: str | Path, dataset_root: str | Path | None = None) -> list[SampleItem]:
    """Load review rows and remap stale absolute paths to the current PC when needed."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
    df = pd.read_csv(csv_path)
    if "image_path" not in df.columns:
        raise ValueError("review_list CSV에는 image_path 컬럼이 필요합니다.")
    local_root = Path(dataset_root) if dataset_root else None

    items: list[SampleItem] = []
    for row_index, row in df.reset_index(drop=True).iterrows():
        image_path_text = clean_value(row.get("image_path"))
        image_path = Path(image_path_text) if image_path_text else Path()
        image_id = clean_value(row.get("image_id")) or (image_path.stem.replace("_combined", "") if image_path_text else "")
        if not image_id:
            continue
        split = clean_value(row.get("split")) or (infer_split(image_path) if image_path_text else "unknown")
        source = clean_value(row.get("group")) or clean_value(row.get("source")) or (infer_source(image_path) if image_path_text else "unknown")
        if source not in SOURCES:
            source = "errors" if image_path_text and "errors" in [part.lower() for part in image_path.parts] else "dataset"
        relative_folder = clean_value(row.get("relative_folder")) or (infer_relative_folder_from_path(image_path, split, source) if image_path_text else ".")
        relative_folder = relative_folder or "."

        suffix = image_path.suffix or ".jpg"
        parent = image_path.parent if image_path_text else Path()
        stem = image_path.stem.replace("_combined", "") if image_path_text else image_id
        json_path_text = clean_value(row.get("json_path"))
        left_path_text = clean_value(row.get("left_image_path"))
        right_path_text = clean_value(row.get("right_image_path"))
        json_path = Path(json_path_text) if json_path_text else parent / f"{stem}_combined.json"
        left_path = Path(left_path_text) if left_path_text else parent / f"{stem}_left{suffix}"
        right_path = Path(right_path_text) if right_path_text else parent / f"{stem}_right{suffix}"

        # Review CSVs may have been produced on another PC. If the sender's absolute
        # paths do not exist locally, reconstruct them from DATASET_ROOT + logical key.
        if local_root is not None and (not image_path_text or not image_path.exists()):
            local_combined, local_json, local_left, local_right = _local_paths(
                local_root, source, split, relative_folder, image_id
            )
            image_path, json_path, left_path, right_path = local_combined, local_json, local_left, local_right

        error_type = clean_value(row.get("error_type")) or (infer_error_type(relative_folder) if source == "errors" else "")
        llm_info = row_to_llm_info(row.to_dict(), row_index=row_index, csv_path=csv_path)
        items.append(
            SampleItem(
                image_id=image_id,
                combined_path=image_path,
                json_path=json_path,
                left_path=left_path,
                right_path=right_path,
                split=split,
                source=source,
                relative_folder=relative_folder,
                error_type=error_type,
                llm_info=llm_info,
            )
        )
    return items


def row_to_llm_info(row: dict[str, Any], row_index: int, csv_path: Path) -> dict[str, Any]:
    interesting_keys = [
        "llm_change", "llm_class", "confidence", "review_required", "review_required_final",
        "review_reasons", "label_mismatch", "detail_mismatch", "detail_mismatch_keys",
        "low_confidence", "empty_class_when_change", "priority_score", "reason_ko", "reason_en",
        "raw_response", "error", "llm_provider", "llm_model", "prompt_path", "batch_id", "run_id",
        "work_mode", "attempt_count", "input_tokens", "output_tokens", "total_tokens",
        "estimated_cost_usd", "processed_at", "original_change", "original_reason",
        "original_arti", "original_arti_bu", "original_arti_bu_t", "original_arti_binil",
        "original_arti_road", "original_arti_roa_m", "original_arti_other", "original_tree",
        "original_fore", "original_farm", "original_water", "arti", "arti_bu", "arti_bu_t",
        "arti_binil", "arti_road", "arti_roa_m", "arti_other", "tree", "fore", "farm", "water",
    ]
    info = {"review_csv": str(csv_path), "review_csv_row": row_index + 1}
    for key in interesting_keys:
        value = clean_value(row.get(key))
        if value != "":
            info[key] = value
    return info


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def infer_relative_folder_from_path(path: Path, split: str, source: str) -> str:
    parts = list(path.parts)
    lower_parts = [part.lower() for part in parts]
    try:
        if source == "errors" and "errors" in lower_parts and split in lower_parts:
            start = lower_parts.index(split) + 1
            rel_parts = parts[start:-1]
            return "/".join(rel_parts) if rel_parts else "."
        if source == "dataset" and split in lower_parts:
            start = lower_parts.index(split) + 1
            rel_parts = parts[start:-1]
            return "/".join(rel_parts) if rel_parts else "."
    except Exception:
        pass
    return "."


def resolve_search_roots(root_path: Path, split: str, source: str) -> list[tuple[Path, str, str]]:
    source_names = list(SOURCES) if source == "both" else [source]
    split_names = list(SPLITS) if split == "all" else [split]
    results: list[tuple[Path, str, str]] = []
    seen: set[Path] = set()
    for source_name in source_names:
        if source_name not in SOURCES:
            continue
        for split_name in split_names:
            if split_name not in SPLITS:
                continue
            for path in candidate_split_paths(root_path, source_name, split_name):
                resolved = path.resolve()
                if path.exists() and resolved not in seen:
                    results.append((path, source_name, split_name))
                    seen.add(resolved)
    return results


def candidate_split_paths(root_path: Path, source: str, split: str) -> list[Path]:
    candidates: list[Path] = []
    if source == "dataset":
        candidates.extend([root_path / "dataset" / split, root_path / split])
    elif source == "errors":
        candidates.extend([root_path / "errors" / split, root_path / "dataset" / "errors" / split, root_path / split])

    if root_path.name.lower() == split:
        parent_name = root_path.parent.name.lower()
        grand_parent_name = root_path.parent.parent.name.lower() if root_path.parent.parent else ""
        if source == "dataset" and parent_name == "dataset":
            candidates.append(root_path)
        if source == "errors" and (parent_name == "errors" or grand_parent_name == "errors"):
            candidates.append(root_path)

    if source == "errors" and split in [part.lower() for part in root_path.parts] and "errors" in [part.lower() for part in root_path.parts]:
        candidates.append(root_path)
    return candidates


def get_relative_folder(parent: Path, search_root: Path) -> str:
    try:
        rel = parent.relative_to(search_root)
    except ValueError:
        return "."
    text = rel.as_posix()
    return text if text != "." else "."


def infer_error_type(relative_folder: str) -> str:
    if not relative_folder or relative_folder == ".":
        return ""
    return relative_folder.split("/")[0]


def infer_split(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    for split in SPLITS:
        if split in parts:
            return split
    return "unknown"


def infer_source(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if "errors" in parts:
        return "errors"
    if "dataset" in parts:
        return "dataset"
    return "unknown"
