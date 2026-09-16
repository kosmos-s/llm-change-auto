from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.compare_labels import compare


class ComparePolicyTests(unittest.TestCase):
    def _run(self, row: dict[str, object]) -> pd.Series:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "llm.csv"
            output = root / "compare.csv"
            pd.DataFrame([row]).to_csv(source, index=False)
            compare(source, output, confidence_threshold=0.70, review_policy="core")
            return pd.read_csv(output).iloc[0]

    def test_detail_mismatch_requires_review_even_when_change_matches(self):
        row = {
            "original_change": 1,
            "llm_change": 1,
            "original_arti": 1,
            "original_arti_bu": 1,
            "arti": 1,
            "arti_bu": 0,
            "arti_road": 1,
            "confidence": 0.95,
            "review_required": False,
            "error": "",
        }
        result = self._run(row)
        self.assertTrue(bool(result["detail_mismatch"]))
        self.assertTrue(bool(result["review_required_final"]))
        self.assertIn("detail_mismatch", str(result["review_reasons"]))

    def test_llm_requested_review_is_respected(self):
        row = {
            "original_change": 0,
            "llm_change": 0,
            "confidence": 0.65,
            "review_required": True,
            "error": "",
        }
        result = self._run(row)
        self.assertTrue(bool(result["review_required_final"]))
        self.assertIn("llm_review_required", str(result["review_reasons"]))


if __name__ == "__main__":
    unittest.main()
