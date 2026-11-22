#!/usr/bin/env python3
"""Build the course technical report from measured result tables and explicit team metadata.

Outputs JSON for the native renderer, editable Markdown, a standalone HTML copy,
and an evidence ledger. No author identities, contributions, deadlines, or results
are inferred. The document remains a technical draft pending human review.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


def read_csv(path):
    with (ROOT / path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def main():
    team = json.loads((HERE / "team_metadata.json").read_text())
    baseline = read_csv("results/fixed_baseline_metrics.csv")
    sweep = read_csv("results/sweep_metrics.csv")
    resources = read_csv("results/resource_summary.csv")
    reference = json.loads((ROOT / "results/reference_verification.json").read_text())
    reproduction_path = ROOT / "results/full_reproduction_verification.json"
    reproduction = json.loads(reproduction_path.read_text())
    environment = json.loads((ROOT / "results/resource_manifest.json").read_text())
    data_manifest = json.loads((ROOT / "configs/benchmark_sources.json").read_text())
    if len(baseline) != 120 or len(sweep) != 1680:
        raise ValueError("Unexpected experiment coverage; update the report specification before building")
    if not reproduction.get("full_run") or reproduction["full_run"]["grid_rows_reproduced"] != len(sweep):
        raise ValueError("Full clean-environment verification is required for this report's reproduction statement")
    blocks = []

    def add(kind, text=None, evidence=(), **kwargs):
        block = {"type": kind, **kwargs}
        if text is not None: block["text"] = text
        if evidence: block["evidence"] = list(evidence)
        blocks.append(block)

    def h(text): add("heading", text)
    def sh(text): add("subheading", text)
    def p(text, *evidence): add("paragraph", text, evidence)
    def note(text, *evidence): add("note", text, evidence)
    def table(rows, widths, *evidence): add("table", rows=rows, widths=widths, evidence=evidence)
    def page(): add("pagebreak")
    def code(text, *evidence): add("code", text, evidence)
    def figure(name, caption, *evidence):
        page()
        add("figure", source=f"figures/{name}.png", caption=caption, evidence=evidence)
        page()

    add("title", "Progressive Entity Matching:\nA Focused Replication")
    add("subtitle", "DSC-5003 · Track 2 · Technical report · 22 November 2026")
    note("TECHNICAL DRAFT — Group identities, actual individual contributions, and human review remain to be completed. Video production and submission are excluded from the current task.", "E12", "E15")
    h("Abstract")
    p("This project independently implements a controlled subset of Progressive Entity Matching: A Design Space Exploration [1]. We study how candidate-pair ordering affects early match discovery under a comparison budget. A sparse character n-gram TF-IDF cosine join supplies candidates to four schedulers: EC, BFS, DFS, and Hybrid. All schedulers receive identical candidates and weights within each configuration. Ground-truth labels simulate a perfect verifier and are excluded from candidate scoring and scheduling.", "E1", "E9")
    p("The evaluation covers two count-aligned linkage benchmarks and a documented Cora deduplication variant. A fixed baseline produces 120 metric rows; the complete 42-setting sensitivity grid produces 1,680 rows. Resource measurements comprise 75 fresh-process trials. On Abt–Buy at 1,076 comparisons, EC recalls 63.85% of true pairs while BFS and Hybrid recall 84.76%. Cora's top-10 candidate recall is only 16.09%, limiting every scheduler. These findings support a bounded replication of scheduling behavior, not an exact reproduction of the full paper's numerical results.", "E3", "E4", "E5", "E14")
    table([["Completed evidence", "Coverage"], ["Fixed baseline", "3 datasets × 4 schedulers × 10 budgets = 120 rows"], ["Sensitivity grid", "42 settings × 4 schedulers × 10 budgets = 1,680 rows"], ["Resource trials", "15 dataset/stage groups × 5 measured trials = 75 jobs"], ["Correctness and reproduction", f"{reproduction['tests_passed']} tests; {reference['verified_cases']} upstream AUC checks; complete grid reproduced"]], [1, 2.4], "E3", "E4", "E5", "E7", "E8")

    page()
    h("1. Group information and contributions")
    p("The supplied course slides require all group members' names and undergraduate majors, plus a breakdown of actual contributions [4]. Those details were not supplied for this repository and have not been invented. The table below is deliberately incomplete.", "E2", "E12")
    member_rows = [["Name", "Undergraduate major"]]
    member_rows += [[m["name"], m["undergraduate_major"]] for m in team["members"]] or [["Not supplied", "Not supplied"]]
    table(member_rows, [1, 1.5], "E12")
    contribution_rows = [["Member", "Actual contribution"]]
    contribution_rows += [[m["name"], m["actual_contribution"]] for m in team["contributions"]] or [["Not supplied", "Must be confirmed by the team; automated work is not evidence of an individual's contribution."]]
    table(contribution_rows, [1, 2.5], "E12")
    p("ChatGPT/Codex assisted implementation, testing, experimental execution, figure generation, and report drafting in this workspace. Research-writing procedures from Scientific Agent Skills were consulted [5]. Human authors must review the work, verify claims, confirm the contribution statement, and adapt any AI-use disclosure to the course's actual requirements. No course-specific AI policy has been supplied.", "E9", "E12", "E13")

    h("2. Paper overview and selection motivation")
    p("Maciejewski, Nikoletos, Papadakis, and Velegrakis present Progressive Entity Matching: A Design Space Exploration in Proceedings of the ACM on Management of Data, volume 3, issue 1, article 65 (SIGMOD 2025) [1]. The paper organizes progressive matching into filtering, weighting, scheduling, and matching. It evaluates combinations across 10 record-linkage and 8 deduplication datasets; its contribution is a design-space framework and experimental exploration rather than a single learned matching model.", "E1")
    p("We selected the paper because its scheduling layer supports a focused, testable course replication. Our question is: for a fixed candidate graph and similarity weights, which ordering discovers true pairs earlier? This isolates ordering quality from candidate-generation changes. It differs from selecting the best end-to-end configuration separately for each method, as done in parts of the original study.", "E1", "E9", "E4")
    p("The scope includes one lightweight Join-family variant and four static schedulers. It excludes neural embeddings, learned verification, the full Blocking/Sorting design space, streaming ingestion, and entity clustering. A result is a ranked list of candidate pairs, not a deployed matching classifier or an entity-resolution product.", "E9")

    h("3. Technical design and implementation")
    table([["Stage", "Representation", "Implementation"], ["Filtering", "Sparse per-query overlap scores", "Character n-gram inverted index; retain positive-score top-k neighbors"], ["Weighting", "L2-normalized sparse vectors", "Joint-corpus smoothed TF-IDF and cosine similarity"], ["Scheduling", "Weighted candidate edges / neighborhoods", "EC, BFS, DFS, or Hybrid, truncated by a verification budget"], ["Matching / evaluation", "Positive-pair set", "Oracle membership lookup; labels read only after candidates are generated"]], [0.65, 1.15, 2.2], "E9")
    p("The code separates CSV validation, candidate generation, scheduling, and evaluation under src/pem/. Experiment scripts save configurations, source/input hashes, ranked pairs, and curves. Raw datasets and reference-library sources remain outside version control. No upstream scheduling or candidate-generation source is copied into the core implementation; reference methods are used only in checksum-verified comparison scripts.", "E9", "E7", "E14")

    sh("3.1 Candidate generation and weighting")
    p("Record attributes are concatenated without using column names. IDs are excluded, as is Cora's identifier-like label field. Unicode NFKC normalization, case folding, and whitespace compression are applied consistently. Character n-grams are counted; empty or short texts may yield no candidates rather than fabricated zero-score neighbors.", "E9", "E14")
    code("idf(t) = ln((1 + N) / (1 + df(t))) + 1\nw(t,d) = count(t,d) * idf(t)\nv(d) = w(d) / ||w(d)||_2\nsim(a,b) = dot(v(a), v(b))", "E9")
    p("For linkage, IDF is fitted on the union of both record sources. An inverted index accumulates dot-product scores only for overlapping terms. The top k positive-overlap targets are retained for each query; bilateral indexing unions two directed joins and keeps the maximum score for repeated pairs. For deduplication, each record queries the shared index, self-pairs are excluded, and the undirected top-k lists are canonicalized and unioned. Consequently, final undirected degree can exceed k.", "E9")
    p("Candidate construction uses sparse dictionaries rather than a dense Cartesian-product matrix. Its work depends on term postings visited by each query and can still approach quadratic behavior on common n-grams. Selecting k targets per query uses a heap-based top-k operation. Vector and graph storage depend on represented terms and retained edges; the implementation does not claim a new asymptotic improvement over the original approach.", "E9")

    sh("3.2 Scheduling algorithms and data structures")
    table([["Method", "Ordering rule"], ["EC", "Globally sort edges by decreasing weight, then retain the budget prefix."], ["DFS", "Rank nodes by mean incident-edge weight; exhaust each sorted neighborhood before moving to the next node."], ["BFS", "Use the same node ranking, then emit one neighborhood position per node per round."], ["Hybrid", "Globally sort each neighborhood's best edge; afterward visit remaining edges in node-mean order."]], [0.55, 3.45], "E1", "E9")
    p("EC uses a full sort, costing O(E log E); it does not implement the paper's bounded-heap optimization. Node-centric methods sort nodes and neighborhoods, with O(E + V log V + sum_v degree(v) log degree(v)) work. Lists hold sorted neighborhoods and a set prevents duplicate emissions. Linkage schedules one declared partition (left by default). Deduplication represents both endpoints; duplicate adjacency entries consume their local round position but not a verification-budget slot. Ties use string IDs deterministically.", "E1", "E9")
    p("These BFS and DFS names describe scheduling of candidate neighborhoods, not ordinary traversal of connected components. The ranking is static: verification outcomes do not update it. The implemented Hybrid follows the global first-edge sort in paper §6. The pinned pyJedAI HB routine instead emits first edges in node-mean order. Our audit records this discrepancy rather than silently equating the two variants.", "E1", "E7", "E9")

    h("4. Correctness validation and metrics")
    p(f"The local suite has {reproduction['tests_passed']} passing tests. It checks hand-computed strategy orders, input-order invariance under ties, budget prefixes, undirected duplicate removal, sparse joins against exhaustive cosine calculation, empty/invalid inputs, ID and label isolation, dataset preparation, grid coverage, resource signatures, and end-to-end demos. These checks support implementation correctness on the covered cases; they are not a proof of equivalence to every upstream workflow.", "E8", "E9")
    p("Let T be the set of all unique true pairs, C the generated candidates, and R(b) the fraction of T found after the first b comparisons. Candidate recall is |C ∩ T| / |T|. Recall@B uses the actually available prefix, so missing candidates remain false negatives. The perfect oracle is an evaluation device; it does not measure the accuracy of a real verification model.", "E1", "E9")
    code("Fixed-budget PR@B = (R(1) + ... + R(B)) / B\nPinned pyJedAI AUC = (R(1) + ... + R(L)) / (L + 1)\nL = min(B, number of available candidates)", "E9", "E7")
    p("For fixed-budget PR, recall stays constant after candidates are exhausted; at B=0 the value is zero. The compatible pyJedAI column has no padded tail and uses actual emissions plus one in the denominator. For example, one true emission out of two total matches with B=4 gives fixed-budget PR=0.5 and compatible AUC=0.25. These are separately named columns and are never interchanged.", "E9", "E7")
    p(f"The compatible metric was checked on {reference['verified_cases']} cases against the actual checksum-verified _generate_auc_data method extracted through Python AST, with tolerance 1e-12. A tie-free bipartite fixture also confirms EC/TOP, BFS, and DFS agreement while exposing the expected Hybrid/HB difference. Compatibility is bounded to batch size one and no label-based early-stop mode; the library revision used for the original paper is unknown.", "E7", "E14")

    h("5. Experimental setup")
    dataset_rows = [["Dataset", "Records", "Unique true pairs", "Relation to paper"]]
    labels = {"d1_restaurants": "Restaurants (D1)", "d2_abt_buy": "Abt–Buy (D2)", "cora_large_variant": "Cora mirror variant"}
    for dataset in data_manifest["datasets"]:
        a, b, truth = dataset["expected_counts"]
        dataset_rows.append([labels[dataset["key"]], f"{a:,}" + (f" / {b:,}" if b else ""), f"{truth:,}", "Same counts as Table 1" if dataset["mode"] == "linkage" else "Different version from Table 2"])
    table(dataset_rows, [1.2, 1, 0.8, 1.5], "E14")
    p("Inputs are pinned to pyJedAI commit eb446095f921af3207bbefd570cc65e818194419 [3]. File length, Git blob SHA, and SHA-256 are checked before conversion. Cora has 1,879 records and 62,891 distinct positive pairs, versus 1,878 and 62,892 in the paper. Its 73,147 raw label rows contain 10,256 redundant entries after orientation canonicalization. We preserve all records and do not manufacture a match or remove a record to force the published counts.", "E14", "E1")
    p("The fixed baseline uses 3-grams, k=10, cosine, right-side indexing, and left-partition scheduling for linkage. The complete grid tests 3/5-grams, k=1/5/10, and left/right/both indexing: 18 linkage settings per dataset and six deduplication settings. Every setting is reported; labels are used for evaluation, not to claim independently validated tuning. The ten budgets are B=i×|T| for i=1,...,10, following the paper's experimental budget scale.", "E3", "E4", "E1")
    p("Resource trials use the fixed baseline. One warm-up block is discarded, followed by five measured blocks; each block shuffles all 15 dataset-stage jobs with seed 5003 and runs them sequentially. Every job starts a new Python process with fixed PYTHONHASHSEED. Candidate workers load source records; scheduler workers load the same candidate snapshot. Output hashes must match the reference ordering before a trial is accepted.", "E5", "E6")
    p("Timing excludes process startup, imports, input loading, hashing, and output serialization. RSS is the full worker lifetime peak through the measured stage, including interpreter and loaded inputs, converted from the platform's getrusage units. The two measures have different boundaries. Min–max ranges summarize five observations; they are not confidence intervals or evidence of five independent datasets.", "E5", "E6")
    table([["Item", "Recorded environment"], ["Experiment Python", environment["python"].split("\n")[0]], ["Operating system", environment["platform"]], ["Architecture", environment["machine"] + "; resource manifest CPU string: " + environment["cpu"]], ["Core dependencies", "Python standard library only"], ["Plotting environment", "Python 3.12; Matplotlib 3.11.2; NumPy 2.5.5"], ["Resource stage budget", "Largest configured budget, measured separately from input loading"]], [1, 2.4], "E6", "E10", "E11")

    h("6. Results")
    sh("6.1 Fixed baseline and early effectiveness")
    main_rows = [["Dataset / budget", "EC", "BFS", "DFS", "Hybrid"]]
    for dataset in data_manifest["datasets"]:
        key, truth = dataset["key"], dataset["expected_counts"][2]
        selected = {r["strategy"]: r for r in baseline if r["dataset"] == key and int(r["budget"]) == truth}
        main_rows.append([labels[key] + f"\nB={truth:,}"] + [f"{float(selected[s]['recall']):.4f}" for s in ["EC", "BFS", "DFS", "Hybrid"]])
    table(main_rows, [1.8, 0.7, 0.7, 0.7, 0.7], "E3")
    note("Table 1. Recall@B at B equal to all unique true pairs. All schedulers use identical candidates and weights within each dataset. These are measured values, not values copied from the paper.", "E3")
    p("Abt–Buy shows a clear ordering effect in this fixed configuration: BFS and Hybrid find 84.76% of the 1,076 matches by budget 1,076, compared with EC's 63.85% and DFS's 9.94%. Hybrid has higher fixed-budget PR than BFS at this first budget (0.4515 versus 0.4139). This does not establish a universal ranking or statistical significance.", "E3")
    p("Restaurants retains all true pairs in the baseline candidate set, but its early ordering is poor. EC finds one true pair in its first 89 comparisons. Of those 89 pairs, 78 have cosine above 0.999999. Repeated sparse profiles therefore create highly ambiguous priorities. This diagnostic shows that high similarity need not imply identity; it does not separately identify a causal effect of preprocessing or tie-breaking.", "E3", "E16")
    p("Cora's candidate recall is 0.1609 with 13,079 retained pairs. Even the smallest configured budget, 62,891, exceeds that candidate count, so final recall is identical for every scheduler across the ten budgets. Fixed-budget PR still reflects how early retained positives appear, followed by the declared constant tail. This is principally a candidate-generation limitation, not evidence that ordering can recover discarded pairs.", "E3")
    figure("baseline", "Figure 1. Fixed-baseline progression. Rows correspond to D1, D2, and the Cora mirror variant; columns show Recall@B and fixed-budget PR@B. Dashed gray lines mark candidate-recall ceilings. Recall is held constant after candidates are exhausted. The budget axis is normalized by the number of all unique true pairs.", "E3", "E10")

    sh("6.2 Complete-grid sensitivity")
    grouped = {}
    for row in sweep:
        grouped.setdefault((row["dataset"], row["strategy"], row["setting"]), []).append(float(row["progressive_recall"]))
    averaged = {key: statistics.mean(values) for key, values in grouped.items()}
    sensitivity = [["Dataset", "Strategy", "Settings", "Median mean PR", "Range"]]
    for dataset in data_manifest["datasets"]:
        for strategy in ["EC", "BFS", "DFS", "Hybrid"]:
            values = [v for (d,s,_),v in averaged.items() if d == dataset["key"] and s == strategy]
            sensitivity.append([labels[dataset["key"]], strategy, str(len(values)), f"{statistics.median(values):.4f}", f"{min(values):.4f}–{max(values):.4f}"])
    table(sensitivity, [1.5, .6, .6, 1, 1.2], "E4")
    note("Table 2. Each setting first averages fixed-budget PR across ten budgets. Medians and ranges summarize those setting-level averages. The settings and budgets are correlated deterministic conditions, not independent sampling replicates.", "E4")
    p("The sweep confirms that candidate construction matters. For Abt–Buy with 3-grams and k=10, bilateral indexing raises candidate recall from 0.9870 to 0.9954 while expanding the candidate graph from 10,760 to 14,808 edges. The trade-off includes more candidate and scheduling work; it is not an isolated improvement in a scheduling rule. On Cora, increasing k from one to five to ten raises candidate recall from 0.0208 to 0.0894 to 0.1609. At k=10, using 5-grams instead yields 0.1590 and does not remove the candidate ceiling.", "E4")
    figure("candidates", "Figure 2. Candidate-generation sensitivity. Rows are datasets; columns are 3-gram and 5-gram representations. Linkage lines distinguish indexing direction. Cora uses one shared index and undirected top-k union. The vertical scale is shared so that the low Cora ceiling remains visible.", "E4", "E10")
    figure("scheduling", "Figure 3. Scheduling sensitivity. Each dot is one predeclared setting's mean fixed-budget PR across ten budgets; the black segment is the median across settings. D1 and D2 have 18 settings each; Cora has six. These dots are not independent repeats, and the median segments are not confidence intervals.", "E4", "E10")

    sh("6.3 Resource measurements")
    resource_rows = [["Dataset", "Stage", "Median ms", "Observed ms range", "Peak RSS MiB"]]
    for dataset in data_manifest["datasets"]:
        for stage in ["candidates", "EC", "BFS", "DFS", "Hybrid"]:
            row = next(r for r in resources if r["dataset"] == dataset["key"] and r["stage"] == stage)
            resource_rows.append([labels[dataset["key"]], stage, f"{float(row['seconds_median'])*1000:.2f}", f"{float(row['seconds_min'])*1000:.2f}–{float(row['seconds_max'])*1000:.2f}", f"{float(row['peak_rss_mib_median']):.2f}"])
    table(resource_rows, [1.45, .9, .8, 1.2, .8], "E5")
    note("Table 3. Five fresh-process trials per row. Time is measured stage work only. Memory is median full-worker lifetime peak RSS, including interpreter and input loading; it is not additional memory allocated solely by the algorithm. Complete raw ranges and standard deviations are retained in the result CSVs.", "E5", "E6")
    p("On this machine and fixed baseline, candidate generation dominates measured stage time: median construction takes about 66 ms on Restaurants, 983 ms on Abt–Buy, and 8.31 seconds on Cora. Median scheduler times range from about 1.5–1.9 ms, 5.1–8.2 ms, and 13.7–23.5 ms respectively. Changing a scheduler can alter early recall substantially even when its own time is small; total preprocessing cost still has to be considered.", "E5")
    figure("resources", "Figure 4. Resource measurements for the fixed baseline. Left: measured stage duration on a logarithmic scale, excluding input loading and worker startup. Right: whole-worker lifetime peak RSS including interpreter and inputs. Markers are medians; whiskers are observed minima and maxima across five trials. Candidate and scheduling workers have different input baselines.", "E5", "E6", "E10")

    h("7. Comparison with the paper and limitations")
    p("Paper §7.3 reports strong Join-family BFS results on D2 and a different best-method ordering on D1, using per-scheduler selected configurations [1]. Its overall best Join workflow uses character 5-grams, TF-IDF, Euclidean similarity, and five neighbors. Our controlled cosine pipeline asks a narrower question. It does not reproduce the original parameter search, all workflow families, model-based comparisons, or exact figures.", "E1", "E9")
    p("Some qualitative behavior is compatible with the paper, but the ranking is not universally reproduced. Our D2 fixed baseline gives Hybrid greater first-budget PR than BFS, while D1 DFS performs poorly at k=10. The report preserves these outcomes. Differences in input versions, IDF smoothing, similarity function, indexing context, tie handling, Hybrid specification, AUC integration, and dependency revision prevent a direct numerical replication claim.", "E1", "E3", "E4", "E7", "E14")
    p("Generalization is limited to two linkage datasets and a Cora mirror variant. The oracle excludes verification-model errors. The small parameter grid does not establish an optimal method, and no held-out strategy selector is trained. Resource observations depend on this workstation and background load. Full-worker RSS is not incremental algorithm memory, and all resource timers are measured at the maximum configured budget rather than separately at every budget.", "E3", "E4", "E5", "E6", "E9")
    p("The inspected mirror has an Apache-2.0 software license, but a dataset-specific redistribution license was not identified. Raw benchmark data are therefore not bundled in the repository. The original experimental dependency revision and exact original Cora bytes remain unresolved. These are explicit provenance limitations, not silently assumed matches.", "E14", "E15")

    h("8. Challenges and lessons learned")
    p("The most important lesson is to separate candidate recall from scheduling effectiveness. A candidate generator may retain every match yet order ambiguous pairs badly, as in D1, or discard most positives before any ordering is attempted, as in Cora. Both checks are necessary before interpreting progressive curves.", "E3", "E4", "E16")
    p("A second lesson is that a metric name does not guarantee the same integration convention. Checking the actual AUC routine exposed a denominator and exhaustion difference. Checking source against the paper also revealed the Hybrid discrepancy. We kept both the paper-based implementation and the version-specific audit rather than changing conventions to obtain a favorable comparison.", "E1", "E7", "E9")
    p("A third lesson is that reproducibility requires executable preprocessing, explicit input versions, deterministic ordering, and measurement boundaries. The pipeline records hashes and retains every declared setting. Repeated timing runs characterize execution variability; they do not supply new independent matching datasets. These controls make failures and limitations reviewable.", "E4", "E6", "E8", "E14")

    h("9. Reproducibility and deliverable links")
    full = reproduction["full_run"]
    p(f"An independent source tree and fresh virtual environment with no installed packages or pip passed {reproduction['tests_passed']} tests, re-prepared checksum-verified cached inputs, and reproduced all 120 fixed-baseline quality rows. The full check additionally reproduced {full['grid_rows_reproduced']:,} grid rows and completed {full['resource_measured_jobs_completed']} resource jobs with matching output signatures. The maximum grid quality difference was {full['grid_maximum_absolute_error']:.1e}. Timing and RSS values are not required to match across repetitions.", "E8")
    p("A separate Python 3.12 environment successfully installed the pinned plotting packages from locally reconstructed cached wheels and generated the report figures. That proves fresh offline installation and execution, not access to PyPI. Direct cold-network requests on this execution host failed at DNS resolution, so network acquisition remains unverified here. The ordinary downloader still uses pinned public URLs and verifies hashes.", "E11", "E15")
    code("python3 scripts/prepare_benchmarks.py --download\nPYTHONPATH=src python3 -m unittest discover -s tests -v\npython3 scripts/verify_reference.py\npython3 scripts/run_sweep.py\npython3 scripts/benchmark_resources.py\npython3 scripts/verify_reproduction.py --full", "E9")
    p("The repository README gives the fixed-baseline, plotting, and report rebuild commands. Configurations and result CSVs are versioned; raw datasets, virtual environments, and transient runs are excluded. Each report table is generated from saved CSVs, and report/evidence_registry.json binds report blocks to evidence files and hashes. Human verification is explicitly pending rather than represented as completed.", "E9", "E12")
    add("paragraph", "Project repository: " + team["repository_url"], evidence=["E15"], url=team["repository_url"])
    note("The repository URL was reachable through the GitHub branch API at the recorded remote revision. The latest report and experimental additions are local changes and have not been uploaded as part of this task. Video production, video-link insertion, and submission were intentionally excluded.", "E15")

    h("10. References")
    references = [
        ("[1] Jakub Maciejewski, Konstantinos Nikoletos, George Papadakis, and Yannis Velegrakis. 2025. Progressive Entity Matching: A Design Space Exploration. Proceedings of the ACM on Management of Data 3(1), Article 65 (SIGMOD), 25 pages. DOI: 10.1145/3709715.", "https://doi.org/10.1145/3709715", "E1"),
        ("[2] JacobMaciejewski. PER-Design-Space-Exploration. Authors' public experiment repository. The supplied local archive has no identified commit pin. Accessed 22 November 2026.", "https://github.com/JacobMaciejewski/PER-Design-Space-Exploration", "E14"),
        ("[3] AI-team-UoA. pyJedAI. Reference source and benchmark mirror at commit eb446095f921af3207bbefd570cc65e818194419. Accessed 22 November 2026. This pin is not established as the original paper's runtime revision.", "https://github.com/AI-team-UoA/pyJedAI/tree/eb446095f921af3207bbefd570cc65e818194419", "E14"),
        ("[4] DSC5003_1introduction&ER.pdf. Supplied course introduction slides, pages 5–9. Group Project (Tentative), Academic Calendar 2026/27. No submission deadline or later amendment was provided.", None, "E2"),
        ("[5] Timothy Kassis, Vinayak Agarwal, Yuhuan He, Darshil Patel, and Aubrey M. Brueckner. 2026. Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents. arXiv preprint, arXiv:2609.00065. DOI: 10.48550/arXiv.2609.00065. Cited for research-writing procedure, not as evidence for entity matching results.", "https://doi.org/10.48550/arXiv.2609.00065", "E13"),
    ]
    for text, url, evidence in references:
        add("paragraph", text, evidence=[evidence], url=url)

    h("Appendix. Administrative completion fields")
    table([["Field", "Status / action"], ["Group names and undergraduate majors", "Not supplied. Fill report/team_metadata.json."], ["Individual contributions", "Not supplied. Enter actual roles; do not infer credit from automated work."], ["Project code / final filename", "Project code not supplied; current filename is DSC5003-report.pdf."], ["Deadline / updated course instructions", "Not supplied; supplied project slides are tentative."], ["Video and submission", "Excluded by the current instruction; no video link or submission is claimed."], ["Human scientific review", "Pending. Machine checks do not replace author review."]], [1.3, 2.7], "E2", "E12", "E15")

    document = {"title": "Progressive Entity Matching: A Focused Replication",
                "subtitle": "DSC-5003 Track 2", "status": "Technical draft · team details and human review pending",
                "blocks": blocks}
    (HERE / "report.json").write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    markdown, html_blocks = [], []
    for block in blocks:
        kind = block["type"]
        if kind in {"title", "heading", "subheading"}:
            level = {"title": 1, "heading": 2, "subheading": 3}[kind]
            text = block["text"].replace("\n", " ")
            markdown.append("#" * level + " " + text)
            html_blocks.append(f"<h{level}>{html.escape(text)}</h{level}>")
        elif kind in {"paragraph", "note", "subtitle"}:
            text = block["text"]
            markdown.append(text)
            body = html.escape(text)
            if block.get("url"): body = f'<a href="{html.escape(block["url"], quote=True)}">{body}</a>'
            html_blocks.append(f'<p class="{kind}">{body}</p>')
        elif kind == "code":
            markdown.append("```text\n" + block["text"] + "\n```")
            html_blocks.append("<pre>" + html.escape(block["text"]) + "</pre>")
        elif kind == "table":
            rows = block["rows"]
            escape_md = lambda value: value.replace("|", "\\|").replace("\n", " / ")
            lines = ["| " + " | ".join(escape_md(v) for v in row) + " |" for row in rows]
            lines.insert(1, "| " + " | ".join("---" for _ in rows[0]) + " |")
            markdown.append("\n".join(lines))
            table_html = "<table>"
            for index, row in enumerate(rows):
                tag = "th" if index == 0 else "td"
                table_html += "<tr>" + "".join(f"<{tag}>{html.escape(v)}</{tag}>" for v in row) + "</tr>"
            html_blocks.append(table_html + "</table>")
        elif kind == "figure":
            markdown.append(f"![{block['caption']}]({block['source']})\n\n{block['caption']}")
            encoded = base64.b64encode((HERE / block["source"]).read_bytes()).decode()
            html_blocks.append(f'<figure><img alt="{html.escape(block["caption"], quote=True)}" src="data:image/png;base64,{encoded}"><figcaption>{html.escape(block["caption"])}</figcaption></figure>')
        elif kind == "pagebreak":
            markdown.append("<!-- pagebreak -->")
            html_blocks.append('<div class="pagebreak"></div>')
    (HERE / "DSC5003-report.md").write_text("\n\n".join(markdown) + "\n")
    css = "body{max-width:900px;margin:48px auto;padding:0 24px;font:15px/1.6 system-ui;color:#1d2939}h1,h2,h3{color:#1c425f}h1{font-size:32px}h2{margin-top:32px}table{border-collapse:collapse;width:100%;margin:18px 0;font-size:13px}th{background:#1c425f;color:white}td,th{text-align:left;padding:9px;border-bottom:1px solid #d8dee6}tr:nth-child(even){background:#f5f7fa}pre{white-space:pre-wrap;background:#f3f5f7;padding:14px}figure{margin:20px 0}img{max-width:100%;height:auto}figcaption,.note{font-size:13px;color:#4a5568}.subtitle{color:#58677b}a{color:#125b8c}@media print{body{margin:0;font-size:10pt}.pagebreak{break-before:page}figure{break-inside:avoid}h2,h3{break-after:avoid}table{break-inside:auto}tr{break-inside:avoid}}"
    (HERE / "DSC5003-report.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Progressive Entity Matching — Technical Report</title><style>' + css + '</style><body>' + "\n".join(html_blocks) + '</body></html>')

    source_files = {
        "E1": ["references/papers/3709715.pdf"], "E2": ["report/course_requirements.json"],
        "E3": ["results/fixed_baseline_metrics.csv"], "E4": ["results/sweep_metrics.csv", "configs/experiment_protocol.json"],
        "E5": ["results/resource_summary.csv", "results/resource_measurements.csv"], "E6": ["results/resource_manifest.json"],
        "E7": ["results/reference_verification.json"], "E8": ["results/full_reproduction_verification.json"],
        "E9": [str(p.relative_to(ROOT)) for p in sorted((ROOT / "src/pem").glob("*.py"))] + ["scripts/run_experiment.py", "scripts/prepare_benchmarks.py", "scripts/run_sweep.py", "scripts/benchmark_resources.py"],
        "E10": ["report/figures/metadata.json"], "E11": ["report/environment_verification.json"],
        "E12": ["report/team_metadata.json"], "E13": ["report/delivery_context.json"],
        "E14": ["configs/benchmark_sources.json", "docs/replication_audit.md"], "E15": ["report/delivery_context.json"],
        "E16": ["results/stage2_analysis.md"],
    }
    evidence = {key: {"files": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
                      "machine_status": "opened_or_checked_in_workspace", "human_review": "pending"}
                for key, paths in source_files.items()}
    claims = []
    for index, block in enumerate(blocks):
        if block.get("evidence"):
            claims.append({"block": index, "evidence_ids": block["evidence"],
                           "content_sha256": hashlib.sha256(json.dumps(block, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                           "human_review": "pending"})
    (HERE / "evidence_registry.json").write_text(json.dumps({"sources": evidence, "claims": claims,
        "submission_ready": False, "note": "Machine provenance is not human verification; all scientific and authorship review remains with the team."}, indent=2) + "\n")
    print(f"Built technical report source: {len(blocks)} blocks with evidence mappings")


if __name__ == "__main__": main()
