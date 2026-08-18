"""Dataset folder scanner.

현재 데이터 구조에 맞춰 `*_combined.jpg`만 LLM 입력 대상으로 스캔한다.
같은 이름의 `*_combined.json`, `*_left.jpg`, `*_right.jpg` 경로와 기존 라벨도 함께 읽는다.
`errors` 하위 오류 유형 폴더까지 보존해 동일 image_id 충돌을 방지한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

LABEL_KEYS = [
    "arti",
    "arti_bu",
    "arti_bu_t",
    "arti_binil",
    "arti_road",
    "arti_roa_m",
    "arti_other",
    "tree",
    "fore",
    "farm",
    "water",
]


def ox_to_int(value: Any) -> int:
    """Convert dataset label values such as o/x/1/0 to int."""
    text = str(value).strip().lower()
    if text in {"o", "1", "true", "yes", "y"}:
        return 1
    return 0


def infer_split(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    for split in ("train", "val", "test"):
        if split in parts:
            return split
    return "unknown"


def infer_group(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if "errors" in parts:
        return "errors"
    if "dataset" in parts:
        return "dataset"
    return "unknown"


def infer_relative_folder(path: Path, split: str) -> str:
    """Return folders between split and the image filename.

    Examples:
        dataset/train/file.jpg -> .
        errors/train/farmland_fp_00/file.jpg -> farmland_fp_00
    """
    if split == "unknown":
        return "."

    parts = list(path.parts)
    lower_parts = [part.lower() for part in parts]
    split_indexes = [index for index, part in enumerate(lower_parts) if part == split.lower()]
    if not split_indexes:
        return "."

    split_index = split_indexes[-1]
    folder_parts = parts[split_index + 1 : -1]
    return "/".join(folder_parts) if folder_parts else "."


def infer_error_type(group: str, relative_folder: str) -> str:
    if group != "errors" or not relative_folder or relative_folder == ".":
        return ""
    return relative_folder.split("/")[0]


def read_label_json(json_path: Path) -> dict[str, Any]:
    if not json_path.exists():
        return {}
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(json_path.read_text(encoding="cp949"))


def normalize_labels(label_json: dict[str, Any]) -> dict[str, Any]:
    artifact_detail = label_json.get("artifact_detail", {}) or {}

    original = {
        "arti": ox_to_int(label_json.get("Artifact", "x")),
        "tree": ox_to_int(label_json.get("Tree", "x")),
        "fore": ox_to_int(label_json.get("forest", "x")),
        "farm": ox_to_int(label_json.get("farmland", "x")),
        "water": ox_to_int(label_json.get("water", "x")),
        "arti_bu": ox_to_int(artifact_detail.get("arti_bu", "x")),
        "arti_bu_t": ox_to_int(artifact_detail.get("arti_bu_t", "x")),
        "arti_binil": ox_to_int(artifact_detail.get("arti_binil", "x")),
        "arti_road": ox_to_int(artifact_detail.get("arti_road", "x")),
        "arti_roa_m": ox_to_int(artifact_detail.get("arti_roa_m", "x")),
        "arti_other": ox_to_int(artifact_detail.get("arti_other", "x")),
    }

    labels = {f"original_{key}": value for key, value in original.items()}
    labels["original_change"] = 1 if any(original[key] for key in LABEL_KEYS) else 0
    labels["original_reason"] = str(label_json.get("reason", ""))
    return labels


def make_pair_paths(combined_path: Path) -> tuple[Path, Path, Path]:
    stem = combined_path.stem.replace("_combined", "")
    parent = combined_path.parent
    left_path = parent / f"{stem}_left{combined_path.suffix}"
    right_path = parent / f"{stem}_right{combined_path.suffix}"
    json_path = parent / f"{stem}_combined.json"
    return left_path, right_path, json_path


def scan_dataset(root: Path) -> pd.DataFrame:
    rows = []
    for combined_path in root.rglob("*_combined.jpg"):
        left_path, right_path, json_path = make_pair_paths(combined_path)
        label_json = read_label_json(json_path)
        labels = normalize_labels(label_json)
        split = infer_split(combined_path)
        group = infer_group(combined_path)
        relative_folder = infer_relative_folder(combined_path, split)

        rows.append(
            {
                "image_id": combined_path.stem.replace("_combined", ""),
                "image_name": combined_path.name,
                "image_path": str(combined_path),
                "left_image_path": str(left_path) if left_path.exists() else "",
                "right_image_path": str(right_path) if right_path.exists() else "",
                "json_path": str(json_path) if json_path.exists() else "",
                "split": split,
                "group": group,
                "relative_folder": relative_folder,
                "error_type": infer_error_type(group, relative_folder),
                **labels,
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["group", "split", "relative_folder", "image_name"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="dataset_sample 또는 dataset 루트 경로")
    parser.add_argument("--output", default="outputs/dataset_index.csv")
    args = parser.parse_args()

    root = Path(args.root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not root.exists():
        raise FileNotFoundError(f"Dataset root not found: {root}")

    df = scan_dataset(root)
    df.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"scanned={len(df)} output={output}")


if __name__ == "__main__":
    main()
