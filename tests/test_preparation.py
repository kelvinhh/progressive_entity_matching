import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare", ROOT / "scripts/prepare_benchmarks.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PreparationTests(unittest.TestCase):
    def test_labels_excluded_and_reverse_truth_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "records.csv").write_text("id,label,title\na,same,Alpha\nb,same,Beta\n")
            (root / "gt.csv").write_text("id1,id2\na,b\nb,a\n")
            config = {"key": "case", "mode": "deduplication", "delimiter": ",",
                      "left": "records.csv", "truth": "gt.csv", "id_column": "id",
                      "exclude_columns": ["id", "label"], "truth_columns": ["id1", "id2"],
                      "expected_counts": [2, None, 1], "paper_counts": [2, None, 1]}
            result = prepare.prepare_dataset(config, root, root / "processed")
            self.assertEqual(result["removed_duplicate_truth_rows"], 1)
            text = (root / "processed/case/left.csv").read_text()
            self.assertNotIn("same", text)
            self.assertIn("Alpha", text)

    def test_corrupt_cached_source_rejected_before_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.csv"
            content = b"expected"
            manifest = {"files": [{"path": "raw.csv", "sha256": hashlib.sha256(content).hexdigest(),
                                   "git_blob_sha": "unused", "size_bytes": len(content)}]}
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                prepare.verify_sources(manifest, Path(directory), False)
