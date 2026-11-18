"""Sparse character n-gram TF-IDF top-k join (paper Section 5.2).

This lightweight variant uses joint-corpus smoothed IDF and cosine similarity.
It only emits positive-overlap pairs; it does not pad top-k with zero scores.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from heapq import nsmallest

from pem.data import Record


@dataclass(frozen=True)
class Candidate:
    left: str
    right: str
    score: float

    @property
    def pair(self) -> tuple[str, str]:
        return self.left, self.right


def vectorize(records: list[Record], ngram: int) -> list[dict[str, float]]:
    counts = [Counter(r.text[i:i + ngram] for i in range(len(r.text) - ngram + 1))
              for r in records]
    frequency = Counter(term for row in counts for term in row)
    idf = {term: math.log((1 + len(records)) / (1 + df)) + 1
           for term, df in frequency.items()}
    vectors = []
    for row in counts:
        weighted = {term: count * idf[term] for term, count in row.items()}
        norm = math.sqrt(sum(value * value for value in weighted.values()))
        vectors.append({term: value / norm for term, value in weighted.items()} if norm else {})
    return vectors


def generate_candidates(left: list[Record], right: list[Record] | None = None, *,
                        ngram: int = 3, top_k: int = 10,
                        min_score: float = 0.0, indexing: str = "right") -> list[Candidate]:
    """Index right/query left by default. 'both' unions the two directed top-k joins.

    Deduplication queries every record against the same index, removes self-pairs,
    then canonicalizes and unions top-k lists. Thus undirected degree may exceed k.
    No labels are accepted by this API.
    """
    if type(ngram) is not int or ngram < 1 or type(top_k) is not int or top_k < 1:
        raise ValueError("ngram and top_k must be positive integers")
    if not math.isfinite(min_score) or not 0 <= min_score <= 1:
        raise ValueError("min_score must be between 0 and 1")
    if indexing not in {"left", "right", "both"}:
        raise ValueError("indexing must be left, right, or both")
    dedup = right is None
    right = left if dedup else right
    for records in (left, right):
        if len({r.id for r in records}) != len(records):
            raise ValueError("Record IDs must be unique within each source")
    vectors = vectorize(left if dedup else left + right, ngram)
    left_vectors = vectors[:len(left)]
    right_vectors = left_vectors if dedup else vectors[len(left):]
    pairs = {}

    def query(queries, query_vectors, targets, target_vectors, reverse=False):
        postings = defaultdict(list)
        for index, vector in enumerate(target_vectors):
            for term, value in vector.items():
                postings[term].append((index, value))
        for record, vector in zip(queries, query_vectors):
            scores = defaultdict(float)
            # Stable accumulation independent of dictionary/hash iteration order.
            for term in sorted(vector):
                for index, value in postings.get(term, ()):
                    if not dedup or record.id != targets[index].id:
                        scores[index] += vector[term] * value
            eligible = ((i, min(1.0, score)) for i, score in scores.items()
                        if score > 0 and score >= min_score)
            for index, score in nsmallest(top_k, eligible, key=lambda x: (-x[1], targets[x[0]].id)):
                pair = (targets[index].id, record.id) if reverse else (record.id, targets[index].id)
                if dedup:
                    pair = tuple(sorted(pair))
                pairs[pair] = max(score, pairs.get(pair, 0.0))

    if dedup or indexing in {"right", "both"}:
        query(left, left_vectors, right, right_vectors)
    if not dedup and indexing in {"left", "both"}:
        query(right, right_vectors, left, left_vectors, reverse=True)
    return [Candidate(a, b, score) for (a, b), score in sorted(pairs.items())]
