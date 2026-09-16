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

    def test_resume_manifest_rejects_prompt_or_scope_changes(self):
        base = {
            "model": "gpt-4o-mini",
            "prompt_sha256": "abc",
            "work_plan_sha256": "plan",
            "dataset_index_sha256": "index",
            "settings": {
                "work_mode": "production", "source": "errors", "split": "train",
                "start": 0, "limit": 1000, "selection_mode": "sequential", "confidence": 0.7,
            },
        }
        same = {**base, "settings": dict(base["settings"])}
        ok, mismatches = run_manifest_compatible(base, same)
        self.assertTrue(ok)
        self.assertEqual(mismatches, [])

        changed = {**base, "prompt_sha256": "different", "settings": dict(base["settings"])}
        changed["settings"]["split"] = "val"
        ok, mismatches = run_manifest_compatible(base, changed)
        self.assertFalse(ok)
        self.assertIn("prompt_sha256", mismatches)
        self.assertIn("settings.split", mismatches)


if __name__ == "__main__":
    unittest.main()
