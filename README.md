# Progressive Entity Matching

A research paper replication project for **DSC-5003, Track 2**.

This project studies how to prioritize candidate record pairs so that true matches are discovered early under a limited comparison budget.

> **Status:** The focused replication includes a 42-setting sweep, 75 isolated resource measurements, a full clean-environment rerun, and a 15-page English technical report. Team details and human review remain pending. Video and submission are excluded from the current task; exact published-number reproduction is not claimed.

## Paper

**Progressive Entity Matching: A Design Space Exploration**  
Jakub Maciejewski, Konstantinos Nikoletos, George Papadakis, and Yannis Velegrakis.  
*Proceedings of the ACM on Management of Data*, 3(1), Article 65 (SIGMOD 2025).

- [Paper and DOI](https://doi.org/10.1145/3709715)
- [Authors' implementation](https://github.com/JacobMaciejewski/PER-Design-Space-Exploration)

This is an independent course replication project and is not the authors' official repository.

## Motivation

Entity matching identifies records that refer to the same real-world entity, such as two product listings or two bibliographic entries. Comparing every possible pair can be expensive. Progressive entity matching prioritizes promising pairs and produces partial results as comparisons proceed.

The main question is: **How many true matches can we discover before the comparison budget runs out?**

The paper organizes this process into four stages:

1. **Filtering:** Generate a manageable set of candidate pairs.
2. **Weighting:** Assign similarity scores to the candidates.
3. **Scheduling:** Order the candidates to prioritize likely matches.
4. **Matching:** Verify pairs in the scheduled order.

Here, progressive processing means returning results while processing an existing dataset; it does not inherently imply streaming data ingestion.

## Replication Scope

We reproduce a focused subset of the paper rather than its entire experimental design space.

- Generate candidates using a sparse character n-gram TF-IDF cosine top-k join.
- Independently implement the paper's **EC, BFS, DFS, and Hybrid** scheduling strategies.
- Evaluate scheduling strategies on the same candidate pairs and weights for a controlled comparison.
- Use a small selection of labeled entity matching datasets.
- Measure matching effectiveness across comparison budgets, together with preprocessing and scheduling costs.
- Document implementation choices, deviations from the paper, and limitations.

The implementation supports both cross-table linkage and single-table deduplication. See [implementation decisions and remaining work](docs/implementation_plan.md) for exact conventions, deviations, and benchmark plans. Any extension beyond the original methods will be identified separately from the replication.

The paper's BFS and DFS strategies schedule candidate neighborhoods; they should not be interpreted as ordinary graph traversal algorithms.

## Evaluation Plan

| Measure | Purpose |
| --- | --- |
| Candidate recall | Check how many ground-truth matches survive candidate generation |
| Recall at budget B | Measure the fraction of all ground-truth matches found after at most B comparisons |
| Progressive recall | Evaluate how early matches are found, following the paper's definition |
| Preprocessing and scheduling time | Account for the work needed before and during candidate ordering |
| Whole-worker peak process RSS | Five fresh-process trials per stage; includes interpreter and input loading |

Ground-truth labels may be used to simulate a perfect verifier when evaluating scheduling, consistent with the paper's evaluation setting. This isolates ordering quality from errors made by a learned matcher. It does not demonstrate the accuracy of a deployed matching model.

Correctness checks cover duplicate candidate removal, budget limits, tie handling, recall calculations, benchmark preparation, and budget multipliers. Experiments record dataset versions, preprocessing, parameters, seeds where applicable, hardware, software versions, and timing boundaries. Ground-truth labels used for evaluation must not leak into candidate scores or scheduling decisions.

## Repository Structure

| Path | Contents |
| --- | --- |
| `src/pem/` | CSV loading, candidate generation, weighting, scheduling, and evaluation |
| `tests/` | Correctness tests and small test fixtures |
| `configs/` | Dataset and experiment configurations |
| `scripts/` | Benchmark preparation, experiment runner, reference checks, and result summary |
| `data/` | Dataset acquisition instructions and local data |
| `data/fixtures/` | Original synthetic linkage and deduplication examples |
| `docs/` | Imported discussion notes and implementation plan |
| `references/` | Reference inventory; local paper PDFs and authors' archive are Git ignored |
| `results/` | First curated benchmark results, provenance, and reference verification |
| `report/` | Technical report PDF, Markdown/HTML, portrait figures, evidence registry, and completion checks |
| `outputs/` | Generated runs, Git ignored |

## Setup and Reproduction

Requires **Python 3.9+**. The baseline uses only the standard library; no model downloads, Docker, or third-party packages are required. Run from the repository root:

```bash
# Correctness tests
PYTHONPATH=src python3 -m unittest discover -s tests -v

# Cross-table linkage demo
python3 scripts/run_experiment.py --config configs/demo_linkage.json --output outputs/demo_linkage

# Single-table deduplication demo
python3 scripts/run_experiment.py --config configs/demo_deduplication.json --output outputs/demo_deduplication
```

For the first real-data baseline:

```bash
# Sources are checksum-verified and pinned to a specific public repository commit.
python3 scripts/prepare_benchmarks.py --download
python3 scripts/verify_reference.py
for dataset in d1_restaurants d2_abt_buy cora_large_variant; do
    python3 scripts/run_experiment.py --config "configs/benchmarks/${dataset}.json" --output "outputs/benchmarks/${dataset}"
done
python3 scripts/summarize_benchmarks.py
```

Without `--download`, preparation validates and reuses cached sources offline.
Real configurations derive ten budgets using `budget_multipliers = [1, ..., 10]`
times the number of unique true pairs. Cora is explicitly labeled a mirror variant
because its counts differ from the paper.

The experiment runner finds `src/` automatically. Configuration input paths are relative to the configuration file. See [data format and acquisition](data/README.md).

Each run writes:

- `metrics.csv`: candidate recall, Recall@B, fixed-budget progressive recall, pinned pyJedAI-compatible AUC, and timing across strategies and budgets.
- `curves.csv`: recall at each actual verification position, including position zero.
- `orders.csv`: pair ranking, similarity, and oracle outcome for inspection.
- `config.json`: configuration snapshot.
- `metadata.json`: input/source hashes, environment, timing boundaries, and whole-run traced Python allocation peak.

All strategies share the same candidates and scores. Node-centric linkage scheduling uses the configured partition (`left` by default). Ties use string IDs. `progressive_recall` is `sum(R(b), b=1..B)/B`, with a constant tail after exhaustion. The separate `pyjedai_auc` uses actual emissions L and denominator L+1, without padding. It agrees with the actual pinned upstream method in 40 reference cases; the original experimental dependency version is unknown. See the [audit](docs/replication_audit.md) for metric and Hybrid scheduling differences.

Scheduling time is measured once at the largest configured budget, not independently for each budget. Timings are single-run diagnostics. Synthetic demos enable `tracemalloc`; real baseline configurations disable it. When enabled, the peak includes evaluation and output rows and is not a per-strategy RSS measurement. These diagnostics are not yet publication-quality resource benchmarks.

For parameter sensitivity and resource benchmarks:

```bash
python3 scripts/run_sweep.py
python3 scripts/benchmark_resources.py
```

The predeclared [protocol](configs/experiment_protocol.json) fixes the full grid,
selection policy, repetition count, and randomized sequential job order. All
settings are retained. Resource trials use separate processes and verify their
output signatures; stage timers exclude loading and process startup, whereas RSS
includes the worker's full lifetime through the stage. Intervals are observed
min–max ranges, not confidence intervals.

Plotting is optional and uses a separate **Python 3.12** environment:

```bash
uv venv .venv_plot --python 3.12
uv pip install --python .venv_plot/bin/python -r requirements_plotting.txt
.venv_plot/bin/python scripts/plot_results.py
python3 scripts/summarize_stage2.py
```

Four figures are saved in PNG, SVG, and PDF. The plotted results are measured
data, not generated illustrations. The current plotting run used the pinned
packages already cached on this machine; cold package installation remains
unverified. Core experiment commands still need only Python's standard library.

```bash
# Fresh source tree and empty venv; re-prepare pinned cached inputs and compare baseline quality.
python3 scripts/verify_reproduction.py

# Also repeat all 42 settings and 75 isolated resource jobs.
python3 scripts/verify_reproduction.py --full
```

The default check covers core tests, reference verification, and 120 fixed-baseline
rows. The completed `--full` run additionally reproduced all 1,680 grid rows and
completed 75 resource jobs with matching output signatures. A separate fresh
environment successfully installed plotting/PDF-check packages from cached wheels
and generated report figures. Cold network access/online dependency resolution
remain unverified because this host failed DNS resolution.

Do not use the upstream repository's installation instructions as if they were setup instructions for this repository; the dependency requirements may differ.

## Data and Results

Fixtures are synthetic pipeline checks. The real-data baseline uses D1 Restaurants, D2 Abt–Buy, and a Cora mirror variant. See [data acquisition and terms](data/README.md), [first measured results](results/first_real_data_baseline.md), and [replication audit](docs/replication_audit.md). Dataset-specific usage terms remain unresolved; raw data and reference code stay outside version control.

Only results generated by this implementation will be presented as our replication results. Comparisons with published results will identify differences in datasets, parameters, hardware, and measurement methods.

| Output | Contents |
| --- | --- |
| [Stage-two analysis](results/stage2_analysis.md) | Sensitivity, diagnostics, resource tables, four figures, and comparison limits |
| [Sweep metrics](results/sweep_metrics.csv) | All 42 configurations × four strategies × ten budgets |
| [Resource summary](results/resource_summary.csv) | Medians and observed ranges across five isolated trials per stage |
| [Figures](results/figures/) | Baseline progression, candidate sensitivity, scheduling sensitivity, and resources |
| [Reproduction verification](results/reproduction_verification.json) | Fresh-environment baseline quality check and recorded scope |
| [Full reproduction verification](results/full_reproduction_verification.json) | Complete grid/resource rerun in a fresh stdlib-only environment |
| [English technical report](report/DSC5003-report.pdf) | 15-page report; human/team information pending |
| [Report rebuild and checklist](report/README.md) | Source, evidence, PDF validation, metadata, and explicit scope exclusions |

## TODO and Research Workflow

This is a research paper replication project. Use research skills for paper-related
work: `research-lookup` for literature discovery and source retrieval, and
`scientific-critical-thinking` for experimental design and evidence appraisal.
Ground algorithm definitions in the original paper and identify source locations.
Keep published results, our measured results, and proposed extensions distinct.
Routine edits to existing project notes do not require a new literature search.

### Completed Baseline

- [x] Organize the paper, discussion notes, and authors' reference archive.
- [x] Implement CSV loading and sparse character n-gram TF-IDF candidate generation.
- [x] Independently implement EC, BFS, DFS, and Hybrid scheduling.
- [x] Implement oracle evaluation, multi-budget metrics, and experiment metadata.
- [x] Add correctness tests and runnable synthetic linkage/deduplication demos.

### P0 — Real Data and Evaluation Alignment

- [x] Acquire three labeled real datasets covering linkage and deduplication; identify Cora as a mirror variant rather than an exact paper dataset.
- [x] Pin source versions and hashes, record preprocessing, and add repeatable conversion scripts with input validation.
- [x] Check the pinned reference's AUC method; document differences and verify 40 cases against the actual method.
- [x] Audit paper-versus-code scheduling and record candidate-generation conventions, with section/code references and a fixture demonstrating the Hybrid discrepancy.
- [x] Add real-data configurations and the paper's budgets `B = i * |ground_truth|` for `i = 1, ..., 10`.
- [x] Run the first four-strategy comparisons on identical candidates and weights, recording candidate recall; save 120 metric rows.
- [ ] Resolve dataset-specific usage terms; the mirror's software license is not assumed to cover benchmark data.
- [ ] Identify the original experimental dependency revision and exact original Cora data, if obtainable; otherwise retain these limitations in the final comparison.

### P1 — Experiments and Analysis

- [x] Run the 42-setting character 3/5-gram, `k = 1/5/10`, and indexing-direction grid; save all 1,680 metric rows and configuration/input/source provenance.
- [x] Keep the fixed baseline separate from the grid; report descriptive sensitivity without selecting a label-tuned setting as independently validated.
- [x] Measure candidate generation and scheduling in randomized sequential blocks: one discarded warm-up block and five measured blocks, using fresh workers.
- [x] Measure full-worker peak process RSS per strategy, including its input-loading baseline; keep it distinct from incremental algorithm memory and Python allocation tracing.
- [x] Export Recall@B/PR curves, sensitivity figures, and timing/memory tables from saved outputs; inspect all four figures.
- [x] Compare bounded findings with paper §7.3 and explain settings that prevent a direct numerical comparison; exact published-number reproduction remains outside this completed comparison.
- [x] Analyze D1's ambiguous high scores, D2's candidate-set trade-off, and Cora's candidate-recall ceiling; keep observations separate from causal explanations.
- [x] Save complete grid/resource results, figures, provenance, and the remaining limitations of the focused replication.

Repeated timing runs measure execution variability; they do not constitute additional
independent datasets or new evidence of matching effectiveness.

### P2 — Reproduction and Course Submission

- [x] Verify 26 tests, all 120 baseline quality rows, all 1,680 grid rows, and 75 resource jobs in a fresh source tree and empty venv using checksum-verified cached inputs.
- [x] Verify fresh offline wheel installation of the pinned plotting/PDF-check dependencies and generate report figures.
- [ ] Cold external dataset acquisition and online dependency resolution: attempted, but blocked by execution-host DNS resolution failure; no success is claimed.
- [x] Generate `report/DSC5003-report.pdf`, Markdown, standalone HTML, and reproducible source, covering all technical report sections, measured results, limitations, references, and explicit administrative fields.
- [x] Validate PDF text/tables, layout, figures, evidence hashes, reproduction artifacts, and local links; verify the repository URL through authenticated GitHub API read access.
- [ ] Team action: supply actual names, undergraduate majors, contributions, project code if assigned, deadline, and later course instructions; finish human review. These fields remain explicitly unfilled.
- [ ] Video production and video-link insertion: excluded by the current user request.
- [ ] Submission: excluded by the current user request. No commit, push, upload, or course submission is performed.

### Optional Extension — After the Baseline Experiments

- [ ] Investigate budget-aware scheduling or graph-based strategy selection with a prespecified evaluation protocol and fair fixed-strategy baselines; label this as our extension rather than an original paper contribution.

Current handoff: [technical report](report/DSC5003-report.pdf) and [P2 completion checklist](report/completion_checklist.md). Remaining human information and excluded actions are listed separately.
See [implementation decisions](docs/implementation_plan.md) for current conventions.

## Team Workflow

- Work on feature branches and submit pull requests for review.
- Keep changes focused and document meaningful implementation decisions.
- Add correctness checks alongside algorithm implementations.
- Record each member's actual contributions for the final report.

Team members and contribution details will be added once confirmed.

## Course Deliverables

- **Source code (30%):** Original core implementation, tests, evaluation code, data access instructions, and reproducible documentation.
- **Video demonstration (20%):** An 8–10 minute explanation of the paper, implementation, and experimental results. The accessible video link will be included in the final report.
- **Written report (50%):** Paper overview, implementation strategy, correctness validation, experimental setup and results, deviations, limitations, contribution statement, references, and deliverable links.

The [technical report PDF](report/DSC5003-report.pdf) is available with
[Markdown](report/DSC5003-report.md), [HTML](report/DSC5003-report.html), and
[rebuild instructions](report/README.md). Its technical content is complete for
this focused replication, while team information and human review remain pending.
Video and submission are excluded from the current scope.

## Attribution

The original paper and authors' repository are the main references. Any reused or adapted code must be explicitly attributed and comply with its applicable license. Our implementation, adapted components, and upstream baselines will be clearly distinguished.

```bibtex
@article{maciejewski2025progressive,
  author = {Maciejewski, Jakub and Nikoletos, Konstantinos and
            Papadakis, George and Velegrakis, Yannis},
  title = {Progressive Entity Matching: A Design Space Exploration},
  journal = {Proceedings of the ACM on Management of Data},
  volume = {3},
  number = {1},
  articleno = {65},
  year = {2025},
  doi = {10.1145/3709715}
}
```
