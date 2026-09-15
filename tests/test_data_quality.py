"""Regression tests for dataset integrity checks."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_quality import summarize_quality, validate_index


def _make_sample(root: Path, group: str, split: str, image_id: str) -> dict[str, str]:
    folder = root / group / split
    folder.mkdir(parents=True, exist_ok=True)

    combined = folder / f"{image_id}_combined.jpg"
    left = folder / f"{image_id}_left.jpg"
    right = folder / f"{image_id}_right.jpg"
    label = folder / f"{image_id}_combined.json"

    for path in [combined, left, right]:
        path.write_bytes(b"test")
    label.write_text(
        json.dumps({"Artifact": "x", "artifact_detail": {}}, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "image_id": image_id,
        "group": group,
        "split": split,
        "relative_folder": ".",
        "image_path": str(combined),
        "left_image_path": str(left),
        "right_image_path": str(right),
        "json_path": str(label),
    }


class DataQualityTest(unittest.TestCase):
    def test_cross_group_different_splits_is_warning_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [
                _make_sample(root, "dataset", "test", "sample_001"),
                _make_sample(root, "errors", "train", "sample_001"),
            ]
            index_csv = root / "dataset_index.csv"
            pd.DataFrame(rows).to_csv(index_csv, index=False)

            report = validate_index(index_csv)
            summary = summarize_quality(report)

            self.assertEqual(summary["errors"], 0)
            self.assertEqual(summary["warnings"], 1)
            self.assertEqual(report.iloc[0]["code"], "cross_group_split_overlap")
            self.assertIn("dataset=test", report.iloc[0]["detail"])
            self.assertIn("errors=train", report.iloc[0]["detail"])

    def test_same_group_multiple_splits_is_blocking_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [
                _make_sample(root, "errors", "test", "sample_002"),
                _make_sample(root, "errors", "train", "sample_002"),
            ]
            index_csv = root / "dataset_index.csv"
            pd.DataFrame(rows).to_csv(index_csv, index=False)

            report = validate_index(index_csv)
            summary = summarize_quality(report)

            self.assertEqual(summary["errors"], 1)
            self.assertEqual(report.iloc[0]["code"], "split_leakage")
            self.assertEqual(report.iloc[0]["group"], "errors")
            self.assertIn("test, train", report.iloc[0]["detail"])


if __name__ == "__main__":
    unittest.main()
