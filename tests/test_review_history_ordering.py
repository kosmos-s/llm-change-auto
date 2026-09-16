from pathlib import Path
import os
import tempfile
import unittest

import pandas as pd

from src.build_review_history import load_latest_llm_rows


class ReviewHistoryOrderingTests(unittest.TestCase):
    def test_processed_at_beats_later_file_mtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            newer = root / "prod_openai_new.csv"
            older = root / "prod_openai_old.csv"
            common = {
                "group": "errors",
                "split": "train",
                "relative_folder": "a",
                "image_id": "x1",
                "llm_provider": "openai",
                "work_mode": "production",
            }
            pd.DataFrame([{**common, "processed_at": "2026-01-01T12:00:00", "llm_change": 1}]).to_csv(newer, index=False)
            pd.DataFrame([{**common, "processed_at": "2026-01-01T11:00:00", "llm_change": 0}]).to_csv(older, index=False)
            os.utime(newer, (1000, 1000))
            os.utime(older, (2000, 2000))

            result = load_latest_llm_rows(root)
            self.assertEqual(len(result), 1)
            self.assertEqual(int(result.iloc[0]["llm_change"]), 1)
            self.assertEqual(str(result.iloc[0]["processed_at"]), "2026-01-01T12:00:00")


if __name__ == "__main__":
    unittest.main()
