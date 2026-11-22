import json
import tempfile
import unittest
from pathlib import Path

from pem.provenance import portable_metadata


class ProvenanceTests(unittest.TestCase):
    def test_nested_project_paths_and_hash_keys_are_relative(self):
        root = Path(__file__).resolve().parents[1]
        source = str(root / "data/example.csv")
        value = {"config": {"path": source}, "input_sha256": {source: "unchanged_hash"},
                 "score": .9, "url": "https://github.com/example/project"}
        actual = portable_metadata(value, root)
        self.assertEqual(actual["config"]["path"], "data/example.csv")
        self.assertEqual(actual["input_sha256"], {"data/example.csv": "unchanged_hash"})
        self.assertEqual(actual["url"], value["url"])
        self.assertEqual(actual["score"], .9)
        self.assertEqual(value["config"]["path"], source)
        self.assertNotIn(str(root), json.dumps(actual))

    def test_external_paths_do_not_expose_names_and_aliases_are_consistent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            private = str(Path(directory) / "private_account" / "private_filename.csv")
            other = str(Path(directory) / "another_account" / "other.csv")
            actual = portable_metadata({"path": private, "hashes": {private: "a", other: "b"}}, root)
            self.assertEqual(actual["path"], "external/input_1.csv")
            self.assertEqual(actual["hashes"], {"external/input_1.csv": "a", "external/input_2.csv": "b"})
            text = json.dumps(actual)
            self.assertNotIn("private_account", text)
            self.assertNotIn("private_filename", text)
