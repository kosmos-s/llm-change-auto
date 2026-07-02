"""Load dataset_sample image/json pairs for the Streamlit verifier UI."""

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
    if split and split != "all":
        search_root = root_path / "dataset" / split
        if not search_root.exists():
            search_root = root_path / split
    else:
        search_root = root_path

    items: list[SampleItem] = []
    for combined_path in sorted(search_root.rglob("*_combined.jpg")):
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
    return items


def infer_split(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    for split in ("train", "val", "test"):
        if split in parts:
            return split
    return "unknown"
