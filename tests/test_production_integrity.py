from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from production_integrity import (
    portable_csv_sha256,
    run_manifest_compatible,
    validate_plan_binding,
    write_plan_metadata,
)


class ProductionIntegrityTests(unittest.TestCase):
    def test_plan_binding_detects_index_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            index = root / "dataset_index.csv"
            plan = root / "work_plan_3000.csv"
            pd.DataFrame([{"image_id": "x1"}]).to_csv(index, index=False)
            pd.DataFrame([{"image_id": "x1"}]).to_csv(plan, index=False)
            write_plan_metadata(index, plan)
            self.assertTrue(validate_plan_binding(index, plan)["ready"])

            pd.DataFrame([{"image_id": "x2"}]).to_csv(index, index=False)
            check = validate_plan_binding(index, plan)
            self.assertFalse(check["ready"])
            self.assertIn("dataset_index_changed", check["reasons"])

    def test_portable_hash_ignores_pc_specific_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = root / "a.csv"
            b = root / "b.csv"
            common = {
                "group": "errors", "split": "train", "relative_folder": "artifact_fp_00",
                "image_id": "x1", "original_change": 1,
            }
            pd.DataFrame([{**common, "image_path": "C:/Users/A/x.jpg", "json_path": "C:/Users/A/x.json"}]).to_csv(a, index=False)
            pd.DataFrame([{**common, "image_path": "D:/team/x.jpg", "json_path": "D:/team/x.json"}]).to_csv(b, index=False)
            self.assertEqual(portable_csv_sha256(a), portable_csv_sha256(b))

    def test_resume_manifest_rejects_prompt_scope_or_selection_changes(self):
        base = {
            "model": "gpt-4o-mini",
            "prompt_sha256": "abc",
            "work_plan_sha256": "plan",
            "dataset_index_sha256": "index",
            "settings": {
                "work_mode": "production", "source": "errors", "split": "train",
                "start": 0, "limit": 1000, "selection_mode": "sequential", "confidence": 0.7,
                "error_types": ["artifact_fp_00", "farmland_fp_00"], "exclude_reviewed": False,
                "input_price": 0.15, "output_price": 0.60,
            },
        }
        same = {**base, "settings": dict(base["settings"])}
        same["settings"]["error_types"] = ["farmland_fp_00", "artifact_fp_00"]
        ok, mismatches = run_manifest_compatible(base, same)
        self.assertTrue(ok)
        self.assertEqual(mismatches, [])

        changed = {**base, "prompt_sha256": "different", "settings": dict(base["settings"])}
        changed["settings"]["split"] = "val"
        changed["settings"]["error_types"] = ["artifact_fp_00"]
        changed["settings"]["exclude_reviewed"] = True
        ok, mismatches = run_manifest_compatible(base, changed)
        self.assertFalse(ok)
        self.assertIn("prompt_sha256", mismatches)
        self.assertIn("settings.split", mismatches)
        self.assertIn("settings.error_types", mismatches)
        self.assertIn("settings.exclude_reviewed", mismatches)


if __name__ == "__main__":
    unittest.main()
