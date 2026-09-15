from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from make_review_list import make_review_list
from run_llm_labeling import filter_dataframe


class BatchSafetyTest(unittest.TestCase):
    def test_start_limit_are_stable_before_review_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviewed = root / "reviewed"
            rows = []
            for i in range(10):
                data_dir = root / "errors" / "train"
                data_dir.mkdir(parents=True, exist_ok=True)
                json_path = data_dir / f"id{i}_combined.json"
                json_path.write_text("{}", encoding="utf-8")
                rows.append(
                    {
                        "image_id": f"id{i}",
                        "group": "errors",
                        "split": "train",
                        "relative_folder": ".",
                        "error_type": "artifact_fp_00",
                        "json_path": str(json_path),
                    }
                )

            # Mark id2 as already reviewed. Batch start=2, limit=3 is id2/id3/id4,
            # so exclusion should leave id3/id4 rather than shifting to id5.
            reviewed_path = reviewed / "errors" / "train" / "id2_combined.json"
            reviewed_path.parent.mkdir(parents=True)
            reviewed_path.write_text("{}", encoding="utf-8")

            result = filter_dataframe(
                pd.DataFrame(rows),
                source="errors",
                split="train",
                start=2,
                limit=3,
                exclude_reviewed_root=reviewed,
            )
            self.assertEqual(result["image_id"].tolist(), ["id3", "id4"])

    def test_review_list_prioritizes_api_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compare = root / "compare.csv"
            output = root / "review.csv"
            pd.DataFrame(
                [
                    {
                        "image_id": "low",
                        "review_required_final": True,
                        "error": "",
                        "label_mismatch": False,
                        "detail_mismatch": False,
                        "low_confidence": True,
                        "review_required": False,
                        "confidence": 0.4,
                    },
                    {
                        "image_id": "api",
                        "review_required_final": True,
                        "error": "timeout",
                        "label_mismatch": False,
                        "detail_mismatch": False,
                        "low_confidence": False,
                        "review_required": False,
                        "confidence": 0.0,
                    },
                ]
            ).to_csv(compare, index=False)
            result = make_review_list(compare, output)
            self.assertEqual(result.iloc[0]["image_id"], "api")
            self.assertGreater(result.iloc[0]["priority_score"], result.iloc[1]["priority_score"])


if __name__ == "__main__":
    unittest.main()
