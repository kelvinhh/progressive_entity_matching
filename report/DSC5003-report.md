# Progressive Entity Matching: A Focused Replication

DSC-5003 · Track 2 · Technical report · 22 November 2026

TECHNICAL DRAFT — Group identities, actual individual contributions, and human review remain to be completed. Video production and submission are excluded from the current task.

## Abstract

This project independently implements a controlled subset of Progressive Entity Matching: A Design Space Exploration [1]. We study how candidate-pair ordering affects early match discovery under a comparison budget. A sparse character n-gram TF-IDF cosine join supplies candidates to four schedulers: EC, BFS, DFS, and Hybrid. All schedulers receive identical candidates and weights within each configuration. Ground-truth labels simulate a perfect verifier and are excluded from candidate scoring and scheduling.

The evaluation covers two count-aligned linkage benchmarks and a documented Cora deduplication variant. A fixed baseline produces 120 metric rows; the complete 42-setting sensitivity grid produces 1,680 rows. Resource measurements comprise 75 fresh-process trials. On Abt–Buy at 1,076 comparisons, EC recalls 63.85% of true pairs while BFS and Hybrid recall 84.76%. Cora's top-10 candidate recall is only 16.09%, limiting every scheduler. These findings support a bounded replication of scheduling behavior, not an exact reproduction of the full paper's numerical results.

| Completed evidence | Coverage |
| --- | --- |
| Fixed baseline | 3 datasets × 4 schedulers × 10 budgets = 120 rows |
| Sensitivity grid | 42 settings × 4 schedulers × 10 budgets = 1,680 rows |
| Resource trials | 15 dataset/stage groups × 5 measured trials = 75 jobs |
| Correctness and reproduction | 28 tests; 40 upstream AUC checks; complete grid reproduced |

<!-- pagebreak -->

## 1. Group information and contributions

The supplied course slides require all group members' names and undergraduate majors, plus a breakdown of actual contributions [4]. Those details were not supplied for this repository and have not been invented. The table below is deliberately incomplete.

| Name | Undergraduate major |
| --- | --- |
| Not supplied | Not supplied |

| Member | Actual contribution |
| --- | --- |
| Not supplied | Must be confirmed by the team; automated work is not evidence of an individual's contribution. |

ChatGPT/Codex assisted implementation, testing, experimental execution, figure generation, and report drafting in this workspace. Research-writing procedures from Scientific Agent Skills were consulted [5]. Human authors must review the work, verify claims, confirm the contribution statement, and adapt any AI-use disclosure to the course's actual requirements. No course-specific AI policy has been supplied.

## 2. Paper overview and selection motivation

Maciejewski, Nikoletos, Papadakis, and Velegrakis present Progressive Entity Matching: A Design Space Exploration in Proceedings of the ACM on Management of Data, volume 3, issue 1, article 65 (SIGMOD 2025) [1]. The paper organizes progressive matching into filtering, weighting, scheduling, and matching. It evaluates combinations across 10 record-linkage and 8 deduplication datasets; its contribution is a design-space framework and experimental exploration rather than a single learned matching model.

We selected the paper because its scheduling layer supports a focused, testable course replication. Our question is: for a fixed candidate graph and similarity weights, which ordering discovers true pairs earlier? This isolates ordering quality from candidate-generation changes. It differs from selecting the best end-to-end configuration separately for each method, as done in parts of the original study.

The scope includes one lightweight Join-family variant and four static schedulers. It excludes neural embeddings, learned verification, the full Blocking/Sorting design space, streaming ingestion, and entity clustering. A result is a ranked list of candidate pairs, not a deployed matching classifier or an entity-resolution product.

## 3. Technical design and implementation

| Stage | Representation | Implementation |
| --- | --- | --- |
| Filtering | Sparse per-query overlap scores | Character n-gram inverted index; retain positive-score top-k neighbors |
| Weighting | L2-normalized sparse vectors | Joint-corpus smoothed TF-IDF and cosine similarity |
| Scheduling | Weighted candidate edges / neighborhoods | EC, BFS, DFS, or Hybrid, truncated by a verification budget |
| Matching / evaluation | Positive-pair set | Oracle membership lookup; labels read only after candidates are generated |

