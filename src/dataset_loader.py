"""Load dataset_sample image/json pairs for the Streamlit verifier UI.

`all` 선택 시에는 dataset/train, dataset/val, dataset/test만 합칩니다.
root 전체를 재귀 검색하지 않기 때문에 errors 폴더나 중복 폴더가 섞이지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SampleItem:
    image_id: str
    combined_path: Path
    json_path: Path
    left_path: Path
    right_path: Path
    split: str


def find_combined_images(root: str | Path, split: str | None = None) -> list[SampleItem]:
    root_path = Path(root)
    split = split or "test"

    search_roots = resolve_search_roots(root_path, split)
    items: list[SampleItem] = []

    for search_root in search_roots:
        if not search_root.exists():
            continue
        for combined_path in sorted(search_root.glob("*_combined.jpg")):
            stem = combined_path.stem.replace("_combined", "")
            parent = combined_path.parent
            suffix = combined_path.suffix
            item_split = infer_split(combined_path)
            items.append(
                SampleItem(
                    image_id=stem,
                    combined_path=combined_path,
                    json_path=parent / f"{stem}_combined.json",
                    left_path=parent / f"{stem}_left{suffix}",
                    right_path=parent / f"{stem}_right{suffix}",
                    split=item_split,
                )
            )

    return sorted(items, key=lambda item: (item.split, item.image_id))


def resolve_search_roots(root_path: Path, split: str) -> list[Path]:
    """Return exact folders to scan.

    Expected dataset root examples:
    - dataset_sample
    - dataset_sample/dataset
    - dataset_sample/dataset/test
    """
    if split == "all":
        candidates = []
        for name in ("test", "train", "val"):
            path1 = root_path / "dataset" / name
            path2 = root_path / name
            if path1.exists():
                candidates.append(path1)
            elif path2.exists():
                candidates.append(path2)
        return candidates

    path1 = root_path / "dataset" / split
    path2 = root_path / split
    if path1.exists():
        return [path1]
    if path2.exists():
        return [path2]

    # 사용자가 이미 dataset/test 같은 분할 폴더를 넣은 경우
    if root_path.name.lower() == split:
        return [root_path]

    return []


def infer_split(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    for split in ("train", "val", "test"):
        if split in parts:
            return split
    return "unknown"
