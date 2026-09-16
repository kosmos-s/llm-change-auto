from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from production_gate import unresolved_review_items


class ProductionGateTests(unittest.TestCase):
    def test_unreviewed_candidate_blocks_final(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            review_lists = outputs / "review_lists"
            review_lists.mkdir(parents=True)
            pd.DataFrame([{
                "group": "errors",
                "split": "train",
                "relative_folder": "artifact_fp_00",
                "image_id": "sample_1",
                "review_required_final": True,
            }]).to_csv(review_lists / "r.csv", index=False)
            pending = unresolved_review_items(review_lists, outputs / "reviewed_json", outputs / "review_events" / "review_events.csv")
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending.iloc[0]["review_state"], "unreviewed")

    def test_test_mode_review_list_does_not_block_frozen_production_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            review_lists = outputs / "review_lists"
            review_lists.mkdir(parents=True)
            plan = outputs / "work_plan_3000.csv"
            pd.DataFrame([{
                "group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1",
            }]).to_csv(plan, index=False)
            pd.DataFrame([{
                "group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1",
                "review_required_final": True, "work_mode": "test",
            }]).to_csv(review_lists / "test_review.csv", index=False)
            pending = unresolved_review_items(
                review_lists, outputs / "reviewed_json", outputs / "review_events" / "review_events.csv", plan
            )
            self.assertTrue(pending.empty)


if __name__ == "__main__":
    unittest.main()
