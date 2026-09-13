"""Check the published artifact against its sources in an isolated build tree."""

from collections import Counter
import csv
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("site_build", REPO / "scripts/build.py")
build = importlib.util.module_from_spec(SPEC)
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
        temporary = tempfile.TemporaryDirectory(prefix="earth303-site-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        # Copy only build inputs. Neither render nor stage touches the real repo.
        for relative in (
            "site.json", "templates/index.html", "style.css", "app.js",
            "assets/data/network.json", "assets/data/summary.json",
            "assets/figures/degree-linear.svg", "assets/figures/degree-loglog.svg",
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
        html = (self.root / "index.html").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"@@[A-Z_]+@@", html), "Unresolved template value in the report")
        self.assertNotIn("polyfill.io", html)
        document = Document(html)
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
        for reference in document.links:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                continue
            destination = (self.root / unquote(parsed.path)).resolve() if parsed.path else self.root / "index.html"
            self.assertTrue(destination.is_relative_to(self.root), f"Local link escapes the published site: {reference}")
            self.assertTrue(destination.is_file(), f"Local link has no file: {reference}")
            if parsed.fragment:
                target = document if destination == self.root / "index.html" else Document(destination.read_text(encoding="utf-8"))
                self.assertIn(unquote(parsed.fragment), target.ids, f"Local fragment is missing: {reference}")

    def test_browser_payload_preserves_raw_nodes_edges_and_measured_degrees(self):
        build.render()
        javascript = (self.root / "assets/data/network.js").read_text(encoding="utf-8")
        prefix = "window.EARTH303_DATA = "
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

    def test_staging_publishes_only_the_allowlist_and_preserves_its_bytes(self):
        # A workspace may contain control files that must never reach Pages.
        for relative in (".git/HEAD", ".codex/private.txt", ".agents/private.txt", "scripts/private.py", "tests/private.py", "unrelated.txt"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private fixture", encoding="utf-8")
        public_files = build.render()
        forbidden = {".git", ".codex", ".agents", "scripts", "tests", "templates"}
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
        for destination in (self.root, self.root.parent, self.root / "../outside-site", self.root / "assets", self.root / "data/nested", self.root / "scripts", self.root / ".git", self.root / ".codex", self.root / ".agents", self.root / "templates", self.root / "tests"):
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
