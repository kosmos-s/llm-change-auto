"""Load dataset_sample image/json pairs for the Streamlit verifier UI.

지원 구조:
- dataset_sample/dataset/{test,train,val}
- dataset_sample/errors/{test,train,val}
- 2026/dataset/{test,train,val}
- 2026/dataset/errors/{test,train,val}

`source`로 dataset과 errors를 명확히 구분한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


def find_combined_images(root: str | Path, split: str | None = None, source: str | None = "dataset") -> list[SampleItem]:
    """Find image/json pairs under the selected source and split.

    Args:
        root: dataset_sample 또는 2026 같은 데이터 루트 경로.
        split: test, train, val, all 중 하나.
        source: dataset, errors, both 중 하나.
    """
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


def resolve_search_roots(root_path: Path, split: str, source: str) -> list[tuple[Path, str, str]]:
    """Return exact folders to scan as (path, source, split).

    `both`는 dataset과 errors를 각각 분리해서 합친다.
    `all`은 선택한 source 안에서 test/train/val만 합친다.
    """
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
    """Return possible folders for one source/split pair.

    로컬 샘플은 dataset_sample/errors/test 형태일 수 있고,
    NAS 전체 데이터는 2026/dataset/errors/test 형태일 수 있어 둘 다 지원한다.
    """
    candidates: list[Path] = []

    if source == "dataset":
        candidates.extend(
            [
                root_path / "dataset" / split,
                root_path / split,
            ]
        )
    elif source == "errors":
        candidates.extend(
            [
                root_path / "errors" / split,
                root_path / "dataset" / "errors" / split,
                root_path / split,
            ]
        )

    # 사용자가 이미 dataset/test 또는 errors/test 같은 분할 폴더를 넣은 경우
    if root_path.name.lower() == split:
        parent_name = root_path.parent.name.lower()
        grand_parent_name = root_path.parent.parent.name.lower() if root_path.parent.parent else ""
        if source == "dataset" and parent_name == "dataset":
            candidates.append(root_path)
        if source == "errors" and (parent_name == "errors" or grand_parent_name == "errors"):
            candidates.append(root_path)

    # 사용자가 오류 유형 폴더까지 직접 넣은 경우 예: errors/test/artifact_fn_00
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
