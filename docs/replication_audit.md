# Paper, reference implementation, and dataset audit

## Evidence and scope

The algorithm specification is Maciejewski et al., *Progressive Entity Matching:
A Design Space Exploration*, [DOI 10.1145/3709715](https://doi.org/10.1145/3709715).
We read the supplied PDF: §3 / PDF page 6 for the objective, §5.2 for sparse
joins, §6 / PDF page 13 for scheduling, and §7.1 / PDF page 14 for counts and budgets.

For an executable cross-check, we retrieved the public pyJedAI sources and data at
commit [`eb446095f921af3207bbefd570cc65e818194419`](https://github.com/AI-team-UoA/pyJedAI/tree/eb446095f921af3207bbefd570cc65e818194419),
on 2026-11-22. The authors' supplied driver imports `pyjedai`, but its dependency
file does not pin a version. Therefore the selected reference is **not established
as the software revision used to produce the paper**.

Source locations and SHA-256 / Git blob hashes are in
[`configs/benchmark_sources.json`](../configs/benchmark_sources.json). All 13 fetched
files matched their Git blob SHA, SHA-256, and expected byte length. Raw data and
reference code remain untracked in `data/raw/pyjedai/`.

## Metric difference

The paper defines progressive recall as a normalized area under a recall curve,
without spelling out all discrete implementation conventions in §3.

| Convention | Our fixed-budget PR@B | Pinned pyJedAI `_generate_auc_data` |
| --- | --- | --- |
| Recall denominator | All unique true pairs | `len(data.ground_truth)`; our adapter passes unique true pairs |
| Area denominator | Configured budget B | Actual emissions L + 1 |
| Candidate exhaustion | Recall held constant until B | No padding after L |
| First emission | Post-verification recall | Post-verification recall at zero-based emission index 0 |
| Early stopping | No label-based early stop | Compatibility check uses default `emit_all_tps_stop=False`, batch size 1 |

See the pinned [evaluation source, lines 295–368](https://github.com/AI-team-UoA/pyJedAI/blob/eb446095f921af3207bbefd570cc65e818194419/src/pyjedai/evaluation.py#L295-L368).

We retain `progressive_recall` as the clearly documented fixed-budget measure and
add `pyjedai_auc` for the pinned routine's convention. The independent integer-sum
implementation was compared against the **actual checksum-verified method**
extracted through Python AST, rather than against another hand-written copy.
Forty cases cover empty orders, missed positives, short/long budgets, and multiple
emission lengths; agreement is within 1e-12. Run `scripts/verify_reference.py`.
The result is recorded in [`results/reference_verification.json`](../results/reference_verification.json).
This establishes metric compatibility in that bounded setting, not full-workflow
or published-number equivalence.

Example: one emitted true match out of two total matches, with budget four,
gives fixed-budget PR=0.5 but pinned pyJedAI AUC=0.25.

## Scheduling difference

Our Hybrid follows §6: gather one best edge per neighborhood, **globally sort
those edges by weight**, then visit remaining edges in node-mean order.
The pinned [`DatasetScheduler._emit_pairs`, lines 535–595](https://github.com/AI-team-UoA/pyJedAI/blob/eb446095f921af3207bbefd570cc65e818194419/src/pyjedai/utils.py#L535-L595)
implements `HB` by emitting each best edge in **node-mean order** without the
global edge-weight sort. These orders can differ.

The verification script executes the pinned scheduler classes in isolation on a
tie-free bipartite fixture. EC/TOP, BFS and DFS agree on that fixture; Hybrid/HB
differs as expected. This is a specific fixture comparison, not an exhaustive
proof of scheduler equivalence. Ties and the handling of bidirectional/undirected
candidate sets remain explicitly defined by our own implementation.

## Real datasets and preparation

| Dataset | Mirror files | Prepared counts | Paper counts | Status |
| --- | --- | --- | --- | --- |
| D1 Restaurants | `data/ccer/D1/{rest1,rest2,gt}.csv` | 339 / 2,256 records; 89 true pairs | Same counts, Table 1 | Count-aligned; identical bytes not established |
| D2 Abt–Buy | `data/ccer/D2/{abt,buy,gt}.csv` | 1,076 / 1,076 records; 1,076 true pairs | Same counts, Table 1 | Count-aligned; identical bytes not established |
| Cora large mirror variant | `data/der/coraLarge/{cora,gt}.csv` | 1,879 records; 62,891 unique pairs | 1,878 records; 62,892 pairs, Table 2 | Explicit variant; no direct numerical replication claim |

The Cora source has 73,147 positive-pair rows. Canonicalizing orientation and
removing duplicates yields 62,891 distinct non-self pairs; all IDs are validated.
We preserve all records. We do not delete a record or fabricate an extra match
to force counts to match the paper.

`prepare_benchmarks.py` keeps source attribute order and concatenates non-ID
values. For Cora, `label` is also excluded as identifier-like metadata. The
normal matching loader then applies the same Unicode/whitespace normalization
used by the synthetic baseline. No transitive closure or new labels are generated.
Each prepared CSV is hashed. The local `data/processed/preparation.json` records
excluded fields, counts, empty texts, and duplicate-label removal.

We use joint-corpus smoothed IDF, positive-overlap top-k, stable string-ID ties,
and the declared partition rule. These are controlled choices, not evidence that
the paper's full candidate generation implementation has been reproduced exactly.

## Terms and unresolved questions

The mirror's [software license](https://github.com/AI-team-UoA/pyJedAI/blob/eb446095f921af3207bbefd570cc65e818194419/LICENSE)
is Apache-2.0. A dataset-specific license for these files was not identified in
the inspected repository material. We do not infer a data redistribution license
from the software license; raw datasets are downloaded locally and are not added
to this repository. Dataset-specific usage terms remain to be resolved/documented.

Remaining provenance questions: the original experimental dependency revision,
the exact original Cora bytes, and dataset-specific terms. None is silently
treated as verified. Current measured results are in
[`results/first_real_data_baseline.md`](../results/first_real_data_baseline.md).
