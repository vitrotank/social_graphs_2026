"""Graph fixtures verify shortest paths, exact centrality, and node deletion."""
import itertools
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze import adjacency, weak_components
from analyze_week3 import analyze_week3, betweenness, removal_curve, removal_svg, shortest_path


class Week3Tests(unittest.TestCase):
    def graph(self, names, edges):
        return adjacency(names, edges)[2]

    def test_betweenness_path_and_disconnected_denominator(self):
        graph = self.graph("ABCD", [("A", "B"), ("B", "C"), ("C", "D")])
        values = betweenness(graph)
        self.assertEqual(values["A"], 0)
        self.assertAlmostEqual(values["B"], 2 / 3)
        self.assertAlmostEqual(values["C"], 2 / 3)
        graph["I"] = set()
        self.assertAlmostEqual(betweenness(graph)["B"], 1 / 3)
        self.assertEqual(betweenness(graph)["I"], 0)

    def test_equal_shortest_paths_split_credit(self):
        graph = self.graph("ABCD", [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")])
        for score in betweenness(graph).values():
            self.assertAlmostEqual(score, 1 / 6)

    def test_directed_routes_and_isolate_and_zero_hops(self):
        outgoing, _, neighbors = adjacency("ABCDE", [("A", "B"), ("B", "C"), ("A", "D"), ("D", "C")])
        self.assertEqual(shortest_path(outgoing, "A", "C"), ["A", "B", "C"])
        self.assertIsNone(shortest_path(outgoing, "C", "A"))
        self.assertEqual(shortest_path(neighbors, "C", "A"), ["C", "B", "A"])
        self.assertEqual(shortest_path(outgoing, "E", "E"), ["E"])
        self.assertIsNone(shortest_path(neighbors, "E", "A"))
        with self.assertRaises(ValueError):
            shortest_path(neighbors, "missing", "A")

    def test_reverse_union_find_matches_brute_force_every_order(self):
        graph = self.graph("ABCDE", [("A", "B"), ("B", "C"), ("B", "D"), ("D", "C")])
        for order in itertools.permutations(graph):
            expected = []
            for removed in range(len(graph) + 1):
                groups = weak_components(graph, set(order[:removed]))
                expected.append(len(groups[0]) if groups else 0)
            self.assertEqual(removal_curve(graph, list(order)), expected)
        with self.assertRaises(ValueError):
            removal_curve(graph, ["A"] * 5)

    def test_reciprocal_links_and_loops_do_not_inflate_undirected_degree(self):
        graph = self.graph("ABC", [("A", "B"), ("B", "A"), ("A", "A"), ("B", "C")])
        self.assertEqual(graph["A"], {"B"})
        self.assertEqual(betweenness(graph)["B"], 1)
        self.assertEqual(removal_curve(graph, ["B", "A", "C"]), [3, 1, 1, 0])

    def test_removal_distinguishes_deleted_node_from_detached_survivors(self):
        nodes = {node: {"name": node} for node in "ABCDE"}
        edges = [("A", "B"), ("B", "C"), ("B", "D")]
        first = analyze_week3(nodes, edges, trials=9, seed=4)
        second = analyze_week3(nodes, edges, trials=9, seed=4)
        self.assertEqual(first, second)
        hub = next(row for row in first["single_removal"] if row["id"] == "B")
        isolate = next(row for row in first["single_removal"] if row["id"] == "E")
        self.assertEqual(hub["largest_component"], 1)
        self.assertEqual(hub["detached_from_original_giant"], 2)
        self.assertEqual(hub["extra_components"], 2)
        self.assertEqual(isolate["detached_from_original_giant"], 0)
        self.assertEqual(first["removal"]["denominator"], 5)
        self.assertEqual(first["removal"]["random"][0]["mean"], 4)
        self.assertEqual(first["removal"]["random"][-1]["mean"], 0)

    def test_published_routes_are_valid_and_figures_parse(self):
        data = json.loads((ROOT / "assets/data/week3.json").read_text(encoding="utf-8"))
        network = json.loads((ROOT / "assets/data/network.json").read_text(encoding="utf-8"))
        outgoing, _, neighbors = adjacency([node["id"] for node in network["nodes"]],
                                           [(edge["source"], edge["target"]) for edge in network["edges"]])
        for mode, graph in (("directed", outgoing), ("undirected", neighbors)):
            rows = data["routes"][mode]
            for source, route in rows["paths"].items():
                self.assertEqual(route, shortest_path(graph, source, "Spider-Man"))
            self.assertEqual(rows["reachable"] + rows["unreachable"], len(graph))
        ET.fromstring(removal_svg(data))
        self.assertEqual(data["single_removal"][0]["id"], "Spider-Man")
        self.assertEqual(data["single_removal"][0]["largest_component"], 271)


if __name__ == "__main__":
    unittest.main()
