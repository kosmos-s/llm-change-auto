from pathlib import Path
import tempfile
import unittest

import pandas as pd

from src.review_events import EVENT_COLUMNS, append_review_event, backup_existing_reviewed_json


class ReviewEventTests(unittest.TestCase):
    def test_append_to_existing_empty_file_writes_header(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review_events.csv"
            path.touch()
            append_review_event(path, {
                "reviewer_name": "tester",
                "image_id": "x1",
                "source": "errors",
                "split": "train",
                "relative_folder": "a",
                "status": "saved",
            })
            frame = pd.read_csv(path)
            self.assertEqual(list(frame.columns), EVENT_COLUMNS)
            self.assertEqual(len(frame), 1)
            self.assertEqual(str(frame.iloc[0]["image_id"]), "x1")

    def test_nested_reviewed_path_is_preserved_in_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_path = root / "outputs" / "reviewed_json" / "errors" / "train" / "a" / "nested" / "x1_combined.json"
            save_path.parent.mkdir(parents=True)
            save_path.write_text('{"Artifact":"x"}', encoding="utf-8")
            backup_root = root / "outputs" / "backups" / "reviewed_json"

            backup = backup_existing_reviewed_json(save_path, backup_root)
            self.assertIsNotNone(backup)
            assert backup is not None
            relative = backup.relative_to(backup_root)
            self.assertEqual(relative.parts[1:], ("errors", "train", "a", "nested", "x1_combined.json"))
            self.assertEqual(backup.read_text(encoding="utf-8"), '{"Artifact":"x"}')


if __name__ == "__main__":
    unittest.main()
