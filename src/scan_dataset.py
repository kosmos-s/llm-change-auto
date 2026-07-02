"""Dataset folder scanner.

원본 이미지를 GitHub에 복사하지 않고, 이미지 경로 목록만 CSV로 저장한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


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


def infer_original_label(path: Path) -> str:
    # errors/test/artifact_fn_00 같은 폴더명을 우선 라벨 힌트로 사용
    parent = path.parent.name
    if parent:
        return parent
    return "unknown"


def scan_dataset(root: Path) -> pd.DataFrame:
    rows = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in IMAGE_EXTS:
            continue
        rows.append(
            {
                "image_name": file_path.name,
                "image_path": str(file_path),
                "split": infer_split(file_path),
                "group": infer_group(file_path),
                "original_label": infer_original_label(file_path),
            }
        )
    return pd.DataFrame(rows).sort_values(["group", "split", "image_name"])


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
