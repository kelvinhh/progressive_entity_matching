"""Oracle evaluation; labels never enter candidate generation or scheduling."""
from __future__ import annotations

from pem.candidates import Candidate


def evaluate(order: list[Candidate], truth: set[tuple[str, str]], budget: int) -> dict:
    """Normalized right-step AUC: sum(R(b), b=1..B)/B.

    If candidates run out before B, recall stays constant through the remaining
    budget. B=0 returns zero. This discrete integration convention is explicit;
    Also reports pyjedai_auc, compatible with _generate_auc_data in the pinned
    pyJedAI snapshot for batch_size=1 and emit_all_tps_stop=False: sum of recall
    over actual emissions divided by (emissions + 1). It has no constant tail.
    """
    if type(budget) is not int or budget < 0:
        raise ValueError("budget must be a nonnegative integer")
    if not truth:
        raise ValueError("Ground truth must be nonempty")
    hits = 0
    area = 0
    seen = set()
    prefix = order[:budget]
    for edge in prefix:
        if edge.pair in seen:
            raise ValueError("Evaluation order contains duplicate pairs")
        seen.add(edge.pair)
        hits += edge.pair in truth
        area += hits
    pyjedai_auc = area / ((len(prefix) + 1) * len(truth))
    area += (budget - len(prefix)) * hits
    return {"budget": budget, "comparisons": len(prefix), "matches": hits,
            "recall": hits / len(truth),
            "progressive_recall": area / (budget * len(truth)) if budget else 0.0,
            "pyjedai_auc": pyjedai_auc}


def recall_curve(order: list[Candidate], truth: set[tuple[str, str]]) -> list[dict]:
    if not truth:
        raise ValueError("Ground truth must be nonempty")
    hits = 0
    rows = [{"comparisons": 0, "matches": 0, "recall": 0.0}]
    for i, edge in enumerate(order, 1):
        hits += edge.pair in truth
        rows.append({"comparisons": i, "matches": hits, "recall": hits / len(truth)})
    return rows
