#!/usr/bin/env python3
"""Portrait report figures with readable font sizes at A4 report width."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ["d1_restaurants", "d2_abt_buy", "cora_large_variant"]
LABELS = ["Restaurants (D1)", "Abt–Buy (D2)", "Cora mirror variant"]
STRATEGIES = ["EC", "BFS", "DFS", "Hybrid"]
COLORS = ["#0072B2", "#E69F00", "#D55E00", "#009E73"]
STYLES = ["-", "--", ":", "-."]


def rows(name):
    with (ROOT / "results" / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def save(fig, name):
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(ROOT / "report/figures" / f"{name}.{suffix}", dpi=220, facecolor="white")
    plt.close(fig)


def main():
    (ROOT / "report/figures").mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 9.5, "legend.fontsize": 8,
                         "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
    baseline, sweep, resource = [rows(name) for name in ("fixed_baseline_metrics.csv", "sweep_metrics.csv", "resource_summary.csv")]
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 8.2), layout="constrained", sharex=True, sharey=True)
    for row, (dataset, label) in enumerate(zip(DATASETS, LABELS)):
        for strategy, color, style in zip(STRATEGIES, COLORS, STYLES):
            group = sorted([r for r in baseline if r["dataset"] == dataset and r["strategy"] == strategy], key=lambda r: int(r["budget"]))
            x = [int(r["budget"]) / int(group[0]["budget"]) for r in group]
            for column, metric in enumerate(("recall", "progressive_recall")):
                axes[row, column].plot(x, [float(r[metric]) for r in group], style, color=color, marker="o", markersize=2.5, label=strategy)
        for column, metric_label in enumerate(("Recall@B", "Fixed-budget PR@B")):
            axes[row, column].set_title(f"{label} — {metric_label}")
            axes[row, column].set_ylim(-.02, 1.04)
            axes[row, column].grid(alpha=.2)
            axes[row, column].set_xticks([1, 2, 4, 6, 8, 10])
        axes[row, 0].axhline(float(group[0]["candidate_recall"]), color="grey", linestyle=(0, (2, 3)), linewidth=.8)
    axes[0, 1].legend(ncol=2, loc="lower right")
    for ax in axes[-1]: ax.set_xlabel("Budget / number of true pairs")
    save(fig, "baseline")

    fig, axes = plt.subplots(3, 2, figsize=(7.2, 8.2), layout="constrained", sharex=True, sharey=True)
    for row, (dataset, label) in enumerate(zip(DATASETS, LABELS)):
        for column, ngram in enumerate((3, 5)):
            directions = ["left", "right", "both"] if row < 2 else ["right"]
            for index, direction in enumerate(directions):
                group = [r for r in sweep if r["dataset"] == dataset and int(r["ngram"]) == ngram and r["indexing"] == direction and r["strategy"] == "EC"]
                values = {int(r["top_k"]): float(r["candidate_recall"]) for r in group}
                axes[row, column].plot(sorted(values), [values[k] for k in sorted(values)], STYLES[index], color=COLORS[index], marker="o", label=direction if row < 2 else "undirected union")
            axes[row, column].set_title(f"{label} — {ngram}-gram")
            axes[row, column].grid(alpha=.2)
            axes[row, column].set_ylim(-.02, 1.04)
            axes[row, column].set_xticks([1, 5, 10])
            axes[row, column].legend(loc="lower right")
        axes[row, 0].set_ylabel("Candidate recall")
    for ax in axes[-1]: ax.set_xlabel("k per query before union")
    save(fig, "candidates")

    fig, axes = plt.subplots(3, 1, figsize=(7.2, 8.2), layout="constrained", sharey=True)
    for ax, dataset, label in zip(axes, DATASETS, LABELS):
        for index, (strategy, color) in enumerate(zip(STRATEGIES, COLORS)):
            settings = {}
            for r in sweep:
                if r["dataset"] == dataset and r["strategy"] == strategy:
                    settings.setdefault(r["setting"], []).append(float(r["progressive_recall"]))
            values = [np.mean(v) for _, v in sorted(settings.items())]
            ax.scatter(index + np.linspace(-.15, .15, len(values)), values, s=18, color=color)
            ax.plot([index - .2, index + .2], [np.median(values)] * 2, color="black", linewidth=1.5)
        ax.set_title(f"{label} — {len(settings)} parameter settings")
        ax.set_xticks(range(4), STRATEGIES)
        ax.set_ylim(-.02, 1.03)
        ax.set_ylabel("Mean PR across budgets")
        ax.grid(axis="y", alpha=.2)
    save(fig, "scheduling")

    fig, axes = plt.subplots(3, 2, figsize=(7.2, 8.2), layout="constrained")
    for row, (dataset, label) in enumerate(zip(DATASETS, LABELS)):
        group = [next(r for r in resource if r["dataset"] == dataset and r["stage"] == stage) for stage in ["candidates", *STRATEGIES]]
        for column, prefix in enumerate(("seconds", "peak_rss_mib")):
            center = np.array([float(r[f"{prefix}_median"]) for r in group])
            low = np.array([float(r[f"{prefix}_min"]) for r in group])
            high = np.array([float(r[f"{prefix}_max"]) for r in group])
            axes[row, column].errorbar(range(5), center, yerr=[center-low, high-center], fmt="o", color="#333333", markersize=4, capsize=3)
            axes[row, column].set_xticks(range(5), ["Candidates", *STRATEGIES], rotation=23)
            axes[row, column].grid(axis="y", alpha=.2)
            if column == 0:
                axes[row, column].set_yscale("log")
                axes[row, column].set_ylabel("Seconds (log scale)")
            else:
                axes[row, column].set_ylim(bottom=0)
                axes[row, column].set_ylabel("Whole-worker peak RSS (MiB)")
            axes[row, column].set_title(label)
    save(fig, "resources")
    (ROOT / "report/figures/metadata.json").write_text(json.dumps({
        "matplotlib": matplotlib.__version__, "numpy": np.__version__,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": {name: hashlib.sha256((ROOT / "results" / name).read_bytes()).hexdigest() for name in ["fixed_baseline_metrics.csv", "sweep_metrics.csv", "resource_summary.csv"]},
        "layout": "Portrait panels intended for A4 width; same measured data as main results figures",
    }, indent=2) + "\n")
    print("Generated four portrait report figures")


if __name__ == "__main__": main()
