"""Check puzzle provenance and mathematical uniqueness against the real release."""
import importlib.util
import csv
from itertools import product
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("puzzles", ROOT / "scripts/puzzles.py")
puzzles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(puzzles)


class PuzzleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network = json.loads((ROOT / "assets/data/network.json").read_text(encoding="utf-8"))
        cls.output = puzzles.make_puzzles(cls.network)

    def test_twelve_puzzles_have_growing_sizes_and_real_nonreciprocal_links(self):
        with (ROOT / "data/raw/week1_edges.tsv").open(encoding="utf-8") as handle:
            original = {tuple(row) for row in csv.reader((line for line in handle if line.strip() and not line.startswith("#")), delimiter="\t")}
        self.assertEqual(len(self.output["puzzles"]), 12)
        self.assertEqual([p["difficulty"] for p in self.output["puzzles"]], ["easy"] * 4 + ["medium"] * 4 + ["hard"] * 4)
        signatures = set()
        for puzzle in self.output["puzzles"]:
            ids = {n["id"] for n in puzzle["nodes"]}
            self.assertEqual(len(ids), {"easy": 3, "medium": 4, "hard": 5}[puzzle["difficulty"]])
            pairs = set()
            for edge in puzzle["edges"]:
                pair = (edge["source"], edge["target"])
                self.assertIn(pair, original)
                self.assertNotIn(pair[::-1], original)
                self.assertEqual({edge["a"], edge["b"]}, set(pair))
                self.assertTrue(set(pair) <= ids)
                pairs.add(pair)
            self.assertEqual(len(pairs), len(puzzle["edges"]))
            signatures.add(tuple(sorted(pairs)))
        self.assertEqual(len(signatures), 12)

    def test_independent_exhaustive_solver_finds_exactly_the_actual_solution(self):
        for puzzle in self.output["puzzles"]:
            solutions = []
            for choices in product((False, True), repeat=len(puzzle["edges"])):
                edges = [(e["a"], e["b"]) if bit else (e["b"], e["a"]) for e, bit in zip(puzzle["edges"], choices)]
                if all(
                    sum(t == node["id"] for _, t in edges) == node["in_target"]
                    and sum(s == node["id"] for s, _ in edges) == node["out_target"]
                    for node in puzzle["nodes"]
                ):
                    solutions.append(set(edges))
            self.assertEqual(solutions, [{(e["source"], e["target"]) for e in puzzle["edges"]}])

    def test_generation_is_deterministic_and_independent_of_input_order(self):
        reversed_network = {"nodes": self.network["nodes"][::-1], "edges": self.network["edges"][::-1]}
        self.assertEqual(self.output, puzzles.make_puzzles(reversed_network))

    def test_solver_rejects_ambiguous_directed_cycle(self):
        self.assertEqual(puzzles.count_solutions(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")], {"a": 1, "b": 1, "c": 1}), 2)

    def test_no_synthetic_puzzles_are_substituted_for_empty_network(self):
        with self.assertRaisesRegex(ValueError, "no non-reciprocal links"):
            puzzles.make_puzzles({"nodes": [{"id": "isolated", "name": "Isolated"}], "edges": []})


if __name__ == "__main__":
    unittest.main()
