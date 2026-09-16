from pathlib import Path
import json
import tempfile
import unittest

import pandas as pd

from src.effective_quality import validate_effective_labels


class EffectiveQualityTests(unittest.TestCase):
    def test_reviewed_json_is_validated_instead_of_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "orig_combined.json"
            original.write_text(json.dumps({"Artifact": "x", "artifact_detail": {}}), encoding="utf-8")
            index = root / "dataset_index.csv"
            pd.DataFrame([{
                "image_id": "orig", "group": "errors", "split": "train", "relative_folder": "a",
                "json_path": str(original), "image_path": str(root / "orig_combined.jpg"),
            }]).to_csv(index, index=False)

            reviewed_root = root / "reviewed_json"
            reviewed = reviewed_root / "errors" / "train" / "a" / "orig_combined.json"
            reviewed.parent.mkdir(parents=True)
            reviewed.write_text(json.dumps({
                "Artifact": "x", "artifact_detail": {"arti_bu": "o"}
            }), encoding="utf-8")

            report = validate_effective_labels(index, reviewed_root)
            self.assertEqual(len(report), 1)
            self.assertEqual(report.iloc[0]["code"], "effective_artifact_logic")
            self.assertEqual(report.iloc[0]["label_source"], "reviewed")


if __name__ == "__main__":
    unittest.main()
