# Progressive Entity Matching

A research paper replication project for **DSC-5003, Track 2**.

This project studies how to prioritize candidate record pairs so that true matches are discovered early under a limited comparison budget.

> **Status:** Project setup. The scope below is a proposed implementation plan; algorithms, executable experiments, and measured results have not yet been added.

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

We plan to reproduce a focused subset of the paper rather than its entire experimental design space.

- Implement a lightweight candidate generation and similarity weighting pipeline.
- Reimplement and compare the paper's **EC, BFS, DFS, and Hybrid** scheduling strategies.
- Evaluate scheduling strategies on the same candidate pairs and weights for a controlled comparison.
- Use a small selection of labeled entity matching datasets.
- Measure matching effectiveness across comparison budgets, together with preprocessing and scheduling costs.
- Document implementation choices, deviations from the paper, and limitations.

Dataset selection, candidate generation details, and final experiment configurations will be documented as implementation progresses. Any extension beyond the original methods will be identified separately from the replication.

The paper's BFS and DFS strategies schedule candidate neighborhoods; they should not be interpreted as ordinary graph traversal algorithms.

## Evaluation Plan

| Measure | Purpose |
| --- | --- |
| Candidate recall | Check how many ground-truth matches survive candidate generation |
| Recall at budget B | Measure the fraction of all ground-truth matches found after at most B comparisons |
| Progressive recall | Evaluate how early matches are found, following the paper's definition |
| Preprocessing and scheduling time | Account for the work needed before and during candidate ordering |
| Peak memory usage | Assess resource requirements |

Ground-truth labels may be used to simulate a perfect verifier when evaluating scheduling, consistent with the paper's evaluation setting. This isolates ordering quality from errors made by a learned matcher. It does not demonstrate the accuracy of a deployed matching model.

Correctness checks will cover duplicate candidate removal, budget limits, tie handling, and recall calculations on small examples with known answers. Experiments will record dataset versions, preprocessing, parameters, seeds where applicable, hardware, software versions, and timing boundaries. Ground-truth labels used for evaluation must not leak into candidate scores or scheduling decisions.

## Planned Repository Structure

The following directories are planned and will be added with their corresponding implementations:

| Path | Contents |
| --- | --- |
| `src/` | Candidate generation, weighting, scheduling, and evaluation |
| `tests/` | Correctness tests and small test fixtures |
| `configs/` | Dataset and experiment configurations |
| `scripts/` | Data preparation and experiment entry points |
| `data/` | Dataset acquisition instructions and local data |
| `results/` | Selected experiment summaries and figures |
| `report/` | Final report and supporting material |

## Setup and Reproduction

The implementation and dependency specification are not available yet. Installation and experiment commands will be added after they have been verified from a clean environment.

The completed reproduction guide will explain how to:

1. Prepare the supported Python environment and install pinned dependencies.
2. Obtain the selected datasets and verify their expected format.
3. Run the correctness tests.
4. Execute the baseline experiments from saved configurations.
5. Regenerate the reported tables and figures.

Do not use the upstream repository's installation instructions as if they were setup instructions for this repository; the dependency requirements may differ.

## Data and Results

Datasets will be linked to their original sources with attribution and usage terms. Raw datasets, model weights, caches, and large intermediate outputs should remain outside version control. Small synthetic fixtures may be committed for tests.

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
