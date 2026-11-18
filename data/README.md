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
reporting results. Real benchmark acquisition and adapters remain to be added.
