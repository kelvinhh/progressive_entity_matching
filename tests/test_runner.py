import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_experiment", ROOT / "scripts/run_experiment.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_both_demo_modes(self):
        for mode in ("linkage", "deduplication"):
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                rows = runner.run(ROOT / f"configs/demo_{mode}.json", output)
                self.assertEqual(len(rows), 28)
                for row in rows:
                    self.assertLessEqual(row["recall"], row["candidate_recall"])
                    self.assertLessEqual(row["progressive_recall"], row["recall"])
                    self.assertLessEqual(row["comparisons"], row["budget"])
                final = [row for row in rows if row["budget"] == 60]
                self.assertEqual(len({row["recall"] for row in final}), 1)
                metadata = json.loads((output / "metadata.json").read_text())
                self.assertEqual(len(metadata["input_sha256"]), 3 if mode == "linkage" else 2)
                self.assertTrue((output / "curves.csv").exists())
                self.assertTrue((output / "orders.csv").exists())
