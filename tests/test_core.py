import csv
import itertools
import math
import random
import tempfile
import unittest
from pathlib import Path

from pem.candidates import Candidate as E, generate_candidates, vectorize
from pem.data import Record, normalize, read_records, read_truth
from pem.evaluation import evaluate
from pem.scheduling import STRATEGIES, schedule


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        # Node means: b=.75, c=.6, a=.5; edge order and node order disagree.
        self.edges = [E("a", "x", .9), E("a", "y", .1), E("b", "z", .8),
                      E("b", "w", .7), E("c", "v", .6)]

    def test_hand_computed_orders(self):
        expected = {
            "EC": [("a", "x"), ("b", "z"), ("b", "w"), ("c", "v"), ("a", "y")],
            "DFS": [("b", "z"), ("b", "w"), ("c", "v"), ("a", "x"), ("a", "y")],
            "BFS": [("b", "z"), ("c", "v"), ("a", "x"), ("b", "w"), ("a", "y")],
            "Hybrid": [("a", "x"), ("b", "z"), ("c", "v"), ("b", "w"), ("a", "y")],
        }
        for strategy, pairs in expected.items():
            self.assertEqual([e.pair for e in schedule(self.edges, strategy)], pairs)

    def test_ties_and_input_permutations(self):
        edges = [E("a", "y", .5), E("a", "x", .5), E("b", "x", .5)]
        for strategy in STRATEGIES:
            expected = schedule(edges, strategy)
            for perm in itertools.permutations(edges):
                self.assertEqual(schedule(list(perm), strategy), expected)

    def test_budget_prefixes_and_deduplication(self):
        rng = random.Random(41)
        for mode in ("linkage", "deduplication"):
            edges = [E(str(i), str(j), rng.random()) for i in range(8) for j in range(i + 1, 8)]
            for strategy in STRATEGIES:
                complete = schedule(edges, strategy, mode=mode)
                self.assertEqual({e.pair for e in complete}, {e.pair for e in edges})
                self.assertEqual(len(complete), len(edges))
                for budget in range(len(edges) + 3):
                    self.assertEqual(schedule(edges, strategy, budget, mode=mode), complete[:budget])

    def test_reverse_duplicates_self_pairs_and_max_weight(self):
        edges = [E("a", "b", .3), E("b", "a", .8), E("a", "a", 1)]
        for strategy in STRATEGIES:
            self.assertEqual(schedule(edges, strategy, mode="deduplication"), [E("a", "b", .8)])

    def test_right_partition_is_not_left_partition(self):
        edges = [E("a", "x", .9), E("a", "y", .1), E("b", "y", .8)]
        order = schedule(edges, "DFS", partition="right")
        self.assertEqual([e.pair for e in order], [("a", "x"), ("b", "y"), ("a", "y")])

    def test_invalid_scores_budgets_and_empty(self):
        for score in (float("nan"), float("inf"), -.1, 1.1):
            with self.assertRaises(ValueError):
                schedule([E("a", "b", score)], "EC")
        for budget in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                schedule(self.edges, "EC", budget)
        for strategy in STRATEGIES:
            self.assertEqual(schedule([], strategy), [])
            self.assertEqual(schedule(self.edges, strategy, 0), [])


class CandidateTests(unittest.TestCase):
    def test_sparse_join_against_exhaustive_cosine(self):
        left = [Record("a", "alpha beta"), Record("b", "beta gamma"), Record("empty", "")]
        right = [Record("x", "alpha beta"), Record("y", "gamma beta"), Record("z", "alpha")]
        vectors = vectorize(left + right, 3)
        expected = []
        for i, record in enumerate(left):
            scores = []
            for j, target in enumerate(right):
                score = math.fsum(vectors[i].get(t, 0) * v for t, v in vectors[len(left) + j].items())
                if score > 0:
                    scores.append(E(record.id, target.id, min(1.0, score)))
            expected.extend(sorted(scores, key=lambda e: (-e.score, e.right))[:2])
        actual = generate_candidates(left, right, top_k=2)
        self.assertEqual({e.pair for e in actual}, {e.pair for e in expected})
        for edge in actual:
            wanted = next(e for e in expected if e.pair == edge.pair)
            self.assertAlmostEqual(edge.score, wanted.score)

    def test_empty_text_short_text_and_zero_overlap(self):
        self.assertEqual(generate_candidates([Record("a", "hi")], [Record("b", "")]), [])
        self.assertEqual(generate_candidates([Record("a", "abc")], [Record("b", "xyz")]), [])
        self.assertEqual(generate_candidates([], []), [])

    def test_bilateral_union_and_shared_ids_across_tables(self):
        left = [Record("1", "alpha"), Record("2", "alphabet")]
        right = [Record("1", "alpha")]
        a = generate_candidates(left, right, top_k=1, indexing="left")
        b = generate_candidates(left, right, top_k=1, indexing="right")
        union = generate_candidates(left, right, top_k=1, indexing="both")
        self.assertEqual({e.pair for e in union}, {e.pair for e in a + b})
        self.assertIn(("1", "1"), {e.pair for e in union})

    def test_deduplication_top_k_before_union(self):
        records = [Record("c", "alpha"), Record("b", "alpha"), Record("a", "alpha")]
        candidates = generate_candidates(records, top_k=1)
        self.assertEqual({e.pair for e in candidates}, {("a", "b"), ("a", "c")})
        self.assertTrue(all(e.left < e.right for e in candidates))

    def test_invalid_parameters(self):
        for kwargs in ({"ngram": 0}, {"top_k": -1}, {"min_score": float("nan")}, {"indexing": "bad"}):
            with self.assertRaises(ValueError):
                generate_candidates([], [], **kwargs)


class EvaluationTests(unittest.TestCase):
    def test_hand_computed_area_and_tail(self):
        truth = {("a", "x"), ("c", "z")}
        order = [E("a", "x", .9), E("b", "y", .8), E("c", "z", .7)]
        result = evaluate(order, truth, 3)
        self.assertEqual(result["recall"], 1)
        self.assertAlmostEqual(result["progressive_recall"], (0.5 + 0.5 + 1) / 3)
        self.assertAlmostEqual(evaluate(order, truth, 5)["progressive_recall"], .8)
        self.assertEqual(evaluate(order, truth, 0)["progressive_recall"], 0)

    def test_missing_candidates_count_in_denominator(self):
        result = evaluate([E("a", "b", .8)], {("a", "b"), ("x", "y")}, 4)
        self.assertEqual(result["recall"], .5)
        self.assertEqual(result["progressive_recall"], .5)
        self.assertEqual(result["comparisons"], 1)

    def test_duplicate_orders_and_empty_truth_rejected(self):
        with self.assertRaises(ValueError):
            evaluate([E("a", "b", .8)] * 2, {("a", "b")}, 2)
        with self.assertRaises(ValueError):
            evaluate([], set(), 3)


class InputTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize("  ＡLPHA\t Beta  "), "alpha beta")

    def test_id_leakage_duplicate_ids_and_unknown_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            path.write_text("id,title\nsecret,Alpha\n")
            self.assertEqual(read_records(path, "id", ["title"]), [Record("secret", "alpha")])
            with self.assertRaises(ValueError):
                read_records(path, "id", ["id", "title"])
            path.write_text("id,title\na,Alpha\na,Beta\n")
            with self.assertRaises(ValueError):
                read_records(path, "id", ["title"])
            path.write_text("left_id,right_id\na,unknown\n")
            with self.assertRaises(ValueError):
                read_truth(path, {"a"}, {"b"}, "linkage")


if __name__ == "__main__":
    unittest.main()
