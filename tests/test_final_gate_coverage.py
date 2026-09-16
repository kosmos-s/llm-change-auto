from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.production_gate import final_gate_summary
from src.production_integrity import write_plan_metadata


class FinalGateCoverageTests(unittest.TestCase):
    def test_final_gate_blocks_without_compare_and_review_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            for rel in ["llm_results", "compare_results", "review_lists", "reviewed_json", "review_events"]:
                (outputs / rel).mkdir(parents=True, exist_ok=True)
            plan_row = {
                "group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1",
                "image_path": "x.jpg", "json_path": "x.json",
            }
            pd.DataFrame([plan_row]).to_csv(outputs / "work_plan_3000.csv", index=False)
            pd.DataFrame([plan_row]).to_csv(outputs / "dataset_index.csv", index=False)
            write_plan_metadata(outputs / "dataset_index.csv", outputs / "work_plan_3000.csv")

            llm_row = dict(plan_row)
            llm_row.update({"llm_provider": "openai", "work_mode": "production", "error": ""})
            pd.DataFrame([llm_row]).to_csv(outputs / "llm_results" / "prod_openai_x.csv", index=False)
            summary = final_gate_summary(outputs, 1)
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["compare_count"], 0)
            self.assertEqual(summary["review_decision_count"], 0)
            self.assertTrue(summary["plan_binding_ready"])
            self.assertFalse(summary["ready"])


if __name__ == "__main__":
    unittest.main()
