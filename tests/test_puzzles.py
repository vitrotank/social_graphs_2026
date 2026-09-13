"""Check puzzle provenance and mathematical uniqueness against the real release."""
import importlib.util
import csv
from datetime import date, datetime, timedelta
from itertools import product
import json
from pathlib import Path
import unittest
from unittest.mock import patch

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
        all_boards = self.output["puzzles"] + [board for week in self.output["weeks"] for board in week["puzzles"]]
        for puzzle in all_boards:
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

    def test_every_week_has_three_distinct_real_boards_with_growing_difficulty(self):
        original = {(edge["source"], edge["target"]) for edge in self.network["edges"]}
        signatures = {tuple(sorted((edge["source"], edge["target"]) for edge in board["edges"]))
                      for board in self.output["puzzles"]}
        ids = {board["id"] for board in self.output["puzzles"]}
        self.assertEqual(self.output["version"], 2)
        self.assertEqual(len(self.output["weeks"]), 52)
        for number, week in enumerate(self.output["weeks"], 1):
            self.assertEqual(week["id"], f"shift-{number:02}")
            self.assertEqual(week["number"], number)
            self.assertEqual([p["difficulty"] for p in week["puzzles"]], ["easy", "medium", "hard"])
            self.assertEqual([p["stage"] for p in week["puzzles"]], [1, 2, 3])
            for stage, board in enumerate(week["puzzles"], 1):
                self.assertEqual((len(board["nodes"]), len(board["edges"])), [(3, 3), (4, 5), (6, 8)][stage - 1])
                self.assertNotIn(board["id"], ids)
                ids.add(board["id"])
                pairs = {(edge["source"], edge["target"]) for edge in board["edges"]}
                self.assertEqual(len(pairs), len(board["edges"]))
                self.assertTrue(pairs <= original)
                self.assertTrue(all((b, a) not in original for a, b in pairs))
                signature = tuple(sorted(pairs))
                self.assertNotIn(signature, signatures)
                signatures.add(signature)
                node_ids = {node["id"] for node in board["nodes"]}
                self.assertTrue(all({a, b} <= node_ids for a, b in pairs))
                reached = {next(iter(node_ids))}
                for _ in node_ids:
                    reached |= {node for a, b in pairs if a in reached or b in reached for node in (a, b)}
                self.assertEqual(reached, node_ids)
        self.assertEqual(len(signatures), 12 + 52 * 3)

    def test_releases_remain_wednesday_evening_across_both_clock_changes(self):
        weeks = self.output["weeks"]
        self.assertEqual(self.output["schedule"], {
            "timezone": "Europe/Copenhagen", "release_hour": 19,
            "week_count": 52, "first_release": "2026-09-09",
        })
        releases = {week["date"]: week["release_at"] for week in weeks}
        self.assertEqual(releases["2026-09-09"], "2026-09-09T17:00:00Z")
        self.assertEqual(releases["2026-10-21"], "2026-10-21T17:00:00Z")
        self.assertEqual(releases["2026-10-28"], "2026-10-28T18:00:00Z")
        self.assertEqual(releases["2027-03-24"], "2027-03-24T18:00:00Z")
        self.assertEqual(releases["2027-03-31"], "2027-03-31T17:00:00Z")
        self.assertEqual(releases["2027-09-01"], "2027-09-01T17:00:00Z")
        for index, week in enumerate(weeks):
            self.assertEqual(date.fromisoformat(week["date"]), date(2026, 9, 9) + timedelta(weeks=index))
            self.assertEqual(datetime.fromisoformat(week["release_at"]).weekday(), 2)

    def test_windows_calendar_fallback_and_invalid_release_days(self):
        with patch.object(puzzles, "ZoneInfo", side_effect=puzzles.ZoneInfoNotFoundError):
            for day, expected in [
                ("2026-10-21", "2026-10-21T17:00:00Z"),
                ("2026-10-28", "2026-10-28T18:00:00Z"),
                ("2027-03-24", "2027-03-24T18:00:00Z"),
                ("2027-03-31", "2027-03-31T17:00:00Z"),
            ]:
                self.assertEqual(puzzles.release_timestamp(date.fromisoformat(day)), expected)
            with self.assertRaisesRegex(ValueError, "IANA timezone data"):
                puzzles.release_timestamp(date(2032, 1, 7))
        with self.assertRaisesRegex(ValueError, "Wednesday"):
            puzzles.make_puzzles(self.network, first_release="2026-09-10")
        with self.assertRaisesRegex(ValueError, "release hour"):
            puzzles.make_puzzles(self.network, release_hour=24)
        with self.assertRaisesRegex(ValueError, "between 1 and 260"):
            puzzles.make_puzzles(self.network, week_count=0)

    def test_extending_the_calendar_preserves_existing_boards_and_ids(self):
        shorter = puzzles.make_puzzles(self.network, week_count=2, release_hour=20)
        self.assertEqual(shorter["puzzles"], self.output["puzzles"])
        for short, full in zip(shorter["weeks"], self.output["weeks"]):
            self.assertEqual(short["puzzles"], full["puzzles"])
            self.assertEqual(short["id"], full["id"])
            self.assertEqual(short["date"], full["date"])
        self.assertEqual(shorter["weeks"][0]["release_at"], "2026-09-09T18:00:00Z")

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
