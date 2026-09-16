from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.production_gate import final_gate_summary
from src.production_integrity import write_plan_metadata


class FinalGateCoverageTests(unittest.TestCase):
    def _prepare(self, outputs: Path) -> dict[str, object]:
        for rel in ["llm_results", "compare_results", "review_lists", "reviewed_json", "review_events"]:
            (outputs / rel).mkdir(parents=True, exist_ok=True)
        plan_row = {
            "group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1",
            "image_path": "x.jpg", "json_path": "x.json",
        }
        pd.DataFrame([plan_row]).to_csv(outputs / "work_plan_3000.csv", index=False)
        pd.DataFrame([plan_row]).to_csv(outputs / "dataset_index.csv", index=False)
        write_plan_metadata(outputs / "dataset_index.csv", outputs / "work_plan_3000.csv")
        llm_row: dict[str, object] = dict(plan_row)
        llm_row.update({
            "llm_provider": "openai", "work_mode": "production", "error": "",
            "run_id": "run_1", "processed_at": "2026-01-01T00:00:01", "response_id": "resp_1",
        })
        pd.DataFrame([llm_row]).to_csv(outputs / "llm_results" / "prod_openai_x.csv", index=False)
        return llm_row

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
            compare.update({"review_required_final": False})
            pd.DataFrame([compare]).to_csv(outputs / "compare_results" / "prod_compare.csv", index=False)
            summary = final_gate_summary(outputs, 1)
            self.assertEqual(summary["compare_count"], 1)
            self.assertEqual(summary["review_decision_count"], 1)
            self.assertEqual(summary["pending_review_count"], 0)
            self.assertTrue(summary["ready"])

    def test_required_candidate_needs_review_list_even_if_reviewed_json_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            row = self._prepare(outputs)
            compare = dict(row)
            compare.update({"review_required_final": True})
            pd.DataFrame([compare]).to_csv(outputs / "compare_results" / "prod_compare.csv", index=False)

            reviewed = outputs / "reviewed_json" / "errors" / "train" / "a" / "x1_combined.json"
            reviewed.parent.mkdir(parents=True, exist_ok=True)
            reviewed.write_text("{}", encoding="utf-8")

            summary = final_gate_summary(outputs, 1)
            self.assertEqual(summary["pending_review_count"], 0)
            self.assertEqual(summary["review_list_missing"], 1)
            self.assertFalse(summary["ready"])

            pd.DataFrame([compare]).to_csv(outputs / "review_lists" / "prod_review.csv", index=False)
            summary = final_gate_summary(outputs, 1)
            self.assertEqual(summary["review_list_missing"], 0)
            self.assertTrue(summary["ready"])

    def test_legacy_openai_row_without_work_mode_does_not_count(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            row = self._prepare(outputs)
            legacy = dict(row)
            legacy.pop("work_mode", None)
            legacy.pop("run_id", None)
            legacy.pop("processed_at", None)
            legacy.pop("response_id", None)
            pd.DataFrame([legacy]).to_csv(outputs / "llm_results" / "prod_openai_x.csv", index=False)
            summary = final_gate_summary(outputs, 1)
            self.assertEqual(summary["success_count"], 0)
            self.assertEqual(summary["missing_success"], 1)
            self.assertFalse(summary["ready"])


if __name__ == "__main__":
    unittest.main()
