#!/usr/bin/env python3
"""Execute the predeclared grid sequentially; report every setting without selection."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from run_experiment import run, write_csv

ROOT = Path(__file__).resolve().parents[1]


def make_configs(protocol: dict):
    for dataset in protocol["datasets"]:
        path = ROOT / "configs/benchmarks" / f"{dataset}.json"
        base = json.loads(path.read_text())
        for side in ("left", "right"):
            if side in base:
                base[side]["path"] = str((path.parent / base[side]["path"]).resolve())
        base["ground_truth"] = str((path.parent / base["ground_truth"]).resolve())
        grid = protocol["grid"]
        directions = grid["linkage_indexing" if base["mode"] == "linkage" else "deduplication_indexing"]
        for ngram, k, indexing in itertools.product(grid["ngram"], grid["top_k"], directions):
            config = json.loads(json.dumps(base))
            config["candidates"].update(ngram=ngram, top_k=k, indexing=indexing)
            config["strategies"] = protocol["strategies"]
            config["budget_multipliers"] = protocol["budget_multipliers"]
            config["trace_memory"] = False
            identifier = f"{dataset}_g{ngram}_k{k}_{indexing}"
            yield identifier, config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs/experiment_protocol.json")
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    output = ROOT / "outputs/sweep"
    output.mkdir(parents=True, exist_ok=True)
    metrics, provenance = [], []
    configs = list(make_configs(protocol))
    for number, (identifier, config) in enumerate(configs, 1):
        destination = output / identifier
        destination.mkdir(exist_ok=True)
        config_path = destination / "input_config.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        rows = run(config_path, destination)
        counts = {"true_pair_count": rows[-1]["budget"] // max(protocol["budget_multipliers"])}
        for row in rows:
            row.update(setting=identifier, ngram=config["candidates"]["ngram"],
                       top_k=config["candidates"]["top_k"], indexing=config["candidates"]["indexing"], **counts)
        metrics.extend(rows)
        metadata = json.loads((destination / "metadata.json").read_text())
        provenance.append({"setting": identifier, "config": config, "metadata": metadata})
        print(f"[{number}/{len(configs)}] {identifier}: candidate recall {rows[0]['candidate_recall']:.4f}", flush=True)
    write_csv(ROOT / "results/sweep_metrics.csv", metrics)
    (ROOT / "results/sweep_manifest.json").write_text(json.dumps({
        "protocol": protocol, "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(),
        "settings": provenance, "selection": "None; all predeclared settings are reported.",
    }, indent=2) + "\n")
    print(f"Saved {len(configs)} settings and {len(metrics)} metric rows", flush=True)


if __name__ == "__main__":
    main()
