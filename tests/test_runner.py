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
    def test_budget_multipliers_and_invalid_settings(self):
        self.assertEqual(runner.resolve_budgets({"budget_multipliers": [1, 2, 10]}, 89), [89, 178, 890])
        for config in ({}, {"budgets": [1], "budget_multipliers": [1]},
                       {"budget_multipliers": [0]}, {"budget_multipliers": [True]}):
            with self.assertRaises(ValueError):
                runner.resolve_budgets(config, 3)

    def test_untraced_run_and_resolved_budgets(self):
        config = json.loads((ROOT / "configs/demo_linkage.json").read_text())
        for key in ("left", "right"):
            config[key]["path"] = str((ROOT / "configs" / config[key]["path"]).resolve())
        config["ground_truth"] = str((ROOT / "configs" / config["ground_truth"]).resolve())
        config.pop("budgets")
        config["budget_multipliers"] = [1, 2]
        config["trace_memory"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config))
            rows = runner.run(path, Path(directory) / "output")
            self.assertEqual({r["budget"] for r in rows}, {6, 12})
            metadata = json.loads((Path(directory) / "output/metadata.json").read_text())
            self.assertEqual(metadata["ground_truth_pairs"], 6)
            self.assertIsNone(metadata["traced_python_peak_bytes_entire_run"])

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
