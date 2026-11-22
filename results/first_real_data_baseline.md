# First real-data baseline

These are measured results of our independent implementation, using one fixed
configuration chosen before examining real-data scores: character 3-grams,
smoothed TF-IDF cosine, k=10, right-side indexing and left-partition scheduling
for linkage; undirected top-k union for deduplication. No parameter tuning was
performed for this table. All four strategies share candidates and weights.

## Data checks

| Dataset | Left records | Right records | Unique true pairs | Candidate pairs | Candidate recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| d1_restaurants | 339 | 2256 | 89 | 3390 | 1.0000 |
| d2_abt_buy | 1076 | 1076 | 1076 | 10760 | 0.9870 |
| cora_large_variant | 1879 | — | 62891 | 13079 | 0.1609 |

D1 and D2 counts agree with paper Table 1; this alone does not establish identical bytes.
Cora is explicitly a mirror variant: 1,879 records / 62,891 unique positive pairs
versus the paper's 1,878 / 62,892. Its 73,147 label rows include 10,256
duplicate/reversed pairs, which are canonicalized. The `label` field is excluded
from text to avoid using identifier-like metadata as a matching feature.

## At B = number of true pairs

| Dataset | Strategy | Budget | Actual comparisons | Recall@B | PR@B (fixed budget) | pyJedAI-compatible AUC |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| d1_restaurants | EC | 89 | 89 | 0.0112 | 0.0003 | 0.0002 |
| d1_restaurants | BFS | 89 | 89 | 0.0112 | 0.0039 | 0.0039 |
| d1_restaurants | DFS | 89 | 89 | 0.0000 | 0.0000 | 0.0000 |
| d1_restaurants | Hybrid | 89 | 89 | 0.0899 | 0.0059 | 0.0059 |
| d2_abt_buy | EC | 1076 | 1076 | 0.6385 | 0.3730 | 0.3726 |
| d2_abt_buy | BFS | 1076 | 1076 | 0.8476 | 0.4139 | 0.4135 |
| d2_abt_buy | DFS | 1076 | 1076 | 0.0994 | 0.0495 | 0.0495 |
| d2_abt_buy | Hybrid | 1076 | 1076 | 0.8476 | 0.4515 | 0.4511 |
| cora_large_variant | EC | 62891 | 13079 | 0.1609 | 0.1473 | 0.0952 |
| cora_large_variant | BFS | 62891 | 13079 | 0.1609 | 0.1455 | 0.0869 |
| cora_large_variant | DFS | 62891 | 13079 | 0.1609 | 0.1464 | 0.0912 |
| cora_large_variant | Hybrid | 62891 | 13079 | 0.1609 | 0.1465 | 0.0917 |

## Interpretation and limits

- Abt–Buy: at B=1,076, BFS and Hybrid find more true matches than EC in this fixed configuration; Hybrid has the higher progressive recall. This is a result for this configuration, not a general ranking.
- Restaurants: very low early recall despite full candidate recall shows that retaining true pairs does not ensure a good early ordering. The source has sparse records and many repeated values; the causal reason for the ranking still needs diagnostic experiments.
- Cora: top-10 generation retains only about 16.1% of labeled pairs. All schedulers are limited by this ceiling. Each configured budget exceeds the number of generated candidates, so final recall is the same for all four strategies. Smaller diagnostic budgets or larger k are needed to examine early ordering more closely.
- PR@B averages post-verification recall over the configured budget, with a constant tail after exhaustion. pyJedAI-compatible AUC averages over actual emissions with denominator L+1 and no tail. These columns answer different questions and must not be interchanged.
- These runs use the paper's scheduling description. Hybrid differs from the pinned library implementation; see the audit. The pin is not known to be the version used in the paper.
- Timings in the CSV are single-run diagnostics with memory tracing disabled. No resource advantage or statistical significance is claimed. Independent RSS and repeated timing measurements are pending.
- Real-data results do not yet reproduce the paper's parameter search, all workflow families, or its full result figures.

## Reproduce

```bash
python3 scripts/prepare_benchmarks.py --download
python3 scripts/verify_reference.py
python3 scripts/run_experiment.py --config configs/benchmarks/d1_restaurants.json --output outputs/benchmarks/d1_restaurants
python3 scripts/run_experiment.py --config configs/benchmarks/d2_abt_buy.json --output outputs/benchmarks/d2_abt_buy
python3 scripts/run_experiment.py --config configs/benchmarks/cora_large_variant.json --output outputs/benchmarks/cora_large_variant
python3 scripts/summarize_benchmarks.py
```

Full ten-budget results: [fixed_baseline_metrics.csv](fixed_baseline_metrics.csv).
Input and source hashes: [metadata](fixed_baseline_metadata/).
Method/source differences: [replication audit](../docs/replication_audit.md).
