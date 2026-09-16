from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from production_integrity import write_plan_metadata
from team_review_exchange import export_review_package, merge_review_package, preview_review_package


class TeamReviewExchangeTests(unittest.TestCase):
    def _prepare(self, root: Path, local_prefix: str) -> None:
        row = {
            "group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1",
            "image_path": f"{local_prefix}/x.jpg", "left_image_path": f"{local_prefix}/x_left.jpg",
            "right_image_path": f"{local_prefix}/x_right.jpg", "json_path": f"{local_prefix}/x.json",
            "original_change": 1,
        }
        pd.DataFrame([row]).to_csv(root / "dataset_index.csv", index=False)
        pd.DataFrame([row]).to_csv(root / "work_plan_3000.csv", index=False)
        write_plan_metadata(root / "dataset_index.csv", root / "work_plan_3000.csv")

    def test_export_preview_and_merge_allow_same_logical_plan_on_different_pc_paths(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            source = Path(a)
            target = Path(b)
            self._prepare(source, "C:/Users/A/dataset")
            self._prepare(target, "D:/team/dataset")

            reviewed = source / "reviewed_json" / "errors" / "train" / "a" / "x1_combined.json"
            reviewed.parent.mkdir(parents=True)
            reviewed.write_text('{"Artifact":"o","artifact_detail":{}}', encoding="utf-8")

            package = export_review_package(source, "tester")
            preview = preview_review_package(package, target)
            self.assertTrue(preview["compatible"])
            self.assertEqual(preview["items"][0]["state"], "new")
            result = merge_review_package(package, target)
            self.assertEqual(result["new"], 1)
            self.assertEqual(result["written"], 1)
            self.assertTrue((target / "reviewed_json" / "errors" / "train" / "a" / "x1_combined.json").exists())

    def test_different_work_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            source = Path(a)
            target = Path(b)
            self._prepare(source, "C:/Users/A/dataset")
            self._prepare(target, "D:/team/dataset")
            changed = pd.read_csv(target / "work_plan_3000.csv")
            changed.loc[0, "image_id"] = "different"
            changed.to_csv(target / "work_plan_3000.csv", index=False)

            package = export_review_package(source, "tester")
            preview = preview_review_package(package, target)
            self.assertFalse(preview["compatible"])
            with self.assertRaises(ValueError):
                merge_review_package(package, target)


if __name__ == "__main__":
    unittest.main()
