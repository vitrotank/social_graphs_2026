"""Numerical checks and source evidence for the Week 6 name ablation.

Small fixtures have hand-computable answers; the frozen-corpus checks prevent
the published figure, offline payload and quoted source passages from drifting.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_week6 as analysis
from analyze import load_graph
from analyze_week5 import load_corpus


class TfidfTests(unittest.TestCase):
    def test_unsmoothed_idf_l2_normalization_and_cosine_have_known_values(self):
        counts = {
            "a": Counter({"common": 2, "amber": 2, "blue": 1}),
            "b": Counter({"common": 1, "blue": 2}),
            "c": Counter({"common": 1, "green": 1}),
        }
        vectors, idf = analysis.fit_tfidf(counts)
        rare, shared = math.log(3), math.log(3 / 2)
        norm_a = math.sqrt((2 * rare) ** 2 + shared ** 2)
        self.assertEqual(idf["common"], 0)
        self.assertAlmostEqual(idf["amber"], rare)
        self.assertAlmostEqual(idf["blue"], shared)
        self.assertAlmostEqual(vectors["a"]["amber"], 2 * rare / norm_a)
        self.assertAlmostEqual(vectors["a"]["blue"], shared / norm_a)
        self.assertEqual(vectors["a"].get("common", 0), 0)
        for vector in vectors.values():
            self.assertAlmostEqual(sum(value * value for value in vector.values()), 1)
        self.assertAlmostEqual(analysis.cosine(vectors["a"], vectors["b"]), shared / norm_a)
        self.assertAlmostEqual(analysis.cosine(vectors["b"], vectors["a"]), shared / norm_a)
        self.assertEqual(analysis.cosine(vectors["a"], vectors["c"]), 0)
        self.assertAlmostEqual(analysis.cosine(vectors["a"], vectors["a"]), 1)

    def test_empty_and_corpus_wide_terms_do_not_produce_nan(self):
        vectors, idf = analysis.fit_tfidf({"a": Counter(common=3), "b": Counter(common=1)})
        self.assertEqual(idf["common"], 0)
        self.assertEqual(analysis.cosine(vectors["a"], vectors["b"]), 0)
        self.assertEqual(analysis.cosine({}, {"rare": 1}), 0)
        self.assertTrue(all(math.isfinite(value) for row in vectors.values() for value in row.values()))

    def test_name_mask_uses_titles_and_excludes_parenthetical_metadata(self):
        nodes = {
            "Storm": {},
            "Human_Torch_(Johnny_Storm)": {},
            "Doctor_Strange_(Marvel_Comics)": {},
            "The_Thing_(comics)": {},
        }
        mask = analysis.build_title_mask(nodes)
        self.assertTrue({"storm", "human", "torch", "doctor", "strange", "thing"} <= mask)
        self.assertTrue({"johnny", "marvel", "comics", "the"}.isdisjoint(mask))
        self.assertEqual(analysis.normalized_tokens("Storm's STORM storm’s fire-resistant 2099"),
                         ["storm", "storm", "storm", "fire", "resistant"])

    def test_title_ablation_can_reveal_shared_story_words(self):
        # The repeated surname wins before masking; the common weather words
        # win afterwards. No expected answer depends on the Marvel corpus.
        nodes = {"Storm": {}, "Human_Torch_(Johnny_Storm)": {}, "Thor": {}}
        texts = {
            "Storm": "Storm " * 10 + "weather thunder cloud",
            "Human_Torch_(Johnny_Storm)": "Storm " * 10 + "flame",
            "Thor": "weather thunder cloud",
        }
        counts = {node: Counter(analysis.normalized_tokens(text)) for node, text in texts.items()}
        before, _ = analysis.fit_tfidf(counts)
        mask = analysis.build_title_mask(nodes)
        after, _ = analysis.fit_tfidf({node: Counter({term: n for term, n in bag.items() if term not in mask})
                                       for node, bag in counts.items()})
        storm, torch, thor = "Storm", "Human_Torch_(Johnny_Storm)", "Thor"
        self.assertGreater(analysis.cosine(before[storm], before[torch]),
                           analysis.cosine(before[storm], before[thor]))
        self.assertAlmostEqual(analysis.cosine(after[storm], after[thor]), 1)
        self.assertEqual(analysis.cosine(after[storm], after[torch]), 0)
        metadata = {node: {"name": node, "url": f"https://example.test/{node}"} for node in nodes}
        rows = {row["node"]: row for row in analysis.analyze_week6(metadata, [], texts)["rows"]}
        self.assertEqual(rows[storm]["before"]["neighbor"], torch)
        self.assertEqual(rows[storm]["after"]["neighbor"], thor)
        self.assertTrue(rows[storm]["changed"])

    def test_full_pipeline_is_deterministic_and_resolves_equal_scores_by_identifier(self):
        nodes = {node: {"name": node, "url": f"https://example.test/{node}"}
                 for node in ("Charlie", "Beth", "Alex")}
        texts = {node: "common common" for node in nodes}
        result = analysis.analyze_week6(nodes, [], texts)
        self.assertEqual(analysis.analyze_week6(dict(reversed(list(nodes.items()))), [],
                                             dict(reversed(list(texts.items())))), result)
        self.assertEqual({row["node"]: row["before"]["neighbor"] for row in result["rows"]},
                         {"Alex": "Beth", "Beth": "Alex", "Charlie": "Alex"})
        self.assertEqual(result["result"]["zero_vectors_before"], 3)
        self.assertEqual(result["result"]["zero_vectors_after"], 3)


class PublishedWeek6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "assets/data/week6.json").read_text(encoding="utf-8"))
        cls.nodes, cls.edges = load_graph(ROOT / "data/raw/week1_nodes.tsv", ROOT / "data/raw/week1_edges.tsv")
        cls.archive = ROOT / "data/raw/marvel_pages.zip"
        cls.texts = load_corpus(cls.archive, cls.nodes)

    def test_committed_outputs_match_recomputed_frozen_analysis(self):
        expected = analysis.analyze_week6(self.nodes, self.edges, self.texts, self.archive)
        self.assertEqual(self.data, expected)
        script = (ROOT / "assets/data/week6.js").read_text(encoding="utf-8")
        prefix = "window.WEEK6_DATA = "
        self.assertTrue(script.startswith(prefix) and script.endswith(";\n"))
        self.assertEqual(json.loads(script[len(prefix):-2]), self.data)
        figure = (ROOT / self.data["figure"]["path"]).read_text(encoding="utf-8")
        self.assertEqual(figure, analysis.render_figure(self.data))
        svg = ET.fromstring(figure)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        self.assertIsNotNone(svg.find("svg:title", ns))
        self.assertIsNotNone(svg.find("svg:desc", ns))
        self.assertEqual(len(svg.findall(".//svg:circle/svg:title", ns)), len(self.nodes))

    def test_every_article_and_removed_occurrence_uses_the_same_denominator(self):
        data, rows = self.data, self.data["rows"]
        self.assertEqual(len(rows), len(self.nodes))
        self.assertEqual({row["node"] for row in rows}, set(self.nodes))
        self.assertEqual(data["corpus"]["documents"], len(self.nodes))
        self.assertEqual(data["corpus"]["sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual(data["result"]["possible_pairs"], len(self.nodes) * (len(self.nodes) - 1) // 2)
        mask = set(data["title_mask"])
        for row in rows:
            with self.subTest(node=row["node"]):
                tokens = analysis.normalized_tokens(self.texts[row["node"]])
                self.assertEqual(row["token_count"], len(tokens))
                self.assertEqual(row["removed_tokens"], sum(term in mask for term in tokens))
                self.assertAlmostEqual(row["removed_token_fraction"], row["removed_tokens"] / len(tokens), places=8)
                self.assertEqual(row["changed"], row["before"]["neighbor"] != row["after"]["neighbor"])
                self.assertLessEqual(row["original_pair_after_similarity"], row["after"]["similarity"])
        result = data["result"]
        self.assertEqual(result["changed"], sum(row["changed"] for row in rows))
        self.assertEqual(result["changed"] + result["unchanged"], len(rows))
        self.assertAlmostEqual(result["changed_fraction"], result["changed"] / len(rows))
        self.assertEqual(result["removed_tokens"], sum(row["removed_tokens"] for row in rows))
        self.assertEqual(data["corpus"]["tokens"], sum(row["token_count"] for row in rows))
        self.assertAlmostEqual(result["removed_token_fraction"], result["removed_tokens"] / data["corpus"]["tokens"])

    def test_neighbor_scores_terms_and_link_status_are_consistent(self):
        mask, edges = set(self.data["title_mask"]), set(self.edges)
        for row in self.data["rows"]:
            for condition in ("before", "after"):
                neighbor = row[condition]
                with self.subTest(node=row["node"], condition=condition):
                    self.assertIn(neighbor["neighbor"], self.nodes)
                    self.assertNotEqual(neighbor["neighbor"], row["node"])
                    self.assertEqual(neighbor["url"], self.nodes[neighbor["neighbor"]]["url"])
                    self.assertTrue(0 <= neighbor["similarity"] <= 1)
                    self.assertEqual(neighbor["linked"],
                                     (row["node"], neighbor["neighbor"]) in edges or
                                     (neighbor["neighbor"], row["node"]) in edges)
                    terms = neighbor["terms"]
                    self.assertLessEqual(sum(term["contribution"] for term in terms), neighbor["similarity"] + 1e-8)
                    self.assertEqual(len({term["term"] for term in terms}), len(terms))
                    self.assertEqual([term["contribution"] for term in terms],
                                     sorted((term["contribution"] for term in terms), reverse=True))
                    if condition == "after":
                        self.assertTrue(mask.isdisjoint(term["term"] for term in terms))
                    for term in terms:
                        self.assertGreater(term["contribution"], 0)
                        self.assertAlmostEqual(term["share"], term["contribution"] / neighbor["similarity"], places=6)
        for condition in ("before", "after"):
            self.assertEqual(self.data["result"][f"linked_{condition}"],
                             sum(row[condition]["linked"] for row in self.data["rows"]))

    def test_every_audited_passage_is_exact_frozen_text_with_traceable_context(self):
        self.assertGreaterEqual(len(self.data["cases"]), 2,
                                "The post must inspect source pages behind its numerical story")
        for case in self.data["cases"]:
            self.assertTrue(case["interpretation"])
            self.assertTrue({case["source"], case["target"]} <= {source["node"] for source in case["sources"]})
            for source in case["sources"]:
                with self.subTest(case=case["id"], node=source["node"]):
                    text = self.texts[source["node"]]
                    start, end = source["start"], source["end"]
                    self.assertTrue(0 <= start < end <= len(text))
                    self.assertEqual(text[start:end], source["text"])
                    self.assertEqual(text[max(0, start - len(source["before"])):start], source["before"])
                    self.assertEqual(text[end:end + len(source["after"])], source["after"])
                    self.assertEqual(source["url"], self.nodes[source["node"]]["url"])


if __name__ == "__main__":
    unittest.main()