The code separates CSV validation, candidate generation, scheduling, and evaluation under src/pem/. Experiment scripts save configurations, source/input hashes, ranked pairs, and curves. Raw datasets and reference-library sources remain outside version control. No upstream scheduling or candidate-generation source is copied into the core implementation; reference methods are used only in checksum-verified comparison scripts.

### 3.1 Candidate generation and weighting

Record attributes are concatenated without using column names. IDs are excluded, as is Cora's identifier-like label field. Unicode NFKC normalization, case folding, and whitespace compression are applied consistently. Character n-grams are counted; empty or short texts may yield no candidates rather than fabricated zero-score neighbors.

```text
idf(t) = ln((1 + N) / (1 + df(t))) + 1
w(t,d) = count(t,d) * idf(t)
v(d) = w(d) / ||w(d)||_2
sim(a,b) = dot(v(a), v(b))
```

For linkage, IDF is fitted on the union of both record sources. An inverted index accumulates dot-product scores only for overlapping terms. The top k positive-overlap targets are retained for each query; bilateral indexing unions two directed joins and keeps the maximum score for repeated pairs. For deduplication, each record queries the shared index, self-pairs are excluded, and the undirected top-k lists are canonicalized and unioned. Consequently, final undirected degree can exceed k.

Candidate construction uses sparse dictionaries rather than a dense Cartesian-product matrix. Its work depends on term postings visited by each query and can still approach quadratic behavior on common n-grams. Selecting k targets per query uses a heap-based top-k operation. Vector and graph storage depend on represented terms and retained edges; the implementation does not claim a new asymptotic improvement over the original approach.

### 3.2 Scheduling algorithms and data structures

| Method | Ordering rule |
| --- | --- |
| EC | Globally sort edges by decreasing weight, then retain the budget prefix. |
| DFS | Rank nodes by mean incident-edge weight; exhaust each sorted neighborhood before moving to the next node. |
| BFS | Use the same node ranking, then emit one neighborhood position per node per round. |
| Hybrid | Globally sort each neighborhood's best edge; afterward visit remaining edges in node-mean order. |

EC uses a full sort, costing O(E log E); it does not implement the paper's bounded-heap optimization. Node-centric methods sort nodes and neighborhoods, with O(E + V log V + sum_v degree(v) log degree(v)) work. Lists hold sorted neighborhoods and a set prevents duplicate emissions. Linkage schedules one declared partition (left by default). Deduplication represents both endpoints; duplicate adjacency entries consume their local round position but not a verification-budget slot. Ties use string IDs deterministically.

These BFS and DFS names describe scheduling of candidate neighborhoods, not ordinary traversal of connected components. The ranking is static: verification outcomes do not update it. The implemented Hybrid follows the global first-edge sort in paper §6. The pinned pyJedAI HB routine instead emits first edges in node-mean order. Our audit records this discrepancy rather than silently equating the two variants.

## 4. Correctness validation and metrics

The local suite has 28 passing tests. It checks hand-computed strategy orders, input-order invariance under ties, budget prefixes, undirected duplicate removal, sparse joins against exhaustive cosine calculation, empty/invalid inputs, ID and label isolation, dataset preparation, grid coverage, resource signatures, and end-to-end demos. These checks support implementation correctness on the covered cases; they are not a proof of equivalence to every upstream workflow.

Let T be the set of all unique true pairs, C the generated candidates, and R(b) the fraction of T found after the first b comparisons. Candidate recall is |C ∩ T| / |T|. Recall@B uses the actually available prefix, so missing candidates remain false negatives. The perfect oracle is an evaluation device; it does not measure the accuracy of a real verification model.

```text
Fixed-budget PR@B = (R(1) + ... + R(B)) / B
Pinned pyJedAI AUC = (R(1) + ... + R(L)) / (L + 1)
L = min(B, number of available candidates)
```

For fixed-budget PR, recall stays constant after candidates are exhausted; at B=0 the value is zero. The compatible pyJedAI column has no padded tail and uses actual emissions plus one in the denominator. For example, one true emission out of two total matches with B=4 gives fixed-budget PR=0.5 and compatible AUC=0.25. These are separately named columns and are never interchanged.

