#!/usr/bin/env python3
"""Compare our metric with the actual pinned upstream AUC method, without dependencies.

Only a checksum-verified class method is executed in isolation. No upstream code
is copied into the implementation. Raw reference source stays outside Git.
"""
from __future__ import annotations

import ast
from abc import ABC
import hashlib
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from queue import PriorityQueue

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pem.candidates import Candidate
from pem.evaluation import evaluate
from pem.scheduling import schedule


def main() -> None:
    manifest = json.loads((ROOT / "configs/benchmark_sources.json").read_text())
    path = "src/pyjedai/evaluation.py"
    source = (ROOT / "data/raw/pyjedai" / path).read_bytes()
    expected = next(row["sha256"] for row in manifest["files"] if row["path"] == path)
    if hashlib.sha256(source).hexdigest() != expected:
        raise ValueError("Reference source checksum mismatch")
    module = ast.parse(source)
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Evaluation")
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_generate_auc_data")
    isolated = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), method], type_ignores=[])
    namespace = {}
    exec(compile(ast.fix_missing_locations(isolated), str(path), "exec"), namespace)
    method_fn = namespace["_generate_auc_data"]
    rng = random.Random(5003)
    cases = 0
    for length in (0, 1, 2, 7, 25):
        pairs = [("left", str(i)) for i in range(length)]
        # Include a true pair that is absent from candidates (candidate recall < 1).
        for missing in (False, True):
            truth = {pair for pair in pairs if rng.random() < .5} or {("missing", "match")}
            if missing:
                truth.add(("unseen", "match"))
            order = [Candidate(a, b, .5) for a, b in pairs]
            for budget in (0, 1, length, length + 5):
                emitted = order[:budget]
                positions = [i for i, edge in enumerate(emitted) if edge.pair in truth]
                _, expected_auc = method_fn(SimpleNamespace(data=SimpleNamespace(ground_truth=truth)), len(emitted), positions)
                actual = evaluate(order, truth, budget)["pyjedai_auc"]
                if abs(expected_auc - actual) > 1e-12:
                    raise AssertionError((length, budget, expected_auc, actual))
                cases += 1

    utils_path = "src/pyjedai/utils.py"
    utils_source = (ROOT / "data/raw/pyjedai" / utils_path).read_bytes()
    utils_sha = next(row["sha256"] for row in manifest["files"] if row["path"] == utils_path)
    if hashlib.sha256(utils_source).hexdigest() != utils_sha:
        raise ValueError("Scheduler reference checksum mismatch")
    parsed = ast.parse(utils_source)
    classes = [node for node in parsed.body if isinstance(node, ast.ClassDef)
               and node.name in {"EntityScheduler", "DatasetScheduler"}]
    isolated = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *classes], type_ignores=[])
    namespace = {"ABC": ABC, "PriorityQueue": PriorityQueue}
    exec(compile(ast.fix_missing_locations(isolated), utils_path, "exec"), namespace)
    edges = [Candidate("0", "3", .9), Candidate("0", "4", .1), Candidate("1", "5", .8),
             Candidate("1", "6", .7), Candidate("2", "7", .6)]
    scheduling = {}
    for strategy, upstream_name in [("EC", "TOP"), ("BFS", "BFS"), ("DFS", "DFS"), ("Hybrid", "HB")]:
        scheduler = namespace["DatasetScheduler"](budget=5, global_top=strategy == "EC")
        for edge in edges:
            scheduler._insert_entity_neighbor(int(edge.left), int(edge.right), edge.score)
        scheduler._sort_neighborhoods_by_avg_weight()
        reference = scheduler._emit_pairs(upstream_name, SimpleNamespace(num_of_entities=8))
        reference_pairs = [(str(a), str(b)) for _, a, b in reference]
        our_pairs = [edge.pair for edge in schedule(edges, strategy)]
        agrees = reference_pairs == our_pairs
        if agrees != (strategy != "Hybrid"):
            raise AssertionError((strategy, our_pairs, reference_pairs))
        scheduling[strategy] = {"agrees_on_fixture": agrees, "ours": our_pairs, "upstream": reference_pairs}
    output = ROOT / "results/reference_verification.json"
    output.write_text(json.dumps({
        "reference_repository": manifest["repository"], "reference_commit": manifest["commit"],
        "source_path": path, "source_sha256": expected, "verified_cases": cases,
        "max_absolute_error_tolerance": 1e-12,
        "scheduler_source_sha256": utils_sha, "scheduling_fixture": scheduling,
        "hybrid_difference": "Our implementation follows paper Section 6: globally sort first edges. "
                             "Pinned DatasetScheduler HB emits first edges in node-mean order instead.",
        "scope": "_generate_auc_data with batch_size=1, actual emissions, no early-stop mode; "
                 "does not establish full workflow equivalence or identify the paper's original software commit",
    }, indent=2) + "\n")
    print(f"Verified {cases} metric cases against pinned upstream method")
    print("Scheduler fixture: EC/BFS/DFS agree; Hybrid differs as documented in paper-versus-code audit")


if __name__ == "__main__":
    main()
