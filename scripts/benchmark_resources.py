#!/usr/bin/env python3
"""Sequential randomized blocks of isolated subprocess time and process RSS trials."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import resource
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from run_experiment import write_csv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pem.candidates import Candidate, generate_candidates
from pem.data import read_records, read_truth
from pem.scheduling import STRATEGIES, schedule
from pem.provenance import portable_metadata


def load_records(config: dict, base: Path):
    def read(spec):
        return read_records((base / spec["path"]).resolve(), spec["id_column"],
                            spec["text_columns"], spec.get("delimiter", ","))
    return read(config["left"]), read(config["right"]) if config["mode"] == "linkage" else None


def signature(edges: list[Candidate]) -> str:
    digest = hashlib.sha256()
    for edge in edges:
        digest.update((json.dumps([edge.left, edge.right, edge.score], separators=(",", ":")) + "\n").encode())
    return digest.hexdigest()


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def worker(job: dict) -> dict:
    start = time.perf_counter()
    if job["stage"] == "candidates":
        config_path = Path(job["config_path"])
        config = json.loads(config_path.read_text())
        left, right = load_records(config, config_path.parent)
        load_seconds = time.perf_counter() - start
        pre_stage_peak = peak_rss_bytes()
        start = time.perf_counter()
        edges = generate_candidates(left, right, **config["candidates"])
    else:
        raw = json.loads(Path(job["candidate_snapshot"]).read_text())
        candidates = [Candidate(*entry) for entry in raw]
        del raw
        load_seconds = time.perf_counter() - start
        pre_stage_peak = peak_rss_bytes()
        start = time.perf_counter()
        edges = schedule(candidates, job["stage"], job["budget"],
                         mode=job["mode"], partition=job["partition"])
    seconds = time.perf_counter() - start
    peak = peak_rss_bytes()  # Capture before hashing/serializing output.
    return {"dataset": job["dataset"], "stage": job["stage"], "stage_seconds": seconds,
            "input_load_seconds": load_seconds, "pre_stage_peak_rss_bytes": pre_stage_peak,
            "worker_peak_rss_bytes": peak, "emitted_count": len(edges),
            "output_signature": signature(edges), "pid": os.getpid()}


def summarize(rows: list[dict]) -> list[dict]:
    summaries = []
    for key in sorted({(r["dataset"], r["stage"]) for r in rows}):
        group = [r for r in rows if (r["dataset"], r["stage"]) == key]
        times = [r["stage_seconds"] for r in group]
        peaks = [r["worker_peak_rss_bytes"] / 2**20 for r in group]
        summaries.append({"dataset": key[0], "stage": key[1], "repeats": len(group),
                          "seconds_median": statistics.median(times), "seconds_min": min(times),
                          "seconds_max": max(times), "seconds_sd": statistics.stdev(times) if len(times) > 1 else 0,
                          "peak_rss_mib_median": statistics.median(peaks),
                          "peak_rss_mib_min": min(peaks), "peak_rss_mib_max": max(peaks)})
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs/experiment_protocol.json")
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(json.loads(args.worker.read_text()))))
        return
    protocol = json.loads(args.protocol.read_text())
    settings = protocol["resources"]
    work = ROOT / "outputs/resources"
    work.mkdir(parents=True, exist_ok=True)
    jobs, provenance = [], []
    for dataset in protocol["datasets"]:
        config_path = ROOT / "configs/benchmarks" / f"{dataset}.json"
        config = json.loads(config_path.read_text())
        left, right = load_records(config, config_path.parent)
        candidates = generate_candidates(left, right, **config["candidates"])
        snapshot = work / f"{dataset}_candidate_snapshot.json"
        snapshot.write_text(json.dumps([[e.left, e.right, e.score] for e in candidates]))
        truth = read_truth((config_path.parent / config["ground_truth"]).resolve(),
                           {r.id for r in left}, {r.id for r in (right if right is not None else left)}, config["mode"])
        budget = max(config["budget_multipliers"]) * len(truth)
        expected = {"candidates": signature(candidates)}
        for strategy in STRATEGIES:
            expected[strategy] = signature(schedule(candidates, strategy, budget,
                                                    mode=config["mode"], partition=config["partition"]))
        for stage in ["candidates", *STRATEGIES]:
            job = {"dataset": dataset, "stage": stage, "config_path": str(config_path),
                   "candidate_snapshot": str(snapshot), "budget": budget,
                   "mode": config["mode"], "partition": config["partition"],
                   "expected_signature": expected[stage]}
            path = work / f"{dataset}_{stage}.json"
            path.write_text(json.dumps(job, indent=2) + "\n")
            jobs.append((path, job))
        provenance.append({"dataset": dataset, "config": config,
                           "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                           "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                           "output_signatures": expected,
                           "input_sha256": {name: hashlib.sha256((config_path.parent / spec["path"]).resolve().read_bytes()).hexdigest()
                                            for name, spec in config.items() if name in {"left", "right"}},
                           "ground_truth_sha256": hashlib.sha256((config_path.parent / config["ground_truth"]).resolve().read_bytes()).hexdigest()})
    rng = random.Random(settings["seed"])
    rows, execution_order = [], []
    blocks = settings["warmup_blocks"] + settings["measured_blocks"]
    for block in range(blocks):
        ordered = list(jobs)
        rng.shuffle(ordered)
        warmup = block < settings["warmup_blocks"]
        for position, (path, job) in enumerate(ordered):
            environment = dict(os.environ, PYTHONHASHSEED=settings["hash_seed"])
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(path)],
                                    capture_output=True, text=True, env=environment,
                                    timeout=settings["worker_timeout_seconds"])
            if result.returncode:
                raise RuntimeError(f"Worker failed: {job['dataset']} {job['stage']}\n{result.stderr}")
            row = json.loads(result.stdout)
            if row["output_signature"] != job["expected_signature"]:
                raise ValueError(f"Output mismatch in isolated worker: {job['dataset']} {job['stage']}")
            execution_order.append({"block": block, "position": position, "warmup": warmup,
                                    "dataset": job["dataset"], "stage": job["stage"]})
            if not warmup:
                row.update(block=block - settings["warmup_blocks"], position=position)
                rows.append(row)
                write_csv(work / "measurements_checkpoint.csv", rows)
        print(f"Completed resource block {block + 1}/{blocks} ({'warm-up' if warmup else 'measured'})", flush=True)
    write_csv(ROOT / "results/resource_measurements.csv", rows)
    write_csv(ROOT / "results/resource_summary.csv", summarize(rows))
    (ROOT / "results/resource_manifest.json").write_text(json.dumps(portable_metadata({
        "filesystem_path_base": "absolute project paths are repository-relative; original config-relative paths keep their base; external paths use anonymous aliases",
        "protocol": protocol, "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted((ROOT / "src/pem").glob("*.py"))},
        "python": sys.version, "executable": Path(sys.executable).name, "platform": platform.platform(),
        "machine": platform.machine(), "cpu": platform.processor(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "rss_units": "bytes after platform conversion", "datasets": provenance,
        "execution_order": execution_order,
        "measurement_boundary": "Fresh worker per trial. Stage timer excludes input loading, hashing, result serialization and process startup. "
                                "RSS is the full worker lifetime peak through the stage, including imports and input loading. "
                                "Candidate and scheduler memory have different input baselines; no subtraction or algorithm-only memory claim.",
    }, ROOT), indent=2) + "\n")
    print(f"Saved {len(rows)} measurements across {len(jobs)} dataset-stage groups", flush=True)


if __name__ == "__main__":
    main()
