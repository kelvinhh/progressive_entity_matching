#!/usr/bin/env python3
"""Run from a fresh checkout without installing third-party packages."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pem.candidates import generate_candidates
from pem.data import read_records, read_truth
from pem.evaluation import evaluate, recall_curve
from pem.scheduling import STRATEGIES, schedule


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(config_path: Path, output: Path) -> list[dict]:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    mode = config["mode"]
    if mode not in {"linkage", "deduplication"}:
        raise ValueError("mode must be linkage or deduplication")
    budgets = config["budgets"]
    if not budgets or any(type(b) is not int or b < 0 for b in budgets):
        raise ValueError("budgets must be a nonempty list of nonnegative integers")
    strategies = config.get("strategies", list(STRATEGIES))
    if not strategies or len(strategies) != len(set(strategies)) or any(s not in STRATEGIES for s in strategies):
        raise ValueError("Select distinct supported strategies")
    paths = []

    def resolve(value):
        path = (config_path.parent / value).resolve()
        paths.append(path)
        return path

    def records(spec):
        return read_records(resolve(spec["path"]), spec["id_column"], spec["text_columns"],
                            spec.get("delimiter", ","))

    tracemalloc.start()
    try:
        start = time.perf_counter()
        left = records(config["left"])
        right = records(config["right"]) if mode == "linkage" else None
        load_seconds = time.perf_counter() - start
        start = time.perf_counter()
        candidates = generate_candidates(left, right, **config.get("candidates", {}))
        candidate_seconds = time.perf_counter() - start
        # Labels are read only after generation; scores cannot depend on them.
        truth = read_truth(resolve(config["ground_truth"]), {r.id for r in left},
                           {r.id for r in (right if right is not None else left)}, mode,
                           config.get("ground_truth_delimiter", ","))
        candidate_recall = len({e.pair for e in candidates} & truth) / len(truth)
        rows, curves, orders = [], [], []
        for strategy in strategies:
            start = time.perf_counter()
            order = schedule(candidates, strategy, max(budgets), mode=mode,
                             partition=config.get("partition", "left"))
            scheduling_seconds = time.perf_counter() - start
            for budget in sorted(set(budgets)):
                rows.append({"dataset": config["name"], "strategy": strategy,
                             **evaluate(order, truth, budget),
                             "candidate_count": len(candidates),
                             "candidate_recall": candidate_recall,
                             "candidate_seconds": candidate_seconds,
                             "scheduling_seconds_at_max_budget": scheduling_seconds})
            curves.extend({"strategy": strategy, **row} for row in recall_curve(order, truth))
            orders.extend({"strategy": strategy, "rank": i, "left_id": e.left,
                           "right_id": e.right, "score": e.score,
                           "is_match": int(e.pair in truth)} for i, e in enumerate(order, 1))
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "metrics.csv", rows)
    write_csv(output / "curves.csv", curves)
    # Keep a header even when there are no candidate pairs.
    if orders:
        write_csv(output / "orders.csv", orders)
    else:
        (output / "orders.csv").write_text("strategy,rank,left_id,right_id,score,is_match\n")
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    metadata = {
        "python": sys.version, "platform": platform.platform(),
        "config_path": str(config_path), "mode": mode,
        "source_sha256": {str(p.relative_to(Path(__file__).resolve().parents[1])):
                          hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted((Path(__file__).resolve().parents[1] / "src/pem").glob("*.py"))},
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "load_seconds": load_seconds, "candidate_seconds": candidate_seconds,
        "traced_python_peak_bytes_entire_run": peak_bytes,
        "measurement_notes": "Single run under tracemalloc. Peak includes inputs, evaluation and all output rows; "
                             "not per-strategy RSS. Scheduling measured once at maximum budget. "
                             "Verification time excluded. Synthetic fixtures are pipeline checks only.",
        "progressive_recall_definition": "sum(recall(b) for b=1..B)/B; constant tail after exhaustion",
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs/experiment"))
    args = parser.parse_args()
    rows = run(args.config, args.output)
    for row in rows:
        print(f"{row['strategy']:6} B={row['budget']:4} "
              f"recall={row['recall']:.4f} PR={row['progressive_recall']:.4f}")
    print(f"Saved experiment to {args.output.resolve()}")
