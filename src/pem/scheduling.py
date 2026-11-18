"""Section 6 scheduling, independently implemented from the paper description.

Deterministic ties use IDs. In deduplication, duplicate adjacency entries consume
their local round position but never consume a verification budget slot.
"""
from __future__ import annotations

import math
from collections import defaultdict
from itertools import islice
from typing import Iterator

from pem.candidates import Candidate

STRATEGIES = ("EC", "BFS", "DFS", "Hybrid")


def edge_key(edge: Candidate) -> tuple:
    return -edge.score, edge.left, edge.right


def schedule(candidates: list[Candidate], strategy: str, budget: int | None = None, *,
             mode: str = "linkage", partition: str = "left") -> list[Candidate]:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")
    if budget is not None and (type(budget) is not int or budget < 0):
        raise ValueError("budget must be a nonnegative integer or None")
    if mode not in {"linkage", "deduplication"} or partition not in {"left", "right"}:
        raise ValueError("Invalid mode or scheduling partition")
    unique = {}
    for edge in candidates:
        if not math.isfinite(edge.score) or not 0 <= edge.score <= 1:
            raise ValueError("Candidate scores must be finite values in [0,1]")
        if mode == "deduplication":
            if edge.left == edge.right:
                continue
            edge = Candidate(*sorted(edge.pair), edge.score)
        if edge.pair not in unique or edge.score > unique[edge.pair].score:
            unique[edge.pair] = edge
    edges = list(unique.values())
    if strategy == "EC":
        # Full sort is intentional in this reference implementation (O(E log E)).
        return sorted(edges, key=edge_key)[:budget]

    neighborhoods = defaultdict(list)
    for edge in edges:
        if mode == "deduplication":
            neighborhoods[edge.left].append(edge)
            neighborhoods[edge.right].append(edge)
        else:
            neighborhoods[edge.left if partition == "left" else edge.right].append(edge)
    for neighbors in neighborhoods.values():
        neighbors.sort(key=edge_key)
    nodes = sorted(neighborhoods, key=lambda node: (
        -math.fsum(e.score for e in neighborhoods[node]) / len(neighborhoods[node]), node))

    def ordered() -> Iterator[Candidate]:
        if strategy == "BFS":
            active = nodes
            depth = 0
            while active:
                next_active = []
                for node in active:
                    neighbors = neighborhoods[node]
                    yield neighbors[depth]
                    if depth + 1 < len(neighbors):
                        next_active.append(node)
                active = next_active
                depth += 1
        elif strategy == "DFS":
            for node in nodes:
                yield from neighborhoods[node]
        else:
            # Unlike plain BFS's first round, Hybrid globally sorts the best edges.
            yield from sorted((neighborhoods[node][0] for node in nodes), key=edge_key)
            for node in nodes:
                yield from neighborhoods[node][1:]

    def distinct() -> Iterator[Candidate]:
        seen = set()
        for edge in ordered():
            if edge.pair not in seen:
                seen.add(edge.pair)
                yield edge

    return list(islice(distinct(), budget)) if budget is not None else list(distinct())
