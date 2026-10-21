"""Check Week 7 graph distances, nearest neighbors and frozen-text evidence.

The graph fixture has a known diamond and an island. Published paths and
scores are then checked against the original graph and corpus independently
of the analysis's path helper.
"""
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_week7 as analysis
from analyze import load_graph
from analyze_week5 import load_corpus
from analyze_week6 import build_title_mask, cosine, fit_tfidf, normalized_tokens


class ShortestPathTests(unittest.TestCase):
    def test_undirected_distances_paths_and_unreachable_nodes_have_known_answers(self):
        # All original arrows point away from A. The analysis deliberately
        # ignores direction, and equal-length paths use sorted neighbor IDs.
        nodes = {node: {} for node in ("Island", "D", "C", "B", "A")}
        edges = [("A", "C"), ("C", "D"), ("A", "B"), ("B", "D"), ("A", "B")]
        adjacency, distances, parents = analysis.shortest_paths(nodes, edges)
        self.assertEqual(set(adjacency["A"]), {"B", "C"})
        self.assertEqual(set(adjacency["D"]), {"B", "C"})
        self.assertEqual(distances["A"]["D"], 2)
        self.assertEqual(distances["D"]["A"], 2)
        self.assertEqual(distances["A"]["A"], 0)
        self.assertNotIn("Island", distances["A"])
        self.assertEqual(analysis.shortest_path("A", "D", parents), ["A", "B", "D"])
        self.assertEqual(analysis.shortest_path("D", "A", parents), ["D", "B", "A"])
        self.assertEqual(analysis.shortest_path("A", "Island", parents), [])
        self.assertEqual(analysis.shortest_path("A", "A", parents), ["A"])

    def test_graph_roster_rejects_an_unknown_endpoint(self):
        with self.assertRaises(ValueError):
            analysis.shortest_paths({"A": {}}, [("A", "outside")])

    def test_zero_cosine_ties_and_reciprocal_baseline_are_deterministic(self):
        nodes = {node: {"name": node, "url": f"https://example.test/{node}"}
                 for node in ("C", "B", "A")}
        texts = {node: "common common" for node in nodes}
        edges = [("A", "B")]
        result = analysis.analyze_week7(nodes, edges, texts)
        self.assertEqual(result, analysis.analyze_week7(dict(reversed(list(nodes.items()))),
                                                       list(reversed(edges)),
                                                       dict(reversed(list(texts.items())))))
        self.assertEqual({row["source"]: row["target"] for row in result["nearest"]},
                         {"A": "B", "B": "A", "C": "A"})
        self.assertEqual(result["result"]["zero_vectors"], 3)
        rows = {row["key"]: row for row in result["comparison"]}
        self.assertEqual(rows["1"]["nearest_count"], 2)
        self.assertEqual(rows["1"]["baseline_count"], 2)
        self.assertAlmostEqual(rows["1"]["nearest_fraction"], 2 / 3)
        self.assertAlmostEqual(rows["1"]["baseline_fraction"], 2 / 6)
        self.assertEqual(rows["disconnected"]["baseline_count"], 4)
        self.assertEqual(rows["4+"]["baseline_count"], 0)


