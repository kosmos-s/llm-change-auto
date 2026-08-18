"""Tests for clean dataset export manifest selection."""

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

from export_clean_dataset import build_clean_manifest


class ExportCleanDatasetTest(unittest.TestCase):
    def test_reviewed_json_overrides_original_and_keeps_error_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "dataset_sample" / "errors" / "train" / "farmland_fp_00"
            data_dir.mkdir(parents=True)
            original_json = data_dir / "sample_combined.json"
            original_json.write_text(json.dumps({"Artifact": "x"}), encoding="utf-8")

            reviewed_root = root / "outputs" / "reviewed_json"
            reviewed_json = reviewed_root / "errors" / "train" / "farmland_fp_00" / "sample_combined.json"
            reviewed_json.parent.mkdir(parents=True)
            reviewed_json.write_text(json.dumps({"Artifact": "o"}), encoding="utf-8")

            index_csv = root / "outputs" / "dataset_index.csv"
            index_csv.parent.mkdir(parents=True)
            pd.DataFrame([
                {
                    "image_id": "sample",
                    "group": "errors",
                    "split": "train",
                    "relative_folder": "farmland_fp_00",
                    "error_type": "farmland_fp_00",
                    "image_path": str(data_dir / "sample_combined.jpg"),
                    "left_image_path": str(data_dir / "sample_left.jpg"),
                    "right_image_path": str(data_dir / "sample_right.jpg"),
                    "json_path": str(original_json),
                }
            ]).to_csv(index_csv, index=False)

            output_csv = root / "outputs" / "clean_dataset" / "clean_dataset_manifest.csv"
            clean_root = root / "outputs" / "clean_dataset"
            result = build_clean_manifest(
                index_csv=index_csv,
                reviewed_root=reviewed_root,
                output_csv=output_csv,
                clean_root=clean_root,
                copy_selected_json=True,
            )

            self.assertEqual(len(result), 1)
            row = result.iloc[0]
            self.assertEqual(row["label_source"], "reviewed")
            self.assertEqual(row["relative_folder"], "farmland_fp_00")
            self.assertEqual(Path(row["effective_json_path"]), reviewed_json)

            copied = clean_root / "errors" / "train" / "farmland_fp_00" / "sample_combined.json"
            self.assertTrue(copied.exists())
            copied_data = json.loads(copied.read_text(encoding="utf-8"))
            self.assertEqual(copied_data["Artifact"], "o")

    def test_unreviewed_uses_original_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "dataset_sample" / "dataset" / "train"
            data_dir.mkdir(parents=True)
            original_json = data_dir / "sample_combined.json"
            original_json.write_text(json.dumps({"Artifact": "x"}), encoding="utf-8")

            index_csv = root / "outputs" / "dataset_index.csv"
            index_csv.parent.mkdir(parents=True)
            pd.DataFrame([
                {
                    "image_id": "sample",
                    "group": "dataset",
                    "split": "train",
                    "relative_folder": ".",
                    "error_type": "",
                    "image_path": str(data_dir / "sample_combined.jpg"),
                    "left_image_path": str(data_dir / "sample_left.jpg"),
                    "right_image_path": str(data_dir / "sample_right.jpg"),
                    "json_path": str(original_json),
                }
            ]).to_csv(index_csv, index=False)

            result = build_clean_manifest(
                index_csv=index_csv,
                reviewed_root=root / "outputs" / "reviewed_json",
                output_csv=root / "outputs" / "clean_dataset" / "clean_dataset_manifest.csv",
            )

            row = result.iloc[0]
            self.assertEqual(row["label_source"], "original")
            self.assertEqual(Path(row["effective_json_path"]), original_json)


if __name__ == "__main__":
    unittest.main()