The compatible metric was checked on 40 cases against the actual checksum-verified _generate_auc_data method extracted through Python AST, with tolerance 1e-12. A tie-free bipartite fixture also confirms EC/TOP, BFS, and DFS agreement while exposing the expected Hybrid/HB difference. Compatibility is bounded to batch size one and no label-based early-stop mode; the library revision used for the original paper is unknown.

## 5. Experimental setup

| Dataset | Records | Unique true pairs | Relation to paper |
| --- | --- | --- | --- |
| Restaurants (D1) | 339 / 2,256 | 89 | Same counts as Table 1 |
| Abt–Buy (D2) | 1,076 / 1,076 | 1,076 | Same counts as Table 1 |
| Cora mirror variant | 1,879 | 62,891 | Different version from Table 2 |

Inputs are pinned to pyJedAI commit eb446095f921af3207bbefd570cc65e818194419 [3]. File length, Git blob SHA, and SHA-256 are checked before conversion. Cora has 1,879 records and 62,891 distinct positive pairs, versus 1,878 and 62,892 in the paper. Its 73,147 raw label rows contain 10,256 redundant entries after orientation canonicalization. We preserve all records and do not manufacture a match or remove a record to force the published counts.

The fixed baseline uses 3-grams, k=10, cosine, right-side indexing, and left-partition scheduling for linkage. The complete grid tests 3/5-grams, k=1/5/10, and left/right/both indexing: 18 linkage settings per dataset and six deduplication settings. Every setting is reported; labels are used for evaluation, not to claim independently validated tuning. The ten budgets are B=i×|T| for i=1,...,10, following the paper's experimental budget scale.

Resource trials use the fixed baseline. One warm-up block is discarded, followed by five measured blocks; each block shuffles all 15 dataset-stage jobs with seed 5003 and runs them sequentially. Every job starts a new Python process with fixed PYTHONHASHSEED. Candidate workers load source records; scheduler workers load the same candidate snapshot. Output hashes must match the reference ordering before a trial is accepted.

Timing excludes process startup, imports, input loading, hashing, and output serialization. RSS is the full worker lifetime peak through the measured stage, including interpreter and loaded inputs, converted from the platform's getrusage units. The two measures have different boundaries. Min–max ranges summarize five observations; they are not confidence intervals or evidence of five independent datasets.

| Item | Recorded environment |
| --- | --- |
| Experiment Python | 3.9.6 (default, May 22 2026, 11:13:45)  |
| Operating system | macOS-26.7.3-arm64-arm-64bit |
| Architecture | arm64; resource manifest CPU string: arm |
| Core dependencies | Python standard library only |
| Plotting environment | Python 3.12; Matplotlib 3.11.2; NumPy 2.5.5 |
| Resource stage budget | Largest configured budget, measured separately from input loading |

## 6. Results

### 6.1 Fixed baseline and early effectiveness

| Dataset / budget | EC | BFS | DFS | Hybrid |
| --- | --- | --- | --- | --- |
| Restaurants (D1) / B=89 | 0.0112 | 0.0112 | 0.0000 | 0.0899 |
| Abt–Buy (D2) / B=1,076 | 0.6385 | 0.8476 | 0.0994 | 0.8476 |
| Cora mirror variant / B=62,891 | 0.1609 | 0.1609 | 0.1609 | 0.1609 |

Table 1. Recall@B at B equal to all unique true pairs. All schedulers use identical candidates and weights within each dataset. These are measured values, not values copied from the paper.

Abt–Buy shows a clear ordering effect in this fixed configuration: BFS and Hybrid find 84.76% of the 1,076 matches by budget 1,076, compared with EC's 63.85% and DFS's 9.94%. Hybrid has higher fixed-budget PR than BFS at this first budget (0.4515 versus 0.4139). This does not establish a universal ranking or statistical significance.

Restaurants retains all true pairs in the baseline candidate set, but its early ordering is poor. EC finds one true pair in its first 89 comparisons. Of those 89 pairs, 78 have cosine above 0.999999. Repeated sparse profiles therefore create highly ambiguous priorities. This diagnostic shows that high similarity need not imply identity; it does not separately identify a causal effect of preprocessing or tie-breaking.

Cora's candidate recall is 0.1609 with 13,079 retained pairs. Even the smallest configured budget, 62,891, exceeds that candidate count, so final recall is identical for every scheduler across the ten budgets. Fixed-budget PR still reflects how early retained positives appear, followed by the declared constant tail. This is principally a candidate-generation limitation, not evidence that ordering can recover discarded pairs.

