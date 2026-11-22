# Data

`fixtures/` contains original, manually constructed product records for pipeline
checks. They are **synthetic**, not the paper's benchmarks. Similar model names
such as M100/M200 and charger wattages deliberately introduce hard negatives.

Input tables are UTF-8 CSV. Configure the ID column and text columns explicitly;
IDs and labels must not be matching features. Each table must have unique,
nonempty IDs. Different sources may use overlapping ID values.

Ground truth is a CSV of **positive pairs only**, with columns `left_id,right_id`.
Do not pass a mixed positive/negative table without first selecting positives.
For deduplication, supply each true pair, not cluster IDs; the reader canonicalizes
pair orientation and rejects self-pairs. Cluster-to-pair expansion is not automatic.

Copy a demo configuration for a real dataset, set `name`, input paths, text
columns, delimiter, and budgets. Input paths are relative to the configuration
file. Store raw real data beneath `data/` outside `fixtures/`; it is ignored by
Git. Record the source URL, version, access date, terms, and any cleaning before
reporting results.

## Pinned real benchmarks

```bash
python3 scripts/prepare_benchmarks.py --download
```

The downloader uses the commit and SHA-256 / Git blob hashes in
`configs/benchmark_sources.json`. Without `--download`, it validates cached bytes
offline. A mismatched cached file fails verification rather than being used.

| Config name | Mode | Record counts | Unique true pairs |
| --- | --- | --- | ---: |
| `d1_restaurants` | Linkage | 339 / 2,256 | 89 |
| `d2_abt_buy` | Linkage | 1,076 / 1,076 | 1,076 |
| `cora_large_variant` | Deduplication | 1,879 | 62,891 |

Source: [pyJedAI mirror at the pinned commit](https://github.com/AI-team-UoA/pyJedAI/tree/eb446095f921af3207bbefd570cc65e818194419/data).
Cora differs from paper Table 2 (1,878 records / 62,892 matches) and is explicitly
labeled a variant rather than an exact reproduction of that dataset.

Preparation retains all records, validates IDs, canonicalizes deduplication pair
orientation, and removes repeated positive-pair rows. It excludes IDs and Cora's
identifier-like `label` field from text. No labels are inferred or expanded.
Cora's raw labels have 73,147 rows; 10,256 are redundant after canonicalization.

Local raw bytes live in `data/raw/pyjedai/`, prepared inputs in `data/processed/`,
and the preparation report in `data/processed/preparation.json`. Only manifests,
scripts, configs, and result summaries are tracked by Git.

Dataset-specific licenses were not identified in the inspected mirror material.
The repository's Apache-2.0 software license is not assumed to license the data.
Raw datasets are not redistributed here; confirming their specific usage terms
remains an open task. See [the audit](../docs/replication_audit.md) for details.
