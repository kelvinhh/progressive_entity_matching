#!/usr/bin/env python3
"""Curate measured fixed-configuration runs into versioned tables and provenance."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    manifest = json.loads((ROOT / "configs/benchmark_sources.json").read_text())
    rows = []
    metadata_dir = ROOT / "results/fixed_baseline_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    for dataset in manifest["datasets"]:
        key = dataset["key"]
        run = ROOT / "outputs/benchmarks" / key
        with (run / "metrics.csv").open(newline="") as stream:
            rows.extend(csv.DictReader(stream))
        shutil.copyfile(run / "metadata.json", metadata_dir / f"{key}.json")
    with (ROOT / "results/fixed_baseline_metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# First real-data baseline", "",
        "These are measured results of our independent implementation, using one fixed",
        "configuration chosen before examining real-data scores: character 3-grams,",
        "smoothed TF-IDF cosine, k=10, right-side indexing and left-partition scheduling",
        "for linkage; undirected top-k union for deduplication. No parameter tuning was",
        "performed for this table. All four strategies share candidates and weights.", "",
        "## Data checks", "",
        "| Dataset | Left records | Right records | Unique true pairs | Candidate pairs | Candidate recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for dataset in manifest["datasets"]:
        key = dataset["key"]
        metadata = json.loads((metadata_dir / f"{key}.json").read_text())
        lines.append(f"| {key} | {metadata['left_records']} | {metadata['right_records'] or '—'} | "
                     f"{metadata['ground_truth_pairs']} | {metadata['candidate_count']} | {metadata['candidate_recall']:.4f} |")
    lines.extend([
        "", "D1 and D2 counts agree with paper Table 1; this alone does not establish identical bytes.",
        "Cora is explicitly a mirror variant: 1,879 records / 62,891 unique positive pairs",
        "versus the paper's 1,878 / 62,892. Its 73,147 label rows include 10,256",
        "duplicate/reversed pairs, which are canonicalized. The `label` field is excluded",
        "from text to avoid using identifier-like metadata as a matching feature.", "",
        "## At B = number of true pairs", "",
        "| Dataset | Strategy | Budget | Actual comparisons | Recall@B | PR@B (fixed budget) | pyJedAI-compatible AUC |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in rows:
        key = row["dataset"]
        truth_count = next(x["expected_counts"][2] for x in manifest["datasets"] if x["key"] == key)
        if int(row["budget"]) == truth_count:
            lines.append(f"| {key} | {row['strategy']} | {row['budget']} | {row['comparisons']} | "
                         f"{float(row['recall']):.4f} | {float(row['progressive_recall']):.4f} | "
                         f"{float(row['pyjedai_auc']):.4f} |")
    lines.extend([
        "", "## Interpretation and limits", "",
        "- Abt–Buy: at B=1,076, BFS and Hybrid find more true matches than EC in this fixed configuration; Hybrid has the higher progressive recall. This is a result for this configuration, not a general ranking.",
        "- Restaurants: very low early recall despite full candidate recall shows that retaining true pairs does not ensure a good early ordering. The source has sparse records and many repeated values; the causal reason for the ranking still needs diagnostic experiments.",
        "- Cora: top-10 generation retains only about 16.1% of labeled pairs. All schedulers are limited by this ceiling. Each configured budget exceeds the number of generated candidates, so final recall is the same for all four strategies. Smaller diagnostic budgets or larger k are needed to examine early ordering more closely.",
        "- PR@B averages post-verification recall over the configured budget, with a constant tail after exhaustion. pyJedAI-compatible AUC averages over actual emissions with denominator L+1 and no tail. These columns answer different questions and must not be interchanged.",
        "- These runs use the paper's scheduling description. Hybrid differs from the pinned library implementation; see the audit. The pin is not known to be the version used in the paper.",
        "- Timings in the CSV are single-run diagnostics with memory tracing disabled. No resource advantage or statistical significance is claimed. Independent RSS and repeated timing measurements are pending.",
        "- Real-data results do not yet reproduce the paper's parameter search, all workflow families, or its full result figures.", "",
        "## Reproduce", "", "```bash",
        "python3 scripts/prepare_benchmarks.py --download",
        "python3 scripts/verify_reference.py",
    ])
    for dataset in manifest["datasets"]:
        key = dataset["key"]
        lines.append(f"python3 scripts/run_experiment.py --config configs/benchmarks/{key}.json --output outputs/benchmarks/{key}")
    lines.extend(["python3 scripts/summarize_benchmarks.py", "```", "",
                  "Full ten-budget results: [fixed_baseline_metrics.csv](fixed_baseline_metrics.csv).",
                  "Input and source hashes: [metadata](fixed_baseline_metadata/).",
                  "Method/source differences: [replication audit](../docs/replication_audit.md).", ""])
    (ROOT / "results/first_real_data_baseline.md").write_text("\n".join(lines))
    print(f"Curated {len(rows)} measured metric rows")


if __name__ == "__main__":
    main()
