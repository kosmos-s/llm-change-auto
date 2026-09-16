from pathlib import Path
import os
import sys
import tempfile
import unittest

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dataset_loader import find_items_from_review_csv


class ReviewCsvPortabilityTests(unittest.TestCase):
    def _write_review_csv(self, root: Path) -> Path:
        csv_path = root / "review.csv"
        pd.DataFrame([{
            "group": "errors",
            "split": "train",
            "relative_folder": "artifact_fp_00",
            "image_id": "sample_1",
            "image_path": "C:/sender/old/sample_1_combined.jpg",
            "json_path": "C:/sender/old/sample_1_combined.json",
            "left_image_path": "C:/sender/old/sample_1_left.jpg",
            "right_image_path": "C:/sender/old/sample_1_right.jpg",
        }]).to_csv(csv_path, index=False)
        return csv_path

    def _write_sample(self, local_dir: Path) -> None:
        local_dir.mkdir(parents=True)
        for suffix in ["combined.jpg", "left.jpg", "right.jpg", "combined.json"]:
            (local_dir / f"sample_1_{suffix}").write_bytes(b"{}" if suffix.endswith("json") else b"jpg")

    def test_stale_sender_paths_remap_to_local_dataset_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local_dir = root / "dataset_sample" / "errors" / "train" / "artifact_fp_00"
            self._write_sample(local_dir)
            csv_path = self._write_review_csv(root)

            previous = os.environ.get("DATASET_ROOT")
            os.environ["DATASET_ROOT"] = str(root / "dataset_sample")
            try:
                items = find_items_from_review_csv(csv_path)
            finally:
                if previous is None:
                    os.environ.pop("DATASET_ROOT", None)
                else:
                    os.environ["DATASET_ROOT"] = previous

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].combined_path, local_dir / "sample_1_combined.jpg")
            self.assertEqual(items[0].json_path, local_dir / "sample_1_combined.json")

    def test_nested_dataset_errors_layout_is_also_remapped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset_root = root / "2026"
            local_dir = dataset_root / "dataset" / "errors" / "train" / "artifact_fp_00"
            self._write_sample(local_dir)
            csv_path = self._write_review_csv(root)

            items = find_items_from_review_csv(csv_path, dataset_root=dataset_root)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].combined_path, local_dir / "sample_1_combined.jpg")
            self.assertEqual(items[0].json_path, local_dir / "sample_1_combined.json")


if __name__ == "__main__":
    unittest.main()
