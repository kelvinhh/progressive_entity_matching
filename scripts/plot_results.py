#!/usr/bin/env python3
"""Export measured baseline, sensitivity, and process-resource figures via Matplotlib."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ["d1_restaurants", "d2_abt_buy", "cora_large_variant"]
TITLES = ["Restaurants (D1)", "Abt–Buy (D2)", "Cora mirror variant"]
STRATEGIES = ["EC", "BFS", "DFS", "Hybrid"]
COLORS = ["#0072B2", "#E69F00", "#D55E00", "#009E73"]
STYLES = ["-", "--", ":", "-."]


def read_csv(name):
    with (ROOT / "results" / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def save(fig, name):
    directory = ROOT / "results/figures"
    directory.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(directory / f"{name}.{suffix}", dpi=200, facecolor="white")
    plt.close(fig)


def baseline_plot(rows):
    fig, axes = plt.subplots(2, 3, figsize=(13.6, 7), layout="constrained", sharex=True, sharey=True)
    for column, (dataset, title) in enumerate(zip(DATASETS, TITLES)):
        for strategy, color, style in zip(STRATEGIES, COLORS, STYLES):
            group = sorted([r for r in rows if r["dataset"] == dataset and r["strategy"] == strategy], key=lambda r: int(r["budget"]))
            first_budget = int(group[0]["budget"])
            x = [int(r["budget"]) / first_budget for r in group]
            for row, metric in enumerate(("recall", "progressive_recall")):
                axes[row, column].plot(x, [float(r[metric]) for r in group], style, color=color, marker="o", markersize=3, label=strategy)
        ceiling = float(group[0]["candidate_recall"])
        axes[0, column].axhline(ceiling, color="#666666", linewidth=1, linestyle=(0, (2, 3)))
        axes[0, column].text(.03, .94, f"Candidate recall: {ceiling:.3f}", transform=axes[0, column].transAxes, va="top", fontsize=9)
        axes[0, column].set_title(title)
        axes[1, column].set_xlabel("Budget / number of true pairs")
        for row in range(2):
            axes[row, column].set_ylim(-.02, 1.05)
            axes[row, column].set_xticks([1, 2, 4, 6, 8, 10])
            axes[row, column].grid(alpha=.2)
    axes[0, 0].set_ylabel("Recall@B")
    axes[1, 0].set_ylabel("Fixed-budget PR@B")
    fig.suptitle("Fixed baseline: character 3-grams, k=10\nRecall held constant after candidate exhaustion", fontsize=13)
    axes[1, 1].legend(ncol=4, loc="upper center", fontsize=9)
    save(fig, "baseline_progression")


def candidate_plot(rows):
    fig, axes = plt.subplots(2, 3, figsize=(13.6, 7), layout="constrained", sharex=True, sharey=True)
    for column, (dataset, title) in enumerate(zip(DATASETS, TITLES)):
        directions = ["left", "right", "both"] if column < 2 else ["right"]
        for row, ngram in enumerate((3, 5)):
            ax = axes[row, column]
            for index, direction in enumerate(directions):
                group = [r for r in rows if r["dataset"] == dataset and int(r["ngram"]) == ngram
                         and r["indexing"] == direction and r["strategy"] == "EC"]
                unique = {int(r["top_k"]): float(r["candidate_recall"]) for r in group}
                x = sorted(unique)
                label = f"Index {direction}" if column < 2 else "Undirected top-k union"
                ax.plot(x, [unique[k] for k in x], STYLES[index], marker="o", color=COLORS[index], label=label)
            ax.set_title(f"{title} · {ngram}-gram")
            ax.set_ylim(-.02, 1.05)
            ax.set_xticks([1, 5, 10])
            ax.grid(alpha=.2)
            if row == 0:
                ax.legend(loc="lower right", fontsize=8)
            else:
                ax.set_xlabel("k (per-query neighbors, before union)")
    axes[0, 0].set_ylabel("Candidate recall")
    axes[1, 0].set_ylabel("Candidate recall")
    fig.suptitle("Candidate-generation sensitivity: every predeclared setting\nLabels used only to measure retained true pairs", fontsize=13)
    save(fig, "candidate_sensitivity")


def scheduling_plot(rows):
    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.5), layout="constrained", sharey=True)
    for ax, dataset, title in zip(axes, DATASETS, TITLES):
        for index, (strategy, color) in enumerate(zip(STRATEGIES, COLORS)):
            settings = {}
            for r in rows:
                if r["dataset"] == dataset and r["strategy"] == strategy:
                    settings.setdefault(r["setting"], []).append(float(r["progressive_recall"]))
            means = [sum(values) / len(values) for _, values in sorted(settings.items())]
            offset = np.linspace(-.17, .17, len(means))
            ax.scatter(index + offset, means, color=color, alpha=.7, s=22)
            ax.plot([index - .2, index + .2], [np.median(means)] * 2, color="black", linewidth=2)
        ax.set_title(f"{title}\n{len(settings)} parameter settings")
        ax.set_xticks(range(4), STRATEGIES)
        ax.set_ylim(-.02, 1.05)
        ax.grid(axis="y", alpha=.2)
    axes[0].set_ylabel("Mean fixed-budget PR across ten budgets")
    fig.suptitle("Scheduling sensitivity across the complete grid\nDots: deterministic settings; black line: median across settings, not a confidence interval", fontsize=12)
    save(fig, "scheduling_sensitivity")


def resources_plot(rows):
    stages = ["candidates", *STRATEGIES]
    fig, axes = plt.subplots(2, 3, figsize=(13.6, 7), layout="constrained")
    for column, (dataset, title) in enumerate(zip(DATASETS, TITLES)):
        ordered = [next(r for r in rows if r["dataset"] == dataset and r["stage"] == stage) for stage in stages]
        for row, prefix, label in [(0, "seconds", "Stage time (seconds, log scale)"),
                                    (1, "peak_rss_mib", "Whole-worker peak RSS (MiB)")]:
            center = np.array([float(r[f"{prefix}_median"]) for r in ordered])
            low = np.array([float(r[f"{prefix}_min"]) for r in ordered])
            high = np.array([float(r[f"{prefix}_max"]) for r in ordered])
            axes[row, column].errorbar(range(5), center, yerr=[center - low, high - center],
                                      fmt="o", color="#333333", capsize=4, markersize=5)
            axes[row, column].set_xticks(range(5), ["Candidates", *STRATEGIES], rotation=18)
            axes[row, column].grid(axis="y", alpha=.2)
            if row == 0:
                axes[row, column].set_yscale("log")
            else:
                axes[row, column].set_ylim(bottom=0)
            if column == 0:
                axes[row, column].set_ylabel(label)
        axes[0, column].set_title(title)
    fig.suptitle("Fixed baseline · 5 isolated trials per stage\nMedian and min–max range; stage timer excludes loading, RSS includes worker startup and input", fontsize=12)
    save(fig, "resource_comparison")


def main():
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.fonttype": "none"})
    names = ["fixed_baseline_metrics.csv", "sweep_metrics.csv", "resource_summary.csv"]
    baseline, sweep, resources = [read_csv(name) for name in names]
    baseline_plot(baseline)
    candidate_plot(sweep)
    scheduling_plot(sweep)
    resources_plot(resources)
    (ROOT / "results/figures/metadata.json").write_text(json.dumps({
        "python": sys.version, "platform": platform.platform(), "matplotlib": matplotlib.__version__,
        "numpy": np.__version__, "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": {name: hashlib.sha256((ROOT / "results" / name).read_bytes()).hexdigest() for name in names},
        "resource_error_bars": "min/max across 5 fresh workers; marker is median, not a confidence interval",
        "sensitivity_points": "All predeclared settings; repeated budgets/settings are not independent data replicates",
    }, indent=2) + "\n")
    print("Exported four figures in PNG, SVG, and PDF")


if __name__ == "__main__":
    main()
