from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backup_outputs import create_outputs_backup
from evaluate_results import evaluate_history_dataframe
from model_metrics import compare_metrics, load_metrics_file
from project_paths import dataset_root_default, openai_target_total
from quality_actions import build_quality_action_plan
from results_inventory import deduplicate_result_rows, unique_openai_results


class ProductionSafetyTest(unittest.TestCase):
    def test_deduplicate_result_rows_keeps_latest(self) -> None:
        frame = pd.DataFrame([
            {"group": "errors", "split": "train", "relative_folder": "artifact_fp_00", "image_id": "x", "processed_at": "2026-01-01T10:00:00", "llm_change": 0},
            {"group": "errors", "split": "train", "relative_folder": "artifact_fp_00", "image_id": "x", "processed_at": "2026-01-01T11:00:00", "llm_change": 1},
        ])
        result = deduplicate_result_rows(frame)
        self.assertEqual(len(result), 1)
        self.assertEqual(int(result.iloc[0]["llm_change"]), 1)

    def test_explicit_test_runs_do_not_count_as_production(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp)
            pd.DataFrame([
                {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "test_1", "llm_provider": "openai", "work_mode": "test"},
            ]).to_csv(results_dir / "test_openai_errors_train_00000_00000.csv", index=False)
            pd.DataFrame([
                {"group": "errors", "split": "train", "relative_folder": "a", "image_id": "prod_1", "llm_provider": "openai", "work_mode": "production"},
            ]).to_csv(results_dir / "prod_openai_errors_train_00000_00000.csv", index=False)
            result = unique_openai_results(results_dir)
            self.assertEqual(result["image_id"].astype(str).tolist(), ["prod_1"])

    def test_human_evaluation_uses_human_truth(self) -> None:
        frame = pd.DataFrame([
            {
                "human_change": 1, "llm_change": 1, "llm_error": "",
                **{f"human_{key}": 0 for key in ["arti", "arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other", "tree", "fore", "farm", "water"]},
                **{f"llm_{key}": 0 for key in ["arti", "arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other", "tree", "fore", "farm", "water"]},
            }
        ])
        result = evaluate_history_dataframe(frame)
        self.assertEqual(result["tp"], 1)
        self.assertEqual(result["f2"], 1.0)

    def test_quality_action_plan_marks_split_leakage_blocking(self) -> None:
        report = pd.DataFrame([{"severity": "error", "code": "split_leakage", "group": "dataset", "image_id": "x", "detail": "test, train", "path": ""}])
        plan = build_quality_action_plan(report)
        self.assertEqual(plan.iloc[0]["priority"], "blocking")

    def test_backup_outputs_creates_zip_and_prunes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outputs = Path(tmp) / "outputs"
            (outputs / "llm_results").mkdir(parents=True)
            (outputs / "llm_results" / "a.csv").write_text("x\n1\n", encoding="utf-8")
            result = create_outputs_backup(outputs, keep_count=1)
            self.assertTrue(Path(result["path"]).exists())
            self.assertGreaterEqual(int(result["file_count"]), 1)

    def test_model_metrics_json_and_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics.json"
            path.write_text(json.dumps({"precision": 0.8, "recall": 0.9, "f1": 0.85, "f2": 0.88}), encoding="utf-8")
            before = load_metrics_file(path)
            after = {**before, "f2": 0.90}
            comparison = compare_metrics(before, after)
            delta = float(comparison[comparison["metric"] == "f2"].iloc[0]["delta"])
            self.assertAlmostEqual(delta, 0.02)

    def test_environment_defaults(self) -> None:
        with patch.dict(os.environ, {"DATASET_ROOT": "D:/sample", "OPENAI_TARGET_TOTAL": "3000"}, clear=False):
            self.assertEqual(dataset_root_default(), Path("D:/sample"))
            self.assertEqual(openai_target_total(), 3000)


if __name__ == "__main__":
    unittest.main()
