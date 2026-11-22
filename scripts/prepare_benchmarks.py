#!/usr/bin/env python3
"""Verify pinned public sources, normalize CSVs, and write benchmark configs.

Network downloads are opt-in. Cached bytes are checked even without --download.
No raw data is committed; sources and SHA-256 checksums are versioned.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pem.data import read_records, read_truth


def verify_sources(manifest: dict, cache: Path, download: bool) -> None:
    for entry in manifest["files"]:
        path = cache / entry["path"]
        if path.exists():
            content = path.read_bytes()
        elif download:
            url = (f"https://raw.githubusercontent.com/{manifest['repository']}/"
                   f"{manifest['commit']}/{entry['path']}")
            request = urllib.request.Request(url, headers={"User-Agent": "pem-course-replication/0.1"})
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()
        else:
            raise FileNotFoundError(f"Missing {path}; run with --download on a network-enabled host")
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {entry['path']}")
        git_sha = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if git_sha != entry["git_blob_sha"] or len(content) != entry["size_bytes"]:
            raise ValueError(f"Git blob or size mismatch: {entry['path']}")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def convert_records(source: Path, destination: Path, spec: dict) -> dict:
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=spec["delimiter"])
        header = reader.fieldnames or []
        if len(header) != len(set(header)) or spec["id_column"] not in header:
            raise ValueError(f"Invalid record header: {source}")
        text_columns = [name for name in header if name not in spec["exclude_columns"]]
        rows = list(reader)
        if not text_columns or any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError(f"Malformed record rows: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "text"])
        for row in rows:
            writer.writerow([row[spec["id_column"]].strip(), " ".join(row[c] for c in text_columns)])
    # Validate IDs before ground-truth conversion.
    records = read_records(destination, "id", ["text"])
    return {"rows": len(records), "text_columns": text_columns,
            "excluded_columns": spec["exclude_columns"],
            "empty_text_records": sum(not r.text for r in records),
            "ids": {r.id for r in records}}


def prepare_dataset(spec: dict, cache: Path, destination: Path) -> dict:
    key = spec["key"]
    output = destination / key
    left = convert_records(cache / spec["left"], output / "left.csv", spec)
    right = (convert_records(cache / spec["right"], output / "right.csv", spec)
             if spec["mode"] == "linkage" else None)
    pairs = set()
    raw_rows = 0
    a, b = spec["truth_columns"]
    with (cache / spec["truth"]).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=spec["delimiter"])
        if not {a, b} <= set(reader.fieldnames or []):
            raise ValueError("Missing ground-truth columns")
        for row in reader:
            raw_rows += 1
            pair = row[a].strip(), row[b].strip()
            if pair[0] not in left["ids"] or pair[1] not in (right or left)["ids"]:
                raise ValueError(f"Unknown ground-truth IDs: {pair}")
            if spec["mode"] == "deduplication":
                if pair[0] == pair[1]:
                    raise ValueError("Ground-truth self-pair")
                pair = tuple(sorted(pair))
            pairs.add(pair)
    with (output / "truth.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["left_id", "right_id"])
        writer.writerows(sorted(pairs))
    truth = read_truth(output / "truth.csv", left["ids"], (right or left)["ids"], spec["mode"])
    counts = [left["rows"], right["rows"] if right else None, len(truth)]
    if counts != spec["expected_counts"]:
        raise ValueError(f"Unexpected data version/counts for {key}: {counts}")
    left.pop("ids")
    if right:
        right.pop("ids")
    return {"dataset": key, "mode": spec["mode"], "counts": counts,
            "paper_counts": spec["paper_counts"], "exact_paper_counts": counts == spec["paper_counts"],
            "raw_truth_rows": raw_rows, "removed_duplicate_truth_rows": raw_rows - len(truth),
            "left": left, "right": right,
            "prepared_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(output.glob("*.csv"))}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download missing sources from the pinned commit")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "configs/benchmark_sources.json").read_text())
    cache = ROOT / "data/raw/pyjedai"
    verify_sources(manifest, cache, args.download)
    configs = ROOT / "configs/benchmarks"
    configs.mkdir(parents=True, exist_ok=True)
    summaries = []
    for spec in manifest["datasets"]:
        summary = prepare_dataset(spec, cache, ROOT / "data/processed")
        summaries.append(summary)
        key = spec["key"]
        config = {
            "name": key, "mode": spec["mode"],
            "left": {"path": f"../../data/processed/{key}/left.csv", "id_column": "id", "text_columns": ["text"]},
            "ground_truth": f"../../data/processed/{key}/truth.csv",
            "candidates": {"ngram": 3, "top_k": 10, "min_score": 0.0, "indexing": "right"},
            "partition": "left", "budget_multipliers": list(range(1, 11)),
            "trace_memory": False,
            "data_provenance": {"repository": manifest["repository"], "commit": manifest["commit"],
                                "paper_counts_match": summary["exact_paper_counts"]},
        }
        if spec["mode"] == "linkage":
            config["right"] = {"path": f"../../data/processed/{key}/right.csv", "id_column": "id", "text_columns": ["text"]}
        (configs / f"{key}.json").write_text(json.dumps(config, indent=2) + "\n")
        print(key, summary["counts"], "paper counts match:", summary["exact_paper_counts"])
    manifest["prepared_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["summaries"] = summaries
    (ROOT / "data/processed/preparation.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