class PublishedWeek7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "assets/data/week7.json").read_text(encoding="utf-8"))
        cls.nodes_path = ROOT / "data/raw/week1_nodes.tsv"
        cls.edges_path = ROOT / "data/raw/week1_edges.tsv"
        cls.archive = ROOT / "data/raw/marvel_pages.zip"
        cls.nodes, cls.edges = load_graph(cls.nodes_path, cls.edges_path)
        cls.texts = load_corpus(cls.archive, cls.nodes)
        cls.adjacency = {node: set() for node in cls.nodes}
        for source, target in cls.edges:
            if source != target:
                cls.adjacency[source].add(target)
                cls.adjacency[target].add(source)
        cls.distances = {}
        for source in cls.nodes:
            distance = {source: 0}
            queue = deque([source])
            while queue:
                current = queue.popleft()
                for target in cls.adjacency[current]:
                    if target not in distance:
                        distance[target] = distance[current] + 1
                        queue.append(target)
            cls.distances[source] = distance
        mask = build_title_mask(cls.nodes)
        counts = {node: Counter(term for term in normalized_tokens(text) if term not in mask)
                  for node, text in cls.texts.items()}
        cls.vectors, _ = fit_tfidf(counts)
        cls.scores = {node: {} for node in cls.nodes}
        ordered = sorted(cls.nodes)
        for index, source in enumerate(ordered):
            for target in ordered[index + 1:]:
                score = cosine(cls.vectors[source], cls.vectors[target])
                cls.scores[source][target] = cls.scores[target][source] = score

    def test_committed_data_bundle_and_figure_match_recomputed_analysis(self):
        expected = analysis.analyze_week7(self.nodes, self.edges, self.texts, self.archive,
                                          self.nodes_path, self.edges_path)
        self.assertEqual(self.data, expected)
        script = (ROOT / "assets/data/week7.js").read_text(encoding="utf-8")
        prefix = "window.WEEK7_DATA = "
        self.assertTrue(script.startswith(prefix) and script.endswith(";\n"))
        self.assertEqual(json.loads(script[len(prefix):-2]), self.data)
        figure = (ROOT / "assets/figures/week7-distance.svg").read_text(encoding="utf-8")
        self.assertEqual(figure, analysis.render_figure(self.data))
        svg = ET.fromstring(figure)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        self.assertTrue(svg.find("svg:title", ns).text)
        self.assertTrue(svg.find("svg:desc", ns).text)
        self.assertEqual(len(svg.findall(".//svg:rect/svg:title", ns)), 10,
                         "The figure must show both measured percentages in all five distance bins")
        mobile = (ROOT / self.data['figure']['mobile_path']).read_text(encoding='utf-8')
        self.assertEqual(mobile, analysis.render_mobile_figure(self.data))
        mobile_svg = ET.fromstring(mobile)
        self.assertEqual([node.text for node in svg.findall('.//svg:rect/svg:title', ns)],
                         [node.text for node in mobile_svg.findall('.//svg:rect/svg:title', ns)],
                         'The phone layout must preserve every bar and its exact denominator')

    def test_provenance_and_comparison_have_exact_counts_and_equal_source_weights(self):
        inputs = {record["path"]: record for record in self.data["corpus"]["inputs"]}
        for path in (self.archive, self.nodes_path, self.edges_path):
            relative = path.relative_to(ROOT).as_posix()
            self.assertEqual(inputs[relative]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(self.data["corpus"]["documents"], len(self.nodes))
        self.assertEqual(self.data["corpus"]["directed_edges"], len(self.edges))
        possible = len(self.nodes) * (len(self.nodes) - 1)
        pairs = [(source, target) for source in self.nodes for target in self.nodes if source != target]
        def bucket(distance):
            return "disconnected" if distance is None else "4+" if distance >= 4 else str(distance)
        baseline = Counter(bucket(self.distances[source].get(target)) for source, target in pairs)
        nearest = Counter(bucket(row["distance"]) for row in self.data["nearest"])
        comparison = self.data["comparison"]
        self.assertEqual([row["key"] for row in comparison], ["1", "2", "3", "4+", "disconnected"])
        for row in comparison:
            self.assertEqual(row["nearest_count"], nearest[row["key"]])
            self.assertEqual(row["baseline_count"], baseline[row["key"]])
            self.assertAlmostEqual(row["nearest_fraction"], nearest[row["key"]] / len(self.nodes))
            self.assertAlmostEqual(row["baseline_fraction"], baseline[row["key"]] / possible)
        self.assertEqual(sum(row["nearest_count"] for row in comparison), len(self.nodes))
        self.assertEqual(sum(row["baseline_count"] for row in comparison), possible)
        self.assertAlmostEqual(sum(row["nearest_fraction"] for row in comparison), 1)
        self.assertAlmostEqual(sum(row["baseline_fraction"] for row in comparison), 1)
        result = self.data["result"]
        self.assertEqual(result["eligible_ordered_choices"], possible)
        self.assertEqual(result["possible_pairs"], possible // 2)
        self.assertEqual(result["disconnected_pairs"], baseline["disconnected"] // 2)
        self.assertEqual(result["far_pairs"], baseline["4+"] // 2)
        self.assertEqual(result["connected_pairs"] + result["disconnected_pairs"], possible // 2)
        self.assertEqual(result["isolated_nodes"], sum(not neighbors for neighbors in self.adjacency.values()))

    def test_nearest_neighbors_use_all_articles_and_measured_masked_cosines(self):
        rows = self.data["nearest"]
        self.assertEqual(len(rows), len(self.nodes))
        self.assertEqual({row["source"] for row in rows}, set(self.nodes))
        for row in rows:
            source, target = row["source"], row["target"]
            with self.subTest(source=source):
                self.assertNotEqual(source, target)
                self.assertEqual(row["source_url"], self.nodes[source]["url"])
                self.assertEqual(row["target_url"], self.nodes[target]["url"])
                candidates = sorted((node for node in self.nodes if node != source),
                                    key=lambda node: (-self.scores[source][node], node))
                self.assertEqual(target, candidates[0])
                self.assertAlmostEqual(row["similarity"], self.scores[source][target], places=8)
                self.assertTrue(math.isfinite(row["similarity"]))
                self.assertTrue(0 <= row["similarity"] <= 1)

    def test_far_cases_follow_the_published_ranking_rule_and_exclude_unreachable_pairs(self):
        ordered = sorted(self.nodes)
        census = sorted(((self.scores[source][target], source, target)
                         for index, source in enumerate(ordered) for target in ordered[index + 1:]),
                        key=lambda pair: (-pair[0], pair[1], pair[2]))
        ranks = {(source, target): rank for rank, (_, source, target) in enumerate(census, 1)}
        far = [(source, target) for _, source, target in census
               if self.distances[source].get(target) is not None and self.distances[source][target] >= 4]
        rows = self.data["top_far_pairs"]
        self.assertEqual([(row["source"], row["target"]) for row in rows], far[:20])
        self.assertEqual([(row["source"], row["target"]) for row in self.data["cases"]], far[:3])
        for index, row in enumerate(rows, 1):
            self.assertEqual(row["eligible_rank"], index)
            self.assertEqual(row["global_rank"], ranks[(row["source"], row["target"])])
        self.assertGreaterEqual(len(self.data["cases"]), 2)
        self.assertTrue(all(case["interpretation"] for case in self.data["cases"]))
        disconnected = self.data["disconnected_case"]
        expected = next((source, target) for _, source, target in census
                        if target not in self.distances[source])
        self.assertEqual((disconnected["source"], disconnected["target"]), expected)
        self.assertTrue(disconnected["interpretation"])

    def test_every_published_pair_has_a_valid_shortest_path_or_is_disconnected(self):
        for row in self.data["nearest"] + self.data["top_far_pairs"] + self.data["cases"] + [self.data["disconnected_case"]]:
            source, target = row["source"], row["target"]
            with self.subTest(source=source, target=target):
                distance = self.distances[source].get(target)
                self.assertEqual(row["distance"], distance)
                if distance is None:
                    self.assertEqual(row["path"], [])
                else:
                    path = row["path"]
                    self.assertEqual((path[0], path[-1]), (source, target))
                    self.assertEqual(len(path) - 1, distance)
                    self.assertEqual(len(path), len(set(path)))
                    for left, right in zip(path, path[1:]):
                        self.assertIn(right, self.adjacency[left])

    def test_terms_and_every_visible_excerpt_are_traceable_to_frozen_text(self):
        mask = set(build_title_mask(self.nodes))
        for row in self.data["nearest"] + self.data["cases"] + [self.data["disconnected_case"]]:
            source, target = row["source"], row["target"]
            terms = row["terms"]
            self.assertTrue(mask.isdisjoint(term["term"] for term in terms))
            self.assertEqual(len(terms), len({term["term"] for term in terms}))
            self.assertEqual([term["contribution"] for term in terms],
                             sorted((term["contribution"] for term in terms), reverse=True))
            self.assertLessEqual(sum(term["contribution"] for term in terms), row["similarity"] + 1e-8)
            for term in terms:
                contribution = self.vectors[source][term["term"]] * self.vectors[target][term["term"]]
                self.assertAlmostEqual(term["contribution"], contribution, places=8)
                self.assertAlmostEqual(term["share"], contribution / row["similarity"], places=6)
            self.assertEqual({excerpt["node"] for excerpt in row["sources"]}, {source, target})
            for excerpt in row["sources"]:
                text = self.texts[excerpt["node"]]
                start, end = excerpt["start"], excerpt["end"]
                self.assertTrue(0 <= start < end <= len(text))
                self.assertEqual(text[start:end], excerpt["text"])
                self.assertEqual(text[max(0, start - len(excerpt["before"])):start], excerpt["before"])
                self.assertEqual(text[end:end + len(excerpt["after"])], excerpt["after"])
                self.assertEqual(excerpt["url"], self.nodes[excerpt["node"]]["url"])


if __name__ == "__main__":
    unittest.main()
