import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sweep
import benchmark_resources


class GridTests(unittest.TestCase):
    def test_grid_cardinality_uniqueness_and_fixed_comparators(self):
        protocol = json.loads((ROOT / "configs/experiment_protocol.json").read_text())
        configs = list(run_sweep.make_configs(protocol))
        self.assertEqual(len(configs), 42)
        self.assertEqual(len({name for name, _ in configs}), 42)
        for _, config in configs:
            self.assertEqual(config["strategies"], ["EC", "BFS", "DFS", "Hybrid"])
            self.assertEqual(config["budget_multipliers"], list(range(1, 11)))
            self.assertNotIn("budgets", config)
        cora = [config for _, config in configs if config["mode"] == "deduplication"]
        self.assertEqual(len(cora), 6)
        self.assertEqual({c["candidates"]["indexing"] for c in cora}, {"right"})


class ResourceTests(unittest.TestCase):
    def test_scheduler_worker_uses_snapshot_and_preserves_order(self):
        from pem.candidates import Candidate
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.json"
            snapshot.write_text(json.dumps([["a", "b", .8], ["a", "c", .9]]))
            result = benchmark_resources.worker({"dataset": "test", "stage": "EC",
                "candidate_snapshot": str(snapshot), "budget": 1,
                "mode": "linkage", "partition": "left"})
            self.assertEqual(result["output_signature"], benchmark_resources.signature([Candidate("a", "c", .9)]))
            self.assertEqual(result["emitted_count"], 1)
            self.assertGreater(result["worker_peak_rss_bytes"], 0)

    def test_summary_uses_measured_range_and_sample_sd(self):
        rows = [{"dataset": "case", "stage": "EC", "stage_seconds": x,
                 "worker_peak_rss_bytes": x * 2**20} for x in (1, 2, 3)]
        result = benchmark_resources.summarize(rows)[0]
        self.assertEqual(result["repeats"], 3)
        self.assertEqual(result["seconds_median"], 2)
        self.assertEqual(result["seconds_sd"], 1)
        self.assertEqual(result["peak_rss_mib_min"], 1)
        self.assertEqual(result["peak_rss_mib_max"], 3)

    def test_order_signature_detects_reordering(self):
        from pem.candidates import Candidate
        edges = [Candidate("a", "b", .9), Candidate("a", "c", .8)]
        self.assertNotEqual(benchmark_resources.signature(edges), benchmark_resources.signature(edges[::-1]))
