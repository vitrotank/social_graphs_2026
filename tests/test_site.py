"""Check the published artifact against its sources in an isolated build tree."""

from collections import Counter
import csv
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("site_build", REPO / "scripts/build.py")
build = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(REPO / "scripts"), *sys.path]):
    SPEC.loader.exec_module(build)


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = []
        self.links = []
        self.references = []
        self.images = []
        self.scripts = []
        self.inputs = []
        self.labels = set()
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        for key in ("href", "src"):
            if attributes.get(key):
                self.links.append(attributes[key])
        for key in ("aria-labelledby", "aria-describedby", "for", "list"):
            self.references.extend(attributes.get(key, "").split())
        if tag == "label" and attributes.get("for"):
            self.labels.add(attributes["for"])
        if tag == "input":
            self.inputs.append(attributes)
        if tag == "img":
            self.images.append(attributes)
        if tag == "script" and attributes.get("src"):
            self.scripts.append(attributes["src"])


def tsv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader((line for line in handle if line.strip() and not line.startswith("#")), delimiter="\t"))


class SiteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="crosstalk-site-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        # Copy only build inputs. Neither render nor stage touches the real repo.
        for relative in (
            "templates/explore.html", "design.css", "explore.css",
            "templates/week5.html", "week5.css", "week5.js", "assets/data/week5.json", "assets/data/week5.js",
            "data/raw/marvel_pages.zip", "data/week5/README.md",
            "templates/week3.html", "templates/week4.html", "templates/louvain.html", "templates/switchboard.html", "templates/grunge.html",
            "week3.css", "week3.js", "week4.css", "week4.js", "louvain.js", "grunge.css", "grunge.js",
            "week1.css", "week2-figures.css", "week2-figures.js", "week3-story.css", "week3-story.js", "home.css", "journal.css", "journal.js",
            "assets/data/week3.json", "assets/data/week3.js", "assets/data/week4.json", "assets/data/week4.js", "assets/figures/week3-removal.svg",
            "assets/data/grunge.json", "assets/data/grunge.js", "data/grunge/snapshot.json", "data/grunge/README.md",
            "site.json", "templates/home.html", "templates/week1.html", "templates/week2.html", "templates/play.html", "templates/cerebro.html",
            "style.css", "app.js", "home.js", "game.css", "game.js", "week2.js",
            "assets/data/network.json", "assets/data/summary.json",
            "assets/figures/degree-linear.svg", "assets/figures/degree-loglog.svg",
            "assets/figures/hero-models.svg", "assets/figures/ccdf-models.svg", "assets/figures/ccdf-fit.svg",
            "assets/figures/clustering-nulls.svg", "assets/figures/growth-models.svg",
            "data/raw/week1_nodes.tsv", "data/raw/week1_edges.tsv", "data/raw/README.md",
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / relative, target)
        self.root_patch = patch.object(build, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_render_is_repeatable_with_working_links_and_accessible_references(self):
        public_files = build.render()
        first = {name: (self.root / name).read_bytes() for name in public_files}
        self.assertEqual(build.render(), public_files)
        self.assertEqual(first, {name: (self.root / name).read_bytes() for name in public_files})
        pages = {path for path in public_files if path.suffix == ".html"}
        self.assertTrue({Path("index.html"), Path("week1/index.html"), Path("week3/index.html"),
                         Path("play/index.html"), Path("play/switchboard.html"), Path("grunge/index.html")} <= pages)
        documents = {}
        for relative in pages:
            html = (self.root / relative).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"@@[A-Z][A-Z0-9_]*@@", html), f"Unresolved template value in {relative}")
            self.assertNotIn("polyfill.io", html)
            self.assertNotIn("open an issue", html.casefold())
            documents[self.root / relative] = Document(html)
        linked_pages = {}
        for path, document in documents.items():
            with self.subTest(page=str(path.relative_to(self.root))):
                self.assertEqual(len(document.ids), len(set(document.ids)), "HTML IDs must be unique")
                for reference in document.references:
                    self.assertIn(reference, document.ids, f"Broken label or accessibility reference: {reference}")
                for image in document.images:
                    self.assertIn("alt", image, f"Missing image alternative: {image}")
                for control in document.inputs:
                    self.assertTrue(control.get("aria-label") or control.get("aria-labelledby") or control.get("id") in document.labels,
                                    f"Input has no accessible label: {control}")
                for source in document.scripts:
                    self.assertFalse(urlsplit(source).scheme or source.startswith("//"), "The site must run without a remote script dependency")
                linked_pages[path] = set()
                for reference in document.links:
                    parsed = urlsplit(reference)
                    if parsed.scheme or parsed.netloc:
                        continue
                    self.assertFalse(parsed.path.startswith("/"), f"Root-relative link breaks GitHub project paths: {reference}")
                    destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
                    self.assertTrue(destination.is_relative_to(self.root), f"Local link escapes the published site: {reference}")
                    self.assertTrue(destination.is_file(), f"Local link has no explicit file for offline viewing: {reference}")
                    self.assertIn(destination.relative_to(self.root), public_files, f"Link target is excluded from publication: {reference}")
                    if destination in documents:
                        linked_pages[path].add(destination)
                    if parsed.fragment:
                        target = documents.get(destination) or Document(destination.read_text(encoding="utf-8"))
                        self.assertIn(unquote(parsed.fragment), target.ids, f"Local fragment is missing: {reference}")
        home = self.root / "index.html"
        for relative in ("week1/index.html", "play/index.html"):
            page = self.root / relative
            self.assertIn(page, linked_pages[home], f"Homepage must link to {relative}")
            self.assertIn(home, linked_pages[page], f"{relative} must link back home")
        story = self.root / "week3/index.html"
        game = self.root / "play/switchboard.html"
        b_side = self.root / "grunge/index.html"
        self.assertIn(game, linked_pages[home], "Homepage must expose the separate Week 3 game")
        for companion in (game, b_side):
            self.assertIn(companion, linked_pages[story], "Week 3 must link to its companions")
            self.assertIn(story, linked_pages[companion], "Week 3 companions must link back to the story")
        self.assertTrue({"blackout", "pathfinder"} <= set(documents[story].ids), "Existing story bookmarks must remain valid")
        for control in ("w3-disconnect", "w3-remove-character", "w3-removal-count", "w3-route-form", "w3-route-character"):
            self.assertNotIn(control, documents[story].ids, "Game controls belong on their separate page")
            self.assertIn(control, documents[game].ids, "The separate game must retain its controls")
        self.assertFalse(any(source.endswith("week3.js") for source in documents[story].scripts),
                         "The story must not load game scripts or data")
        self.assertIn("../week3.js", documents[game].scripts)
        self.assertTrue(any(image.get("src", "").endswith("week3-removal.svg") for image in documents[story].images),
                        "The story must retain its static removal figure")

    def test_new_published_week_updates_homepage_and_creates_its_page(self):
        config_path = self.root / "site.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["weeks"][5].update({"status": "published", "title": "Sixth dispatch",
                                   "summary": "A new question for the journal.",
                                   "path": "week6/index.html", "template": "week6.html"})
        config_path.write_text(json.dumps(config), encoding="utf-8")
        (self.root / "templates/week6.html").write_text(
            '<!doctype html><html><body>@@HEADER@@<h1>Sixth dispatch</h1>@@FOOTER@@</body></html>', encoding="utf-8")
        files = build.render()
        self.assertIn(Path("week6/index.html"), files)
        home = (self.root / "index.html").read_text(encoding="utf-8")
        self.assertIn("Sixth dispatch", home)
        self.assertIn('href="week6/index.html"', home)
        self.assertIn("Read Week 6", home)
        self.assertIn('href="../index.html"', (self.root / "week6/index.html").read_text(encoding="utf-8"))

    def test_browser_payload_preserves_raw_nodes_edges_and_measured_degrees(self):
        config_path = self.root / "site.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["arcade"] = {"release_hour": 18, "week_count": 3, "first_release": "2026-09-09"}
        config_path.write_text(json.dumps(config), encoding="utf-8")
        build.render()
        javascript = (self.root / "assets/data/network.js").read_text(encoding="utf-8")
        prefix = "window.CROSSTALK_DATA = "
        self.assertTrue(javascript.startswith(prefix) and javascript.endswith(";\n"))
        payload = json.loads(javascript[len(prefix):-2])
        network, summary = payload["network"], payload["summary"]
        self.assertEqual(network, json.loads((self.root / "assets/data/network.json").read_text(encoding="utf-8")))
        self.assertEqual(summary, json.loads((self.root / "assets/data/summary.json").read_text(encoding="utf-8")))
        roster_rows = tsv_rows(self.root / "data/raw/week1_nodes.tsv")
        column = roster_rows[0].index("node_id")
        roster = {row[column] for row in roster_rows[1:]}
        raw_edges = {tuple(row) for row in tsv_rows(self.root / "data/raw/week1_edges.tsv")}
        self.assertEqual({node["id"] for node in network["nodes"]}, roster)
        self.assertEqual({(edge["source"], edge["target"]) for edge in network["edges"]}, raw_edges)
        self.assertEqual((summary["nodes"], summary["edges"]), (len(roster), len(raw_edges)))
        incoming = Counter(target for _, target in raw_edges)
        outgoing = Counter(source for source, _ in raw_edges)
        for node in network["nodes"]:
            self.assertEqual((node["in_degree"], node["out_degree"]), (incoming[node["id"]], outgoing[node["id"]]))
        self.assertEqual(set(summary["isolates"]), {node for node in roster if not incoming[node] and not outgoing[node]})

        # The game uses an offline JavaScript payload; its downloadable source
        # must expose exactly the same generated puzzle facts.
        javascript = (self.root / "assets/data/puzzles.js").read_text(encoding="utf-8")
        prefix = "window.CROSSTALK_PUZZLES = "
        self.assertTrue(javascript.startswith(prefix) and javascript.endswith(";\n"))
        self.assertEqual(json.loads(javascript[len(prefix):-2]),
                         json.loads((self.root / "assets/data/puzzles.json").read_text(encoding="utf-8")))
        puzzles = json.loads(javascript[len(prefix):-2])
        self.assertEqual(puzzles["schedule"]["release_hour"], 18)
        self.assertEqual(len(puzzles["weeks"]), 3)
        self.assertEqual(puzzles["weeks"][0]["release_at"], "2026-09-09T16:00:00Z")

    def test_editorial_exhibits_use_only_frozen_nodes_edges_and_analysis(self):
        build.render()
        def bundle(name, variable):
            text = (self.root / name).read_text(encoding="utf-8")
            prefix = f"window.{variable} = "
            self.assertTrue(text.startswith(prefix) and text.endswith(";\n"))
            return json.loads(text[len(prefix):-2])
        cover = bundle("assets/data/cover.js", "CROSSTALK_COVER")
        marvel = json.loads((self.root / "assets/data/network.json").read_text(encoding="utf-8"))
        philosopher = json.loads((self.root / "assets/data/week4.json").read_text(encoding="utf-8"))
        originals = {"marvel": marvel["nodes"], "philosophers": philosopher["explorer"]["nodes"]}
        source_pairs = {
            "marvel": {frozenset((edge["source"], edge["target"])) for edge in marvel["edges"]},
            "philosophers": {frozenset((edge["source"], edge["target"])) for edge in philosopher["explorer"]["edges"] if edge["alpha"] < .5},
        }
        for name, exhibit in cover.items():
            roster = {node["id"]: node for node in originals[name]}
            shown = {node["id"] for node in exhibit["nodes"]}
            self.assertLess(len(shown), len(roster), "The lightweight cover must disclose its sample")
            self.assertIn("Selected", exhibit["sampleNote"])
            for node in exhibit["nodes"]:
                self.assertEqual(node["degree"], roster[node["id"]]["degree"])
                self.assertEqual(node["label"], roster[node["id"]]["label"])
                self.assertTrue(0 <= node["x"] <= 1 and 0 <= node["y"] <= 1)
            for edge in exhibit["edges"]:
                pair = frozenset((edge["source"], edge["target"]))
                self.assertTrue(pair <= shown)
                self.assertIn(pair, source_pairs[name], "A cover mark must be an observed link")
        figure = bundle("assets/data/week3-figure.js", "CROSSTALK_WEEK3_FIGURE")
        source = json.loads((self.root / "assets/data/week3.json").read_text(encoding="utf-8"))
        self.assertEqual(figure["nodes"], source["nodes"])
        for key, value in figure["removal"].items():
            self.assertEqual(value, source["removal"][key])
        self.assertTrue(all(row in source["single_removal"] for row in figure["ranking"]))

    def test_staging_publishes_only_the_allowlist_and_preserves_its_bytes(self):
        # A workspace may contain control files that must never reach Pages.
        for relative in (".git/HEAD", ".codex/private.txt", ".agents/private.txt", ".preview/private.txt", "scripts/private.py", "tests/private.py", "unrelated.txt"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private fixture", encoding="utf-8")
        public_files = build.render()
        forbidden = {".git", ".codex", ".agents", ".preview", "scripts", "tests", "templates"}
        self.assertFalse(any(path.parts[0] in forbidden for path in public_files))
        self.assertNotIn(Path("unrelated.txt"), public_files)
        output = self.root / "_site"
        build.stage(output, public_files)
        self.assertEqual({path.relative_to(output) for path in output.rglob("*") if path.is_file()}, set(public_files))
        for relative in public_files:
            self.assertEqual((output / relative).read_bytes(), (self.root / relative).read_bytes())
        # Rebuilding into its own exact artifact is supported and deterministic.
        build.stage(output, public_files)

    def test_staging_rejects_unsafe_destinations_without_overwriting_source_files(self):
        public_files = build.render()
        original = {path: (self.root / path).read_bytes() for path in public_files}
        for destination in (self.root, self.root.parent, self.root / "../outside-site", self.root / "assets", self.root / "data/nested", self.root / "scripts", self.root / ".git", self.root / ".codex", self.root / ".agents", self.root / ".preview", self.root / "templates", self.root / "tests", self.root / "week1", self.root / "play/nested"):
            with self.subTest(destination=str(destination)):
                with self.assertRaises(ValueError):
                    build.stage(destination, public_files)
        occupied = self.root / "_occupied"
        occupied.mkdir()
        sentinel = occupied / "notes.txt"
        sentinel.write_text("keep this user file", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected files"):
            build.stage(occupied, public_files)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep this user file")
        self.assertEqual(list(occupied.iterdir()), [sentinel])
        self.assertEqual(original, {path: (self.root / path).read_bytes() for path in public_files})


if __name__ == "__main__":
    unittest.main()