<!-- pagebreak -->

![Figure 1. Fixed-baseline progression. Rows correspond to D1, D2, and the Cora mirror variant; columns show Recall@B and fixed-budget PR@B. Dashed gray lines mark candidate-recall ceilings. Recall is held constant after candidates are exhausted. The budget axis is normalized by the number of all unique true pairs.](figures/baseline.png)

Figure 1. Fixed-baseline progression. Rows correspond to D1, D2, and the Cora mirror variant; columns show Recall@B and fixed-budget PR@B. Dashed gray lines mark candidate-recall ceilings. Recall is held constant after candidates are exhausted. The budget axis is normalized by the number of all unique true pairs.

<!-- pagebreak -->

### 6.2 Complete-grid sensitivity

| Dataset | Strategy | Settings | Median mean PR | Range |
| --- | --- | --- | --- | --- |
| Restaurants (D1) | EC | 18 | 0.4954 | 0.4014–0.5903 |
| Restaurants (D1) | BFS | 18 | 0.4524 | 0.3670–0.5903 |
| Restaurants (D1) | DFS | 18 | 0.0010 | 0.0000–0.5903 |
| Restaurants (D1) | Hybrid | 18 | 0.5903 | 0.5711–0.6037 |
| Abt–Buy (D2) | EC | 18 | 0.7303 | 0.6590–0.7838 |
| Abt–Buy (D2) | BFS | 18 | 0.7555 | 0.6590–0.7905 |
| Abt–Buy (D2) | DFS | 18 | 0.4708 | 0.1865–0.7818 |
| Abt–Buy (D2) | Hybrid | 18 | 0.7402 | 0.6590–0.7883 |
| Cora mirror variant | EC | 6 | 0.0876 | 0.0206–0.1569 |
| Cora mirror variant | BFS | 6 | 0.0875 | 0.0206–0.1564 |
| Cora mirror variant | DFS | 6 | 0.0876 | 0.0206–0.1567 |
| Cora mirror variant | Hybrid | 6 | 0.0876 | 0.0206–0.1567 |

Table 2. Each setting first averages fixed-budget PR across ten budgets. Medians and ranges summarize those setting-level averages. The settings and budgets are correlated deterministic conditions, not independent sampling replicates.

The sweep confirms that candidate construction matters. For Abt–Buy with 3-grams and k=10, bilateral indexing raises candidate recall from 0.9870 to 0.9954 while expanding the candidate graph from 10,760 to 14,808 edges. The trade-off includes more candidate and scheduling work; it is not an isolated improvement in a scheduling rule. On Cora, increasing k from one to five to ten raises candidate recall from 0.0208 to 0.0894 to 0.1609. At k=10, using 5-grams instead yields 0.1590 and does not remove the candidate ceiling.

<!-- pagebreak -->

![Figure 2. Candidate-generation sensitivity. Rows are datasets; columns are 3-gram and 5-gram representations. Linkage lines distinguish indexing direction. Cora uses one shared index and undirected top-k union. The vertical scale is shared so that the low Cora ceiling remains visible.](figures/candidates.png)

Figure 2. Candidate-generation sensitivity. Rows are datasets; columns are 3-gram and 5-gram representations. Linkage lines distinguish indexing direction. Cora uses one shared index and undirected top-k union. The vertical scale is shared so that the low Cora ceiling remains visible.

<!-- pagebreak -->

<!-- pagebreak -->

