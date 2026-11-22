#!/usr/bin/env python3
"""Write a source-traceable analysis of the complete grid and measured resources."""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    with (ROOT / "results" / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    sweep = read("sweep_metrics.csv")
    resources = read("resource_summary.csv")
    protocol = json.loads((ROOT / "configs/experiment_protocol.json").read_text())
    groups = defaultdict(list)
    for row in sweep:
        groups[(row["dataset"], row["strategy"], row["setting"])].append(float(row["progressive_recall"]))
    setting_means = {key: statistics.mean(values) for key, values in groups.items()}
    lines = [
        "# Parameter sensitivity and resource measurements", "",
        "## Scope and protocol", "",
        "We executed all 42 predeclared candidate configurations: 18 each for D1 and D2",
        "(3/5-grams × k=1/5/10 × left/right/both indexing), and six for the Cora mirror",
        "variant (3/5-grams × k=1/5/10, undirected union). Each configuration uses the",
        "same candidates and weights for EC, BFS, DFS and Hybrid, with ten budgets",
        "B=i×|truth|. This produces 1,680 metric rows. Scheduling remains on the left",
        "partition for linkage, so changing indexing isolates candidate generation",
        "rather than jointly changing the scheduling partition.", "",
        "The grid is descriptive sensitivity analysis. We do not choose a winning setting",
        "on these labels and claim independent validation. Every setting is reported.", "",
        "Protocol: [experiment_protocol.json](../configs/experiment_protocol.json).",
        "Full results: [sweep_metrics.csv](sweep_metrics.csv); source/input/config hashes:",
        "[sweep_manifest.json](sweep_manifest.json).", "",
        "## Scheduling sensitivity", "",
        "For each setting we average fixed-budget PR across its ten budgets. The table",
        "summarizes those setting-level means. The ranges are variation across chosen",
        "parameters, not sampling uncertainty, confidence intervals, or independent replicates.", "",
        "| Dataset | Strategy | Settings | Minimum | Median | Maximum |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for dataset in protocol["datasets"]:
        for strategy in protocol["strategies"]:
            values = [value for (d, s, _), value in setting_means.items() if d == dataset and s == strategy]
            lines.append(f"| {dataset} | {strategy} | {len(values)} | {min(values):.4f} | {statistics.median(values):.4f} | {max(values):.4f} |")
    lines.extend([
        "", "![Scheduling sensitivity](figures/scheduling_sensitivity.png)", "",
        "![Fixed-baseline progression](figures/baseline_progression.png)", "",
        "## Candidate ceiling and diagnostic cases", "",
        "The candidate-recall ceiling is evaluated against all unique positive pairs.",
        "A scheduler cannot recover positives discarded before scheduling.", "",
        "| Dataset | n-gram | k | Indexing | Candidate pairs | Candidate recall |",
        "| --- | ---: | ---: | --- | ---: | ---: |",
    ])
    examples = {
        ("d1_restaurants", 3, 1, "right"), ("d1_restaurants", 3, 10, "right"),
        ("d2_abt_buy", 3, 10, "right"), ("d2_abt_buy", 3, 10, "both"),
        ("cora_large_variant", 3, 1, "right"), ("cora_large_variant", 3, 5, "right"),
        ("cora_large_variant", 3, 10, "right"), ("cora_large_variant", 5, 10, "right"),
    }
    seen = set()
    for row in sweep:
        key = row["dataset"], int(row["ngram"]), int(row["top_k"]), row["indexing"]
        if key in examples and key not in seen:
            seen.add(key)
            lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {key[3]} | {row['candidate_count']} | {float(row['candidate_recall']):.4f} |")
    orders = ROOT / "outputs/benchmarks/d1_restaurants/orders.csv"
    with orders.open(newline="") as stream:
        first = [r for r in csv.DictReader(stream) if r["strategy"] == "EC"][:89]
    near_perfect = sum(float(r["score"]) > .999999 for r in first)
    true = sum(int(r["is_match"]) for r in first)
    lines.extend([
        "", "![Candidate sensitivity](figures/candidate_sensitivity.png)", "",
        f"**D1 diagnostic:** in the fixed k=10 baseline, {near_perfect} of the first 89 EC pairs",
        f"have cosine above 0.999999, yet only {true} of those 89 comparisons is a true pair.",
        "This is a concrete example of highly similar sparse profiles creating ambiguous",
        "priorities. It explains why a perfect-looking similarity score is not proof of",
        "entity identity. It does not by itself isolate the effect of preprocessing or tie-breaking.", "",
        "**Abt–Buy:** bilateral candidate generation increases recall at k=10 in the",
        "3-gram setting, but also changes the number of candidates and scheduling cost.",
        "This is a candidate-set trade-off, not an isolated improvement in the scheduler.", "",
        "**Cora:** the candidate ceiling rises with k and remains about 16% at k=10.",
        "Switching from 3-grams to 5-grams does not resolve that limitation in this grid.",
        "All ten configured budgets exceed the generated candidate count, so ordinary",
        "recall is flat across those budgets. Differences in fixed-budget PR mainly",
        "reflect the within-candidate ordering plus the explicit constant tail; they",
        "must not be confused with improvements in final recall.", "",
        "## Timing and memory", "",
        "Resource trials use the previously fixed 3-gram, k=10, right-index baseline.",
        "One warm-up block is discarded, followed by five measured blocks. Each block",
        "shuffles all 15 dataset-stage jobs using seed 5003 and executes them sequentially.",
        "Each job starts a fresh Python process with fixed PYTHONHASHSEED. Warm-up warms",
        "OS-level caches; it does not reuse a warmed Python interpreter.", "",
        "Stage timers exclude process startup, imports, input loading, output hashing,",
        "and serialization. Candidate workers load source records; scheduler workers",
        "load an identical serialized candidate snapshot and schedule at the maximum",
        "configured budget. Every worker's output signature is checked against a",
        "reference result before accepting the observation.", "",
        "Memory is full-worker lifetime peak RSS through the stage, normalized from",
        "platform-specific getrusage units to bytes. It includes interpreter, imports,",
        "input parsing, and the input object graph. It is **not incremental algorithm",
        "memory**, and candidate/scheduler workers have different input baselines.", "",
        "| Dataset | Stage | Trials | Median time (ms) | Min–max time (ms) | Median peak RSS (MiB) | Min–max RSS (MiB) |",
        "| --- | --- | ---: | ---: | --- | ---: | --- |",
    ])
    for row in resources:
        lines.append(f"| {row['dataset']} | {row['stage']} | {row['repeats']} | "
                     f"{float(row['seconds_median'])*1000:.2f} | {float(row['seconds_min'])*1000:.2f}–{float(row['seconds_max'])*1000:.2f} | "
                     f"{float(row['peak_rss_mib_median']):.2f} | {float(row['peak_rss_mib_min']):.2f}–{float(row['peak_rss_mib_max']):.2f} |")
    lines.extend([
        "", "![Resource comparison](figures/resource_comparison.png)", "",
        "Intervals are observed min–max ranges across five trials, not confidence",
        "intervals. Timings reflect this machine and its current background load. No",
        "cross-machine speedup, superiority over published code, or statistical significance",
        "is claimed. See [raw measurements](resource_measurements.csv),",
        "[summary](resource_summary.csv), and [protocol/environment/hash manifest](resource_manifest.json).", "",
        "## Relation to the paper", "",
        "Paper §7.3 reports strong BFS results on D2 and a different outcome on D1,",
        "using the best configurations per scheduling method. Our fixed baseline and",
        "complete-grid sensitivity test a different controlled question: scheduling on",
        "the same candidate graph within each setting. The paper's overall best Join",
        "workflow uses character 5-grams, TF-IDF, Euclidean similarity and five neighbors;",
        "our implementation uses cosine and smoothed joint-corpus IDF. The paper's",
        "dependency revision is unpinned in the supplied archive, and its Hybrid text",
        "differs from the currently pinned library code. Cora also uses a mirror variant.", "",
        "Some qualitative behavior is compatible with the paper, but the ranking is",
        "not universally reproduced: on our D2 fixed baseline Hybrid has greater PR",
        "than BFS, and on D1 DFS performs poorly at k=10. A direct numerical claim",
        "would require matching data bytes, candidate generation, indexing/scheduling",
        "context, integration convention, and software version. These results do not",
        "establish that match. See [the source audit](../docs/replication_audit.md).", "",
        "## Remaining work", "",
        "- Resolve original dataset/software provenance and dataset-specific terms where possible.",
        "- If pursuing direct published-number reproduction, add matched weighting/similarity and exact reference settings before making that claim.",
        "- Finish clean-environment validation, team contribution information, final report, and video.",
        "- Treat automatic strategy selection or budget-aware scheduling as optional future work with a separate evaluation protocol.", "",
        "## Reproduce this stage", "", "```bash",
        "python3 scripts/run_sweep.py", "python3 scripts/benchmark_resources.py",
        "# Plotting uses Python 3.12 and requirements_plotting.txt; core experiments use stdlib only.",
        "uv venv .venv_plot --python 3.12",
        "uv pip install --python .venv_plot/bin/python -r requirements_plotting.txt",
        ".venv_plot/bin/python scripts/plot_results.py", "python3 scripts/summarize_stage2.py", "```", "",
    ])
    (ROOT / "results/stage2_analysis.md").write_text("\n".join(lines))
    print("Saved stage-two analysis")


if __name__ == "__main__":
    main()
