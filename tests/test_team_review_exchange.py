from pathlib import Path
import json
import tempfile
import unittest

from src.team_review_exchange import export_review_package, preview_review_package


class TeamReviewExchangeTests(unittest.TestCase):
    def test_export_and_preview_detects_same_file(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp)
            target = outputs / "reviewed_json" / "errors" / "train" / "x" / "sample_combined.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"value": 1}), encoding="utf-8")
            package = export_review_package(outputs, "tester")
            preview = preview_review_package(package, outputs)
            self.assertEqual(len(preview["items"]), 1)
            self.assertEqual(preview["items"][0]["state"], "same")


if __name__ == "__main__":
    unittest.main()
