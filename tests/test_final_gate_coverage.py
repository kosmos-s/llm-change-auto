from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.production_gate import final_gate_summary
from src.production_integrity import write_plan_metadata


class FinalGateCoverageTests(unittest.TestCase):
    def _prepare(self, outputs: Path) -> dict[str, str]:
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
        return plan_row

    def test_final_gate_blocks_without_compare_and_review_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            self._prepare(outputs)
            summary = final_gate_summary(outputs, 1)
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["compare_count"], 0)
            self.assertEqual(summary["review_decision_count"], 0)
            self.assertTrue(summary["plan_binding_ready"])
            self.assertFalse(summary["ready"])

    def test_final_gate_accepts_complete_no_review_required_sample(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            row = self._prepare(outputs)
            compare = dict(row)
            compare.update({"work_mode": "production", "review_required_final": False})
            pd.DataFrame([compare]).to_csv(outputs / "compare_results" / "prod_compare.csv", index=False)
            summary = final_gate_summary(outputs, 1)
            self.assertEqual(summary["compare_count"], 1)
            self.assertEqual(summary["review_decision_count"], 1)
            self.assertEqual(summary["pending_review_count"], 0)
            self.assertTrue(summary["ready"])

    def test_legacy_openai_row_without_work_mode_does_not_count(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            row = self._prepare(outputs)
            legacy = dict(row)
            legacy.update({"llm_provider": "openai", "error": ""})
            pd.DataFrame([legacy]).to_csv(outputs / "llm_results" / "prod_openai_x.csv", index=False)
            summary = final_gate_summary(outputs, 1)
            self.assertEqual(summary["success_count"], 0)
            self.assertEqual(summary["missing_success"], 1)
            self.assertFalse(summary["ready"])


if __name__ == "__main__":
    unittest.main()
