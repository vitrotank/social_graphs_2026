"""Scientific checks for centrality and the committed hyperlink evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("grunge_analysis", ROOT / "scripts/crawl_grunge.py")
grunge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(grunge)


class GrungeTests(unittest.TestCase):
    def test_star_bridge_and_disconnected_normalization(self):
        graph = {"hub": {"a", "b", "c"}, "a": {"hub"}, "b": {"hub"}, "c": {"hub"}}
        scores = grunge.betweenness(graph)
        self.assertAlmostEqual(scores["hub"], 1)
        self.assertEqual([scores[node] for node in ("a", "b", "c")], [0, 0, 0])
        graph["isolated"] = set()
        self.assertAlmostEqual(grunge.betweenness(graph)["hub"], .5)

    def test_equal_shortest_paths_share_credit(self):
        diamond = {"a": {"b", "c"}, "b": {"a", "d"}, "c": {"a", "d"}, "d": {"b", "c"}}
        for value in grunge.betweenness(diamond).values():
            self.assertAlmostEqual(value, 1 / 6)

    def test_every_sample_edge_has_matching_source_evidence(self):
        snapshot = json.loads((ROOT / "data/grunge/snapshot.json").read_text(encoding="utf-8"))
        roster = {page["title"] for page in snapshot["pages"]}
        self.assertEqual(len(roster), 15)
        for page in snapshot["pages"]:
            self.assertIsNone(page["revision_id"])
            self.assertEqual(set(page["links"]), {edge["target"] for edge in page["evidence"]})
            self.assertLessEqual(set(page["links"]), roster - {page["title"]})
            for edge in page["evidence"]:
                self.assertEqual(edge["source_url"], page["url"])
                self.assertEqual(edge["target_url"], "https://en.wikipedia.org/wiki/" + edge["target"].replace(" ", "_"))

    def test_frozen_output_matches_recomputed_analysis(self):
        raw = (ROOT / "data/grunge/snapshot.json").read_bytes()
        rebuilt = grunge.analyze(json.loads(raw))
        committed = json.loads((ROOT / "assets/data/grunge.json").read_text(encoding="utf-8"))
        self.assertEqual(committed["meta"]["snapshot_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(rebuilt["nodes"], committed["nodes"])
        self.assertEqual(rebuilt["edges"], committed["edges"])
        self.assertEqual(rebuilt["summary"], committed["summary"])
        self.assertEqual(sum(node["in_degree"] for node in rebuilt["nodes"]), 55)
        self.assertEqual(rebuilt["summary"]["components"], [15])


if __name__ == "__main__":
    unittest.main()
