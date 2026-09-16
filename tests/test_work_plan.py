from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from work_plan import build_work_plan, load_work_plan


class WorkPlanTests(unittest.TestCase):
    def test_builds_exact_split_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = []
            for split in ["train", "val", "test"]:
                for i in range(3):
                    rows.append({"group": "errors", "split": split, "relative_folder": "x", "image_id": f"{split}_{i}"})
            index = root / "index.csv"
            plan = root / "plan.csv"
            pd.DataFrame(rows).to_csv(index, index=False)
            result = build_work_plan(index, plan, split_counts={"train": 2, "val": 2, "test": 2})
            self.assertEqual(len(result), 6)
            self.assertEqual(result.groupby("split").size().to_dict(), {"train": 2, "val": 2, "test": 2})
            self.assertEqual(len(load_work_plan(plan)), 6)


if __name__ == "__main__":
    unittest.main()
