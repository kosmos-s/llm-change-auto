from pathlib import Path
import json
import tempfile
import unittest

from src.run_manifest import read_manifest, write_manifest


class RunManifestTests(unittest.TestCase):
    def test_write_manifest_archives_same_prefix_artifacts_before_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            outputs = Path(temp) / "outputs"
            manifest_path = outputs / "run_manifests" / "batch_a.json"
            llm = outputs / "llm_results" / "batch_a.csv"
            compare = outputs / "compare_results" / "batch_a_compare.csv"
            review = outputs / "review_lists" / "batch_a_review.csv"
            checkpoint = outputs / "llm_results" / "batch_a.checkpoint.json"
            for path in [manifest_path, llm, compare, review, checkpoint]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("old", encoding="utf-8")

            new_manifest = {"batch_id": "batch_a", "model": "gpt-4o-mini", "settings": {}}
            write_manifest(manifest_path, new_manifest)

            self.assertEqual(read_manifest(manifest_path), new_manifest)
            self.assertFalse(llm.exists())
            self.assertFalse(compare.exists())
            self.assertFalse(review.exists())
            self.assertFalse(checkpoint.exists())

            backups = list((outputs / "backups" / "overwritten_batches").glob("*/batch_a"))
            self.assertEqual(len(backups), 1)
            backup_root = backups[0]
            self.assertTrue((backup_root / "llm_results" / "batch_a.csv").exists())
            self.assertTrue((backup_root / "compare_results" / "batch_a_compare.csv").exists())
            self.assertTrue((backup_root / "review_lists" / "batch_a_review.csv").exists())
            self.assertTrue((backup_root / "run_manifests" / "batch_a.json").exists())

    def test_write_manifest_without_existing_artifacts_creates_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "outputs" / "run_manifests" / "batch_b.json"
            manifest = {"batch_id": "batch_b", "model": "gpt-4o-mini", "settings": {}}
            result = write_manifest(path, manifest)
            self.assertEqual(result, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), manifest)


if __name__ == "__main__":
    unittest.main()
