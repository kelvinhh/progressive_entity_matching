# Progressive Entity Matching

A research paper replication project for **DSC-5003, Track 2**.

This project studies how to prioritize candidate record pairs so that true matches are discovered early under a limited comparison budget.

> **Status:** The first independent implementation is runnable: sparse TF-IDF candidate generation, EC/BFS/DFS/Hybrid scheduling, oracle evaluation, two synthetic demos, and correctness tests. Real benchmark experiments and comparison with published results are pending.

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
| Whole-run traced Python allocation peak | Diagnostic only; per-strategy RSS benchmarks remain pending |

Ground-truth labels may be used to simulate a perfect verifier when evaluating scheduling, consistent with the paper's evaluation setting. This isolates ordering quality from errors made by a learned matcher. It does not demonstrate the accuracy of a deployed matching model.

Correctness checks will cover duplicate candidate removal, budget limits, tie handling, and recall calculations on small examples with known answers. Experiments will record dataset versions, preprocessing, parameters, seeds where applicable, hardware, software versions, and timing boundaries. Ground-truth labels used for evaluation must not leak into candidate scores or scheduling decisions.

## Repository Structure

| Path | Contents |
| --- | --- |
| `src/pem/` | CSV loading, candidate generation, weighting, scheduling, and evaluation |
| `tests/` | Correctness tests and small test fixtures |
| `configs/` | Dataset and experiment configurations |
| `scripts/run_experiment.py` | Experiment entry point |
| `data/` | Dataset acquisition instructions and local data |
| `data/fixtures/` | Original synthetic linkage and deduplication examples |
| `docs/` | Imported discussion notes and implementation plan |
| `references/` | Reference inventory; local paper PDFs and authors' archive are Git ignored |
| `results/` | Location for future curated benchmark results |
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

The experiment runner finds `src/` automatically. Configuration input paths are relative to the configuration file. Copy a demo configuration to prepare a real dataset; see [data format](data/README.md).

Each run writes:

- `metrics.csv`: candidate recall, Recall@B, progressive recall, and timing across strategies and budgets.
- `curves.csv`: recall at each actual verification position, including position zero.
- `orders.csv`: pair ranking, similarity, and oracle outcome for inspection.
- `config.json`: configuration snapshot.
- `metadata.json`: input/source hashes, environment, timing boundaries, and whole-run traced Python allocation peak.

All strategies share the same candidates and scores. Node-centric linkage scheduling uses the configured partition (`left` by default). Ties use string IDs. Progressive recall is the normalized discrete right-step area `sum(R(b), b=1..B)/B`; after candidate exhaustion recall stays constant to B. The exact integration convention is documented, and equivalence to the upstream AUC utility has not yet been verified.

Scheduling time is measured once at the largest configured budget, not independently for each budget. Timings are a single run under `tracemalloc`; the reported peak includes evaluation and output rows and is not a per-strategy RSS measurement. These diagnostics are not yet publication-quality resource benchmarks.

Do not use the upstream repository's installation instructions as if they were setup instructions for this repository; the dependency requirements may differ.

## Data and Results

The included fixtures are synthetic pipeline checks, not evidence of reproducing the paper's findings. Real datasets will be linked to their original sources with attribution and usage terms. Raw datasets, model weights, caches, and large intermediate outputs should remain outside version control.

Only results generated by this implementation will be presented as our replication results. Comparisons with published results will identify differences in datasets, parameters, hardware, and measurement methods.

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

The final report and video links will be added when available.

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
