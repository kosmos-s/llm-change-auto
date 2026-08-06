"""Tests for LLM result analysis metrics."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evaluate_results import evaluate_dataframe


class EvaluateResultsTest(unittest.TestCase):
    def test_binary_metrics_and_api_error_filter(self) -> None:
        df = pd.DataFrame(
            [
                {"original_change": 1, "llm_change": 1, "error": ""},
                {"original_change": 1, "llm_change": 0, "error": ""},
                {"original_change": 0, "llm_change": 1, "error": ""},
                {"original_change": 0, "llm_change": 0, "error": ""},
                {"original_change": 1, "llm_change": 0, "error": "api failed"},
            ]
        )
        for key in [
            "arti",
            "arti_bu",
            "arti_bu_t",
            "arti_binil",
            "arti_road",
            "arti_roa_m",
            "arti_other",
            "tree",
            "fore",
            "farm",
            "water",
        ]:
            df[f"original_{key}"] = 0
            df[key] = 0

        result = evaluate_dataframe(df)

        self.assertEqual(result["total_rows"], 5)
        self.assertEqual(result["valid_rows"], 4)
        self.assertEqual(result["api_errors"], 1)
        self.assertEqual(result["tp"], 1)
        self.assertEqual(result["tn"], 1)
        self.assertEqual(result["fp"], 1)
        self.assertEqual(result["fn"], 1)
        self.assertAlmostEqual(result["change_accuracy"], 0.5)
        self.assertAlmostEqual(result["precision"], 0.5)
        self.assertAlmostEqual(result["recall"], 0.5)
        self.assertAlmostEqual(result["f1"], 0.5)
        self.assertAlmostEqual(result["f2"], 0.5)


if __name__ == "__main__":
    unittest.main()
