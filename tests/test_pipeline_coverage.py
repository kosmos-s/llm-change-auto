from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.pipeline_coverage import pipeline_coverage


class PipelineCoverageTests(unittest.TestCase):
    def _write_openai(self, outputs: Path, rows: list[dict[str, object]]) -> None:
        (outputs / "llm_results").mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(outputs / "llm_results" / "prod_openai.csv", index=False)

    def test_requires_full_fresh_compare_and_review_list_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            (outputs / "compare_results").mkdir(parents=True)
            (outputs / "review_lists").mkdir(parents=True)
            plan = outputs / "work_plan_3000.csv"
            rows = [
                {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1"},
                {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "x2"},
            ]
            pd.DataFrame(rows).to_csv(plan, index=False)
            openai = [
                dict(rows[0], llm_provider="openai", work_mode="production", run_id="r1", processed_at="2026-01-01T00:00:01", response_id="a", error=""),
                dict(rows[1], llm_provider="openai", work_mode="production", run_id="r1", processed_at="2026-01-01T00:00:02", response_id="b", error=""),
            ]
            self._write_openai(outputs, openai)

            partial = pd.DataFrame([
                dict(openai[0], review_required_final=True),
            ])
            partial.to_csv(outputs / "compare_results" / "b_compare.csv", index=False)
            summary = pipeline_coverage(outputs, plan)
            self.assertEqual(summary["compare_count"], 1)
            self.assertEqual(summary["review_decision_count"], 1)
            self.assertEqual(summary["review_list_missing"], 1)
            self.assertFalse(summary["ready"])

            full = pd.DataFrame([
                dict(openai[0], review_required_final=True),
                dict(openai[1], review_required_final=False),
            ])
            full.to_csv(outputs / "compare_results" / "b_compare.csv", index=False)
            pd.DataFrame([dict(full.iloc[0])]).to_csv(outputs / "review_lists" / "b_review.csv", index=False)
            summary = pipeline_coverage(outputs, plan)
            self.assertEqual(summary["compare_count"], 2)
            self.assertEqual(summary["review_decision_count"], 2)
            self.assertEqual(summary["review_required_count"], 1)
            self.assertEqual(summary["review_list_count"], 1)
            self.assertEqual(summary["review_list_missing"], 0)
            self.assertTrue(summary["ready"])

    def test_stale_compare_after_openai_retry_does_not_count(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            (outputs / "compare_results").mkdir(parents=True)
            (outputs / "review_lists").mkdir(parents=True)
            plan = outputs / "work_plan_3000.csv"
            row = {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1"}
            pd.DataFrame([row]).to_csv(plan, index=False)
            latest = dict(row, llm_provider="openai", work_mode="production", run_id="retry", processed_at="2026-01-01T00:00:02", response_id="new", error="")
            self._write_openai(outputs, [latest])
            stale = dict(row, work_mode="production", run_id="first", processed_at="2026-01-01T00:00:01", response_id="old", review_required_final=False)
            pd.DataFrame([stale]).to_csv(outputs / "compare_results" / "b_compare.csv", index=False)
            summary = pipeline_coverage(outputs, plan)
            self.assertEqual(summary["compare_count"], 0)
            self.assertEqual(summary["stale_compare_count"], 1)
            self.assertFalse(summary["ready"])

    def test_test_mode_compare_never_counts_toward_production(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            (outputs / "compare_results").mkdir(parents=True)
            (outputs / "review_lists").mkdir(parents=True)
            plan = outputs / "work_plan_3000.csv"
            row = {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "x1"}
            pd.DataFrame([row]).to_csv(plan, index=False)
            current = dict(row, llm_provider="openai", work_mode="production", run_id="r", processed_at="2026-01-01T00:00:01", response_id="x", error="")
            self._write_openai(outputs, [current])
            pd.DataFrame([dict(current, work_mode="test", review_required_final=True)]).to_csv(
                outputs / "compare_results" / "test_compare.csv", index=False
            )
            summary = pipeline_coverage(outputs, plan)
            self.assertEqual(summary["compare_count"], 0)
            self.assertEqual(summary["review_decision_count"], 0)
            self.assertFalse(summary["ready"])


if __name__ == "__main__":
    unittest.main()
