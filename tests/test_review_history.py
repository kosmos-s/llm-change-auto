"""Tests for review-history matching and OpenAI-only result selection."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from build_review_history import build_review_history


EMPTY_DETAIL = {
    "arti_bu": "x",
    "arti_bu_t": "x",
    "arti_binil": "x",
    "arti_road": "x",
    "arti_roa_m": "x",
    "arti_other": "x",
}


def write_review_json(path: Path, *, artifact: str = "x", farmland: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "Artifact": artifact,
        "Tree": "x",
        "forest": "x",
        "farmland": farmland,
        "water": "x",
        "reason": "reviewed",
        "reason_ko": "검수 완료",
        "artifact_detail": dict(EMPTY_DETAIL),
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class ReviewHistoryTest(unittest.TestCase):
    def test_duplicate_image_id_is_matched_by_relative_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index_path = root / "dataset_index.csv"
            reviewed_root = root / "reviewed_json"
            llm_dir = root / "llm_results"
            output_path = root / "review_history.csv"
            llm_dir.mkdir(parents=True)

            image_id = "00_336062011_0044_0"
            artifact_image = root / "dataset_sample" / "errors" / "train" / "artifact_fp_00" / f"{image_id}_combined.jpg"
            farmland_image = root / "dataset_sample" / "errors" / "train" / "farmland_fp_00" / f"{image_id}_combined.jpg"

            index_df = pd.DataFrame(
                [
                    {
                        "image_id": image_id,
                        "group": "errors",
                        "split": "train",
                        "relative_folder": "artifact_fp_00",
                        "image_path": str(artifact_image),
                        "json_path": str(artifact_image.with_suffix(".json")),
                        "original_change": 0,
                    },
                    {
                        "image_id": image_id,
                        "group": "errors",
                        "split": "train",
                        "relative_folder": "farmland_fp_00",
                        "image_path": str(farmland_image),
                        "json_path": str(farmland_image.with_suffix(".json")),
                        "original_change": 1,
                        "original_farm": 1,
                    },
                ]
            ).fillna(0)
            index_df.to_csv(index_path, index=False, encoding="utf-8-sig")

            llm_df = pd.DataFrame(
                [
                    {
                        "image_id": image_id,
                        "group": "errors",
                        "split": "train",
                        "image_path": str(artifact_image),
                        "llm_provider": "openai",
                        "llm_change": 0,
                        "confidence": 0.8,
                    },
                    {
                        "image_id": image_id,
                        "group": "errors",
                        "split": "train",
                        "image_path": str(farmland_image),
                        "llm_provider": "openai",
                        "llm_change": 1,
                        "farm": 1,
                        "confidence": 0.9,
                    },
                ]
            ).fillna(0)
            llm_df.to_csv(llm_dir / "openai_errors_train_2.csv", index=False, encoding="utf-8-sig")

            artifact_review = reviewed_root / "errors" / "train" / "artifact_fp_00" / f"{image_id}_combined.json"
            farmland_review = reviewed_root / "errors" / "train" / "farmland_fp_00" / f"{image_id}_combined.json"
            write_review_json(artifact_review)
            write_review_json(farmland_review, farmland="o")

            result = build_review_history(
                index_csv=index_path,
                reviewed_root=reviewed_root,
                llm_results_dir=llm_dir,
                output_csv=output_path,
            ).sort_values("relative_folder").reset_index(drop=True)

            self.assertEqual(len(result), 2)

            artifact_row = result[result["relative_folder"] == "artifact_fp_00"].iloc[0]
            farmland_row = result[result["relative_folder"] == "farmland_fp_00"].iloc[0]

            self.assertIn("artifact_fp_00", artifact_row["image_path"])
            self.assertEqual(int(artifact_row["llm_change"]), 0)
            self.assertEqual(int(artifact_row["human_change"]), 0)

            self.assertIn("farmland_fp_00", farmland_row["image_path"])
            self.assertEqual(int(farmland_row["llm_change"]), 1)
            self.assertEqual(int(farmland_row["human_change"]), 1)

    def test_gemini_result_is_ignored_when_openai_result_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            index_path = root / "dataset_index.csv"
            reviewed_root = root / "reviewed_json"
            llm_dir = root / "llm_results"
            output_path = root / "review_history.csv"
            llm_dir.mkdir(parents=True)

            image_id = "00_1234"
            image_path = root / "dataset_sample" / "dataset" / "train" / f"{image_id}_combined.jpg"
            pd.DataFrame(
                [
                    {
                        "image_id": image_id,
                        "group": "dataset",
                        "split": "train",
                        "relative_folder": ".",
                        "image_path": str(image_path),
                        "json_path": str(image_path.with_suffix(".json")),
                        "original_change": 0,
                    }
                ]
            ).to_csv(index_path, index=False, encoding="utf-8-sig")

            pd.DataFrame(
                [
                    {
                        "image_id": image_id,
                        "group": "dataset",
                        "split": "train",
                        "image_path": str(image_path),
                        "llm_provider": "openai",
                        "llm_change": 0,
                        "confidence": 0.9,
                    }
                ]
            ).to_csv(llm_dir / "openai_dataset_train_1.csv", index=False, encoding="utf-8-sig")

            pd.DataFrame(
                [
                    {
                        "image_id": image_id,
                        "group": "dataset",
                        "split": "train",
                        "image_path": str(image_path),
                        "llm_provider": "gemini",
                        "llm_change": 1,
                        "confidence": 0.99,
                    }
                ]
            ).to_csv(llm_dir / "gemini_dataset_train_1.csv", index=False, encoding="utf-8-sig")

            write_review_json(reviewed_root / "dataset" / "train" / f"{image_id}_combined.json")

            result = build_review_history(
                index_csv=index_path,
                reviewed_root=reviewed_root,
                llm_results_dir=llm_dir,
                output_csv=output_path,
            )

            self.assertEqual(len(result), 1)
            self.assertEqual(result.iloc[0]["llm_provider"], "openai")
            self.assertEqual(int(result.iloc[0]["llm_change"]), 0)
            self.assertIn("openai_dataset_train_1.csv", result.iloc[0]["llm_result_csv"])


if __name__ == "__main__":
    unittest.main()