![Figure 3. Scheduling sensitivity. Each dot is one predeclared setting's mean fixed-budget PR across ten budgets; the black segment is the median across settings. D1 and D2 have 18 settings each; Cora has six. These dots are not independent repeats, and the median segments are not confidence intervals.](figures/scheduling.png)

Figure 3. Scheduling sensitivity. Each dot is one predeclared setting's mean fixed-budget PR across ten budgets; the black segment is the median across settings. D1 and D2 have 18 settings each; Cora has six. These dots are not independent repeats, and the median segments are not confidence intervals.

<!-- pagebreak -->

### 6.3 Resource measurements

| Dataset | Stage | Median ms | Observed ms range | Peak RSS MiB |
| --- | --- | --- | --- | --- |
| Restaurants (D1) | candidates | 65.91 | 57.53–69.17 | 30.70 |
| Restaurants (D1) | EC | 1.53 | 1.48–1.56 | 19.91 |
| Restaurants (D1) | BFS | 1.88 | 1.78–1.91 | 19.83 |
| Restaurants (D1) | DFS | 1.76 | 1.67–2.05 | 19.83 |
| Restaurants (D1) | Hybrid | 1.91 | 1.76–1.96 | 19.75 |
| Abt–Buy (D2) | candidates | 983.20 | 933.24–1602.63 | 83.11 |
| Abt–Buy (D2) | EC | 5.13 | 4.84–5.66 | 23.84 |
| Abt–Buy (D2) | BFS | 8.16 | 7.96–10.21 | 24.75 |
| Abt–Buy (D2) | DFS | 7.29 | 7.13–8.63 | 24.59 |
| Abt–Buy (D2) | Hybrid | 7.39 | 7.28–8.00 | 24.75 |
| Cora mirror variant | candidates | 8305.94 | 6841.10–10154.13 | 73.62 |
| Cora mirror variant | EC | 13.70 | 13.26–14.99 | 27.34 |
| Cora mirror variant | BFS | 23.52 | 21.97–25.43 | 28.58 |
| Cora mirror variant | DFS | 20.15 | 19.90–22.60 | 28.48 |
| Cora mirror variant | Hybrid | 21.76 | 20.45–23.82 | 28.59 |

Table 3. Five fresh-process trials per row. Time is measured stage work only. Memory is median full-worker lifetime peak RSS, including interpreter and input loading; it is not additional memory allocated solely by the algorithm. Complete raw ranges and standard deviations are retained in the result CSVs.

On this machine and fixed baseline, candidate generation dominates measured stage time: median construction takes about 66 ms on Restaurants, 983 ms on Abt–Buy, and 8.31 seconds on Cora. Median scheduler times range from about 1.5–1.9 ms, 5.1–8.2 ms, and 13.7–23.5 ms respectively. Changing a scheduler can alter early recall substantially even when its own time is small; total preprocessing cost still has to be considered.

<!-- pagebreak -->

![Figure 4. Resource measurements for the fixed baseline. Left: measured stage duration on a logarithmic scale, excluding input loading and worker startup. Right: whole-worker lifetime peak RSS including interpreter and inputs. Markers are medians; whiskers are observed minima and maxima across five trials. Candidate and scheduling workers have different input baselines.](figures/resources.png)

Figure 4. Resource measurements for the fixed baseline. Left: measured stage duration on a logarithmic scale, excluding input loading and worker startup. Right: whole-worker lifetime peak RSS including interpreter and inputs. Markers are medians; whiskers are observed minima and maxima across five trials. Candidate and scheduling workers have different input baselines.

<!-- pagebreak -->

## 7. Comparison with the paper and limitations

Paper §7.3 reports strong Join-family BFS results on D2 and a different best-method ordering on D1, using per-scheduler selected configurations [1]. Its overall best Join workflow uses character 5-grams, TF-IDF, Euclidean similarity, and five neighbors. Our controlled cosine pipeline asks a narrower question. It does not reproduce the original parameter search, all workflow families, model-based comparisons, or exact figures.

Some qualitative behavior is compatible with the paper, but the ranking is not universally reproduced. Our D2 fixed baseline gives Hybrid greater first-budget PR than BFS, while D1 DFS performs poorly at k=10. The report preserves these outcomes. Differences in input versions, IDF smoothing, similarity function, indexing context, tie handling, Hybrid specification, AUC integration, and dependency revision prevent a direct numerical replication claim.

Generalization is limited to two linkage datasets and a Cora mirror variant. The oracle excludes verification-model errors. The small parameter grid does not establish an optimal method, and no held-out strategy selector is trained. Resource observations depend on this workstation and background load. Full-worker RSS is not incremental algorithm memory, and all resource timers are measured at the maximum configured budget rather than separately at every budget.

The inspected mirror has an Apache-2.0 software license, but a dataset-specific redistribution license was not identified. Raw benchmark data are therefore not bundled in the repository. The original experimental dependency revision and exact original Cora bytes remain unresolved. These are explicit provenance limitations, not silently assumed matches.

## 8. Challenges and lessons learned

The most important lesson is to separate candidate recall from scheduling effectiveness. A candidate generator may retain every match yet order ambiguous pairs badly, as in D1, or discard most positives before any ordering is attempted, as in Cora. Both checks are necessary before interpreting progressive curves.

A second lesson is that a metric name does not guarantee the same integration convention. Checking the actual AUC routine exposed a denominator and exhaustion difference. Checking source against the paper also revealed the Hybrid discrepancy. We kept both the paper-based implementation and the version-specific audit rather than changing conventions to obtain a favorable comparison.

A third lesson is that reproducibility requires executable preprocessing, explicit input versions, deterministic ordering, and measurement boundaries. The pipeline records hashes and retains every declared setting. Repeated timing runs characterize execution variability; they do not supply new independent matching datasets. These controls make failures and limitations reviewable.

## 9. Reproducibility and deliverable links

An independent source tree and fresh virtual environment with no installed packages or pip passed 28 tests, re-prepared checksum-verified cached inputs, and reproduced all 120 fixed-baseline quality rows. The full check additionally reproduced 1,680 grid rows and completed 75 resource jobs with matching output signatures. The maximum grid quality difference was 0.0e+00. Timing and RSS values are not required to match across repetitions.

A separate Python 3.12 environment successfully installed the pinned plotting packages from locally reconstructed cached wheels and generated the report figures. That proves fresh offline installation and execution, not access to PyPI. Direct cold-network requests on this execution host failed at DNS resolution, so network acquisition remains unverified here. The ordinary downloader still uses pinned public URLs and verifies hashes.

```text
python3 scripts/prepare_benchmarks.py --download
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/verify_reference.py
python3 scripts/run_sweep.py
python3 scripts/benchmark_resources.py
python3 scripts/verify_reproduction.py --full
```

The repository README gives the fixed-baseline, plotting, and report rebuild commands. Configurations and result CSVs are versioned; raw datasets, virtual environments, and transient runs are excluded. Each report table is generated from saved CSVs, and report/evidence_registry.json binds report blocks to evidence files and hashes. Human verification is explicitly pending rather than represented as completed.

Project repository: https://github.com/kelvinhh/progressive_entity_matching

The repository URL was reachable through the GitHub branch API at the recorded remote revision. The latest report and experimental additions are local changes and have not been uploaded as part of this task. Video production, video-link insertion, and submission were intentionally excluded.

## 10. References

[1] Jakub Maciejewski, Konstantinos Nikoletos, George Papadakis, and Yannis Velegrakis. 2025. Progressive Entity Matching: A Design Space Exploration. Proceedings of the ACM on Management of Data 3(1), Article 65 (SIGMOD), 25 pages. DOI: 10.1145/3709715.

[2] JacobMaciejewski. PER-Design-Space-Exploration. Authors' public experiment repository. The supplied local archive has no identified commit pin. Accessed 22 November 2026.

[3] AI-team-UoA. pyJedAI. Reference source and benchmark mirror at commit eb446095f921af3207bbefd570cc65e818194419. Accessed 22 November 2026. This pin is not established as the original paper's runtime revision.

[4] DSC5003_1introduction&ER.pdf. Supplied course introduction slides, pages 5–9. Group Project (Tentative), Academic Calendar 2026/27. No submission deadline or later amendment was provided.

[5] Timothy Kassis, Vinayak Agarwal, Yuhuan He, Darshil Patel, and Aubrey M. Brueckner. 2026. Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents. arXiv preprint, arXiv:2609.00065. DOI: 10.48550/arXiv.2609.00065. Cited for research-writing procedure, not as evidence for entity matching results.

## Appendix. Administrative completion fields

| Field | Status / action |
| --- | --- |
| Group names and undergraduate majors | Not supplied. Fill report/team_metadata.json. |
| Individual contributions | Not supplied. Enter actual roles; do not infer credit from automated work. |
| Project code / final filename | Project code not supplied; current filename is DSC5003-report.pdf. |
| Deadline / updated course instructions | Not supplied; supplied project slides are tentative. |
| Video and submission | Excluded by the current instruction; no video link or submission is claimed. |
| Human scientific review | Pending. Machine checks do not replace author review. |
