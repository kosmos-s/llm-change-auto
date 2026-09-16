from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.production_readiness import preflight_quality_summary


class ProductionReadinessTests(unittest.TestCase):
    def test_blocks_when_quality_errors_exist(self):
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / "index.csv"
            pd.DataFrame([{"image_id": "x"}]).to_csv(index, index=False)
            report = pd.DataFrame([{"severity": "error", "code": "split_leakage"}])
            with patch("src.production_readiness.validate_index", return_value=report), patch("src.production_readiness.summarize_quality", return_value={"errors": 1, "warnings": 0, "total": 1}):
                summary = preflight_quality_summary(index, None)
            self.assertFalse(summary["ready"])
            self.assertEqual(summary["errors"], 1)


if __name__ == "__main__":
    unittest.main()
