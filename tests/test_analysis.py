"""Independent tiny graphs check scientific meaning and input integrity."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/analyze.py"
SPEC = importlib.util.spec_from_file_location("analysis", SCRIPT)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.nodes = self.path / "nodes.tsv"
        self.edges = self.path / "edges.tsv"
        self.nodes.write_text("# Frozen fixture\nnode_id\tname\turl\nA\tAlpha\t\nB\tBeta\t\nC\tGamma\t\nD\tDelta\t\nE\tEpsilon\t\n", encoding="utf-8")
        # A <-> B -> C. D and E are invisible in the edge file.
        self.edges.write_text("# source\ttarget\nA\tB\nB\tA\nB\tC\n", encoding="utf-8")

    def test_isolates_direction_components_and_reciprocity(self):
        nodes, edges = analysis.load_graph(self.nodes, self.edges)
        network, summary = analysis.analyze(nodes, edges, iterations=2)
        by_id = {node["id"]: node for node in network["nodes"]}
        self.assertEqual(summary["nodes"], 5)
        self.assertEqual(summary["edges"], 3)
        self.assertEqual(summary["isolates"], ["D", "E"])
        self.assertEqual([part["size"] for part in summary["weak_components"]], [3, 1, 1])
        self.assertEqual(summary["strong_component_sizes"], [2, 1, 1, 1])
        self.assertEqual((by_id["B"]["in_degree"], by_id["B"]["out_degree"], by_id["B"]["degree"], by_id["B"]["total_degree"]), (1, 2, 2, 3))
        self.assertAlmostEqual(summary["reciprocity"], 2 / 3)
        self.assertEqual(summary["reciprocal_pairs"], 1)
        self.assertEqual(summary["degree_distributions"]["in"], [{"degree": 0, "count": 2, "probability": .4}, {"degree": 1, "count": 3, "probability": .6}])

    def test_degree_conservation_and_normalization(self):
        network, summary = analysis.analyze(*analysis.load_graph(self.nodes, self.edges), iterations=2)
        for key in ("in_degree", "out_degree"):
            self.assertEqual(sum(node[key] for node in network["nodes"]), len(network["edges"]))
        for direction in ("in", "out"):
            self.assertEqual(sum(point["count"] for point in summary["degree_distributions"][direction]), 5)
            self.assertAlmostEqual(sum(point["probability"] for point in summary["degree_distributions"][direction]), 1)

    def test_bridge_removal_really_breaks_a_component(self):
        _, _, neighbors = analysis.adjacency("ABCDE", [("A", "B"), ("B", "C")])
        experiment = analysis.hub_removal(neighbors, ["B", "A", "C", "D", "E"], trials=10)
        first = next(row for row in experiment["steps"] if row["removed"] == 1)
        self.assertEqual(first["targeted_largest_component"], 1)
        self.assertEqual(first["targeted_fraction_original"], .2)
        self.assertEqual(first["targeted_fraction_remaining"], .25)

    def test_unknown_endpoint_is_rejected_instead_of_becoming_a_node(self):
        self.edges.write_text("A\tUnknown\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing from the roster"):
            analysis.load_graph(self.nodes, self.edges)

    def test_duplicate_edges_and_roster_rows_are_rejected(self):
        self.edges.write_text("A\tB\nA\tB\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate directed edge"):
            analysis.load_graph(self.nodes, self.edges)
        self.nodes.write_text("node_id\tname\nA\tAlpha\nA\tAgain\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate node"):
            analysis.load_graph(self.nodes, self.edges)

    def test_missing_roster_fails_without_substitute_data(self):
        with self.assertRaisesRegex(ValueError, "Missing input"):
            analysis.load_graph(self.path / "absent.tsv", self.edges)

    def test_empty_edge_list_preserves_every_roster_node(self):
        self.edges.write_text("# source\ttarget\n", encoding="utf-8")
        network, summary = analysis.analyze(*analysis.load_graph(self.nodes, self.edges), iterations=2)
        self.assertEqual(summary["isolate_count"], 5)
        self.assertIsNone(summary["reciprocity"])
        self.assertEqual(summary["weak_component_count"], 5)
        self.assertTrue(all(node["total_degree"] == 0 for node in network["nodes"]))

    def test_layout_and_experiment_are_repeatable_and_svg_is_valid(self):
        graph = analysis.load_graph(self.nodes, self.edges)
        first = analysis.analyze(*graph, iterations=4)
        second = analysis.analyze(*graph, iterations=4)
        self.assertEqual(first, second)
        for node in first[0]["nodes"]:
            self.assertTrue(0 <= node["x"] <= 1 and 0 <= node["y"] <= 1)
        for logarithmic in (False, True):
            svg = analysis.degree_svg(first[1], logarithmic)
            ET.fromstring(svg)
            if logarithmic:
                self.assertIn("Zero-degree pages excluded", svg)


if __name__ == "__main__":
    unittest.main()
