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


if __name__ == "__main__":
    unittest.main()
