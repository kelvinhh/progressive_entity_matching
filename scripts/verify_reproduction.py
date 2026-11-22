#!/usr/bin/env python3
"""Check the stdlib-only core in a fresh source tree/venv using pinned cached data.

This does not test cold network access or installation of plotting dependencies.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Also repeat the complete grid and isolated resource benchmark in the clean environment")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "configs/benchmark_sources.json").read_text())
    with tempfile.TemporaryDirectory(prefix="pem_clean_reproduction_") as temporary:
        clean = Path(temporary)
        for folder in ("src", "scripts", "tests", "configs"):
            shutil.copytree(ROOT / folder, clean / folder, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "data/fixtures", clean / "data/fixtures")
        for entry in manifest["files"]:
            relative = Path("data/raw/pyjedai") / entry["path"]
            source = ROOT / relative
            destination = clean / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        (clean / "results").mkdir()
        environment = dict(os.environ, PYTHONPATH=str(clean / "src"),
                           PYTHONPYCACHEPREFIX=str(clean / "pycache"), PYTHONHASHSEED="0")

        def command(args):
            result = subprocess.run(args, cwd=clean, env=environment, capture_output=True,
                                    text=True, timeout=300)
            if result.returncode:
                raise RuntimeError(f"Reproduction command failed: {args}\n{result.stderr}")
            return result

        command([sys.executable, "-m", "venv", str(clean / "venv"), "--without-pip"])
        python = str(clean / "venv/bin/python")
        runtime = json.loads(command([python, "-c", "import json,sys,importlib.metadata; print(json.dumps({'python':sys.version,'distributions':[d.metadata['Name'] for d in importlib.metadata.distributions()]}))"]).stdout)
        if runtime["distributions"]:
            raise AssertionError(f"Expected empty fresh environment: {runtime['distributions']}")
        tests = command([python, "-m", "unittest", "discover", "-s", "tests", "-v"])
        count = int(re.search(r"Ran (\d+) tests", tests.stderr).group(1))
        command([python, "scripts/prepare_benchmarks.py"])
        command([python, "scripts/verify_reference.py"])
        with (ROOT / "results/fixed_baseline_metrics.csv").open(newline="") as stream:
            expected_rows = list(csv.DictReader(stream))
        actual_rows = []
        for dataset in manifest["datasets"]:
            key = dataset["key"]
            command([python, "scripts/run_experiment.py", "--config", f"configs/benchmarks/{key}.json",
                     "--output", f"outputs/benchmarks/{key}"])
            with (clean / "outputs/benchmarks" / key / "metrics.csv").open(newline="") as stream:
                actual_rows.extend(csv.DictReader(stream))
            print(f"Fresh-environment reproduction: {key}", flush=True)
        identity = lambda row: (row["dataset"], row["strategy"], row["budget"])
        expected = {identity(row): row for row in expected_rows}
        actual = {identity(row): row for row in actual_rows}
        if expected.keys() != actual.keys():
            raise AssertionError("Reproduced settings/budgets do not match")
        fields = ["comparisons", "matches", "recall", "progressive_recall", "pyjedai_auc",
                  "candidate_count", "candidate_recall"]
        max_error = 0.0
        for key in expected:
            for field in fields:
                error = abs(float(expected[key][field]) - float(actual[key][field]))
                max_error = max(error, max_error)
                if error > 1e-12:
                    raise AssertionError((key, field, expected[key][field], actual[key][field]))
        full = None
        if args.full:
            print("Repeating all 42 grid settings in the fresh environment", flush=True)
            command([python, "scripts/run_sweep.py"])
            with (ROOT / "results/sweep_metrics.csv").open(newline="") as stream:
                expected_sweep = {(r["setting"], r["strategy"], r["budget"]): r for r in csv.DictReader(stream)}
            with (clean / "results/sweep_metrics.csv").open(newline="") as stream:
                actual_sweep = {(r["setting"], r["strategy"], r["budget"]): r for r in csv.DictReader(stream)}
            if expected_sweep.keys() != actual_sweep.keys():
                raise AssertionError("Full-grid configuration mismatch")
            sweep_error = max(abs(float(expected_sweep[k][f]) - float(actual_sweep[k][f]))
                              for k in expected_sweep for f in fields)
            if sweep_error > 1e-12:
                raise AssertionError(f"Full-grid metrics differ: {sweep_error}")
            print("Repeating isolated resource jobs in the fresh environment", flush=True)
            command([python, "scripts/benchmark_resources.py"])
            with (clean / "results/resource_measurements.csv").open(newline="") as stream:
                fresh_trials = list(csv.DictReader(stream))
            with (ROOT / "results/resource_measurements.csv").open(newline="") as stream:
                expected_signatures = {(r["dataset"], r["stage"]): r["output_signature"] for r in csv.DictReader(stream)}
            if len(fresh_trials) != 75 or any(row["output_signature"] != expected_signatures[(row["dataset"], row["stage"])] for row in fresh_trials):
                raise AssertionError("Fresh resource measurements or signatures differ")
            full = {"grid_rows_reproduced": len(actual_sweep), "grid_maximum_absolute_error": sweep_error,
                    "resource_measured_jobs_completed": len(fresh_trials),
                    "resource_output_signatures_match": True,
                    "timing_values_compared": False, "rss_values_compared": False}
        verification = {
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime": runtime, "tests_passed": count,
            "metric_rows_reproduced": len(actual), "compared_fields": fields,
            "maximum_absolute_error": max_error, "tolerance": 1e-12,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for folder in ["src", "scripts", "configs", "tests"]
                              for p in sorted((ROOT / folder).rglob("*"))
                              if p.is_file() and "__pycache__" not in p.parts},
            "reference_commit": manifest["commit"],
            "full_run": full,
            "scope": "Fresh copied source tree and venv with no installed distributions or pip; "
                     "pinned cached source files are verified and normalized from scratch; "
                     "all 120 fixed-baseline quality rows reproduced. Timing values are not compared. "
                     "Cold network downloads and plotting-package installation are not covered. "
                     "The optional full_run field records whether the entire grid and resource jobs were also repeated; timing/RSS values are never expected to match exactly.",
        }
    filename = "full_reproduction_verification.json" if args.full else "reproduction_verification.json"
    (ROOT / "results" / filename).write_text(json.dumps(verification, indent=2) + "\n")
    print(f"Verified {count} tests and {len(actual)} metric rows in a fresh stdlib-only venv", flush=True)


if __name__ == "__main__":
    main()
