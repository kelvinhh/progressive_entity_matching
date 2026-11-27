#!/usr/bin/env python3
"""Execute pinned upstream components on controlled fixtures and real candidate graphs.

This is a component audit, not a full pyJedAI installation or end-to-end baseline.
Upstream code is checksum-verified and executed without rewriting its algorithms.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import random
import sys
from abc import ABC
from collections import defaultdict
from pathlib import Path
from queue import PriorityQueue
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pem.candidates import Candidate, generate_candidates, vectorize
from pem.data import Record, read_records, read_truth
from pem.evaluation import evaluate
from pem.scheduling import STRATEGIES, schedule

MANIFEST = json.loads((ROOT / "configs/benchmark_sources.json").read_text())
SOURCES = {}


def extract(path, names, namespace):
    entry = next(e for e in MANIFEST["files"] if e["path"] == path)
    source = (ROOT / "data/raw/pyjedai" / path).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    assert len(source) == entry["size_bytes"]
    assert hashlib.sha256(source).hexdigest() == entry["sha256"]
    assert blob == entry["git_blob_sha"]
    SOURCES[path] = entry["sha256"]
    parsed = ast.parse(source)
    nodes = [n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), path, "exec"), namespace)
    return namespace


def upstream_schedule(cls, edges, strategy, left_ids, right_ids, *, native=False, dedup=False, budget=None):
    left_ids = list(left_ids) if native else sorted(left_ids)
    right_ids = left_ids if dedup else (list(right_ids) if native else sorted(right_ids))
    lm = {v: i for i, v in enumerate(left_ids)}
    rm = lm if dedup else {v: len(lm) + i for i, v in enumerate(right_ids)}
    reverse = {v: k for k, v in lm.items()}
    reverse.update({v: k for k, v in rm.items()})
    scheduler = cls(budget=len(edges) if budget is None else budget, global_top=strategy == "EC")
    for edge in edges:
        a, b = lm[edge.left], rm[edge.right]
        if dedup:
            # ProgressiveMatching._schedule_candidates inserts smaller endpoint only.
            a, b = min(a, b), max(a, b)
        scheduler._insert_entity_neighbor(a, b, edge.score)
    scheduler._sort_neighborhoods_by_avg_weight()
    emitted = scheduler._emit_pairs({"EC": "TOP", "Hybrid": "HB"}.get(strategy, strategy),
                                   SimpleNamespace(num_of_entities=len(reverse)))
    result = []
    for score, a, b in emitted:
        pair = (reverse[a], reverse[b])
        if dedup:
            pair = tuple(sorted(pair))
        result.append(Candidate(*pair, score))
    return result


class GraphCollector:
    """Output adapter only; candidate selection still runs the upstream method."""
    def __init__(self):
        self.edges = {}

    def add_edge(self, a, b, weight):
        self.edges[a, b] = weight


def topk_checks():
    ns = extract("src/pyjedai/joins.py", {"AbstractJoin", "TopKJoin", "PETopKJoin"},
                 {"PYJEDAIFeature": object, "PriorityQueue": PriorityQueue, "math": math, "defaultdict": defaultdict})
    cases = []
    fixtures = [("distinct", [.9, .7, .3]), ("boundary_tie", [.9, .8, .8]),
                ("zero_supplied", [0., 0., 0.])]
    for name, scores in fixtures:
        for store in (True, False):
            join = ns["PETopKJoin"](K=2, metric="cosine", tokenization="char", qgrams=3)
            join.data = SimpleNamespace(dataset_limit=len(scores))
            # Shared scores isolate selection; this does NOT verify TF-IDF generation.
            join.vectorizer = SimpleNamespace(predict=lambda id1, id2: scores[id1])
            join.store_neighborhoods = store
            join.neighborhoods = defaultdict(list)
            join.pairs = GraphCollector()
            join._process_candidates(set(range(len(scores))), 0, 0)
            if store:
                join._process_neighborhoods()
                selected = sorted(a for _, a in join.neighborhoods[len(scores)])
            else:
                selected = sorted(a for a, _ in join.pairs.edges)
            ours = sorted(sorted((i for i, score in enumerate(scores) if score > 0),
                                 key=lambda i: (-scores[i], str(i)))[:2])
            cases.append({"fixture": name, "store_neighborhoods": store,
                          "ours_selected": ours, "upstream_selected": selected})
    assert cases[0]["upstream_selected"] == cases[0]["ours_selected"]
    assert cases[2]["upstream_selected"] == cases[2]["ours_selected"]
    assert len(cases[3]["upstream_selected"]) == 3  # no-cache path retains boundary ties
    assert len(cases[4]["upstream_selected"]) == 2  # zero scores are admitted if supplied
    # Execute the original character-posting index and query loops too, using
    # explicitly shared TF-IDF scores. No pandas/networkx/full fit is required.
    index_cases = []
    for name, target, query in [
        ("positive_distinct", [Record("a", "abc"), Record("b", "abcd"), Record("c", "zzz")], Record("q", "abcde")),
        ("character_overlap_without_3gram_overlap", [Record("a", "abd")], Record("q", "abc")),
        ("numeric_row_order_vs_string_id_tie", [Record("2", "abc"), Record("10", "abc")], Record("q", "abc")),
    ]:
        vectors = vectorize([query] + target, 3)
        scores = [min(1., sum(value * v.get(t, 0.) for t, value in vectors[0].items())) for v in vectors[1:]]
        join = ns["PETopKJoin"](K=1, metric="cosine", tokenization="char", qgrams=3)
        join.data = SimpleNamespace(dataset_limit=len(target))
        join.vectorizer = SimpleNamespace(predict=lambda id1, id2: scores[id1])
        join.target_entities = [r.text for r in target]
        join.indexed_entities = [query.text]
        join.indexed_entities_count = 1
        join._progress_bar = SimpleNamespace(update=lambda _: None)
        join.store_neighborhoods = True
        join.neighborhoods = defaultdict(list)
        join.pairs = GraphCollector()
        join.entity_index = join._create_entity_index()
        join.clean_indexing()
        join._process_neighborhoods()
        selected = sorted(target[a].id for neighbors in join.neighborhoods.values() for _, a in neighbors)
        ours = sorted(e.right for e in generate_candidates([query], target, top_k=1))
        index_cases.append({"fixture": name, "ours_selected": ours, "upstream_selected": selected,
                            "shared_similarity_scores": scores})
    assert index_cases[0]["ours_selected"] == index_cases[0]["upstream_selected"]
    assert index_cases[1]["ours_selected"] == [] and index_cases[1]["upstream_selected"] == ["a"]
    assert index_cases[2]["ours_selected"] == ["10"] and index_cases[2]["upstream_selected"] == ["2"]
    return {"selection_fixtures": cases, "index_loop_fixtures_shared_scores": index_cases,
            "score_generation_independently_verified": False}


def random_checks(cls):
    rng = random.Random(5003)
    count = 0
    hybrid_differences = 0
    for _ in range(100):
        left = [f"l{i:02}" for i in range(rng.randint(1, 9))]
        right = [f"r{i:02}" for i in range(rng.randint(1, 9))]
        edges = [Candidate(a, b, rng.random()) for a in left for b in right if rng.random() < .5]
        for strategy in STRATEGIES:
            for budget in sorted({0, 1, len(edges) // 2, len(edges), len(edges) + 3}):
                reference = upstream_schedule(cls, edges, strategy, left, right, budget=budget)
                ours = schedule(edges, strategy, budget)
                agrees = [e.pair for e in ours] == [e.pair for e in reference]
                if strategy != "Hybrid":
                    assert agrees, (strategy, budget)
                else:
                    hybrid_differences += not agrees
                count += 1
    return {"graphs": 100, "strategy_budget_cases": count,
            "EC_BFS_DFS_all_agree": True, "Hybrid_differing_cases": hybrid_differences,
            "scope": "random bipartite graphs, no deliberately tied scores/means, aligned ID order"}


def main():
    ns = extract("src/pyjedai/utils.py", {"EntityScheduler", "DatasetScheduler"},
                 {"ABC": ABC, "PriorityQueue": PriorityQueue})
    evaluation = extract("src/pyjedai/evaluation.py", {"Evaluation"}, {})
    metric = evaluation["Evaluation"]._generate_auc_data
    cls = ns["DatasetScheduler"]
    summary = {"reference_repository": MANIFEST["repository"], "reference_commit": MANIFEST["commit"],
               "scope": "Actual upstream components via AST; shared locally generated candidate scores. "
                        "Not original TF-IDF/Join fit, full workflow, published-number or timing equivalence.",
               "random_scheduling": random_checks(cls), "topk_selection": topk_checks(), "datasets": []}
    rows = []
    for dataset in MANIFEST["datasets"]:
        name = dataset["key"]
        cp = ROOT / "configs/benchmarks" / f"{name}.json"
        config = json.loads(cp.read_text())
        def records(spec):
            return read_records(cp.parent / spec["path"], spec["id_column"], spec["text_columns"])
        left = records(config["left"])
        dedup = config["mode"] == "deduplication"
        right = None if dedup else records(config["right"])
        edges = generate_candidates(left, right, **config["candidates"])
        truth = read_truth(cp.parent / config["ground_truth"], {r.id for r in left},
                           {r.id for r in (left if dedup else right)}, config["mode"])
        ds = {"dataset": name, "candidate_count": len(edges), "comparisons": [],
              "input_sha256": {str((cp.parent / config[k]["path"]).resolve().relative_to(ROOT)):
                               hashlib.sha256((cp.parent / config[k]["path"]).read_bytes()).hexdigest()
                               for k in (["left"] if dedup else ["left", "right"])}}
        tp = cp.parent / config["ground_truth"]
        ds["input_sha256"][str(tp.resolve().relative_to(ROOT))] = hashlib.sha256(tp.read_bytes()).hexdigest()
        for native in (False, True):
            encoding = "native_record_order" if native else "aligned_id_order"
            for strategy in STRATEGIES:
                ours = schedule(edges, strategy, mode=config["mode"])
                reference = upstream_schedule(cls, edges, strategy, [r.id for r in left],
                                              [] if dedup else [r.id for r in right], native=native, dedup=dedup)
                a, b = [e.pair for e in ours], [e.pair for e in reference]
                assert len(a) == len(b) == len(edges) and set(a) == set(b)
                first = next((i for i, (x, y) in enumerate(zip(a, b), 1) if x != y), None)
                ds["comparisons"].append({"id_encoding": encoding, "strategy": strategy,
                                          "orders_equal": a == b, "first_differing_rank": first,
                                          "same_candidate_set": True,
                                          "ours_at_first_difference": a[first-1] if first else None,
                                          "upstream_at_first_difference": b[first-1] if first else None})
                for multiple in config["budget_multipliers"]:
                    budget = multiple * len(truth)
                    for label, order in (("ours", ours), ("upstream_shared_candidates", reference)):
                        result = evaluate(order, truth, budget)
                        emitted = order[:budget]
                        positions = [i for i, e in enumerate(emitted) if e.pair in truth]
                        _, auc = metric(SimpleNamespace(data=SimpleNamespace(ground_truth=truth)), len(emitted), positions)
                        assert abs(auc - result["pyjedai_auc"]) <= 1e-12
                        rows.append({"dataset": name, "id_encoding": encoding, "strategy": strategy,
                                     "implementation": label, **result})
        summary["datasets"].append(ds)
        print(f"Audited {name}: {len(edges)} candidates", flush=True)
    summary["source_sha256"] = SOURCES
    summary["independent_implementation_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                   for p in sorted((ROOT / "src/pem").glob("*.py"))}
    summary["audit_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summary["real_data_metric_checks"] = len(rows)
    (ROOT / "results/reference_component_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (ROOT / "results/reference_component_metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Verified {summary['random_scheduling']['strategy_budget_cases']} randomized cases; {len(rows)} real-data AUC checks")


if __name__ == "__main__":
    main()
