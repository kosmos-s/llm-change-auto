from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.pipeline_coverage import pipeline_coverage


class PipelineCoverageTests(unittest.TestCase):
    def test_requires_full_production_compare_and_review_decision_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            (outputs / "compare_results").mkdir(parents=True)
            plan = outputs / "work_plan_3000.csv"
            rows = [
                {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1"},
                {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "x2"},
            ]
            pd.DataFrame(rows).to_csv(plan, index=False)

            partial = pd.DataFrame([dict(rows[0], work_mode="production", review_required_final=True)])
            partial.to_csv(outputs / "compare_results" / "b_compare.csv", index=False)
            summary = pipeline_coverage(outputs, plan)
            self.assertEqual(summary["compare_count"], 1)
            self.assertEqual(summary["review_decision_count"], 1)
            self.assertFalse(summary["ready"])

            full = pd.DataFrame([
                dict(rows[0], work_mode="production", review_required_final=True),
                dict(rows[1], work_mode="production", review_required_final=False),
            ])
            full.to_csv(outputs / "compare_results" / "b_compare.csv", index=False)
            summary = pipeline_coverage(outputs, plan)
            self.assertEqual(summary["compare_count"], 2)
            self.assertEqual(summary["review_decision_count"], 2)
            self.assertTrue(summary["ready"])

    def test_test_mode_compare_never_counts_toward_production(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            (outputs / "compare_results").mkdir(parents=True)
            plan = outputs / "work_plan_3000.csv"
            row = {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1"}
            pd.DataFrame([row]).to_csv(plan, index=False)
            pd.DataFrame([dict(row, work_mode="test", review_required_final=True)]).to_csv(
                outputs / "compare_results" / "test_compare.csv", index=False
            )
            summary = pipeline_coverage(outputs, plan)
            self.assertEqual(summary["compare_count"], 0)
            self.assertEqual(summary["review_decision_count"], 0)
            self.assertFalse(summary["ready"])


if __name__ == "__main__":
    unittest.main()
