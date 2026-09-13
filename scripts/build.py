#!/usr/bin/env python3
"""Render Crosstalk's homepage, weekly journal, and original network puzzle.

Only the Python standard library is required. No network access is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from html import escape
import json
import math
from pathlib import Path
import re
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from puzzles import make_puzzles

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def header(config: dict, prefix: str, current: str) -> str:
    routes = [("home", "index.html", "Home"), ("journal", "index.html#journal", "Weekly journal"),
              ("play", "play/index.html", "Crossed Wires")]
    links = ''.join(f'<a href="{prefix}{url}"' + (' aria-current="page"' if key == current else '') + f'>{label}</a>' for key, url, label in routes)
    mark = '<svg class="brand-mark" viewBox="0 0 48 40" aria-hidden="true"><path d="M5 12h7c14 0 3 20 16 20h15" fill="none" stroke="currentColor" stroke-width="3"/><path d="M5 30h7c14 0 3-20 16-20h15" fill="none" stroke="#dc512f" stroke-width="3"/><circle cx="5" cy="12" r="4" fill="currentColor"/><circle cx="43" cy="32" r="4" fill="currentColor"/><circle cx="5" cy="30" r="4" fill="#dc512f"/><circle cx="43" cy="10" r="4" fill="#dc512f"/></svg>'
    return f'<header class="site-header"><div class="shell header-inner"><a class="brand" href="{prefix}index.html" aria-label="Crosstalk home">{mark}<span class="brand-copy"><strong>{escape(config["title"])}</strong><small>A NETWORK SCIENCE NOTEBOOK</small></span></a><nav class="nav-links" aria-label="Main navigation">{links}<a href="{escape(config["repository_url"], quote=True)}">Source ↗</a></nav></div></header>'


def footer(config: dict, prefix: str) -> str:
    members = []
    for member in config["members"]:
        match = re.fullmatch(r"(.+?)\s*\((s\d+)\)", member)
        members.append(f'<div class="member"><strong>{escape(match[1] if match else member)}</strong><small>{escape(match[2] if match else "")}</small></div>')
    return f'<footer id="team" class="site-footer"><div class="shell"><div class="footer-top"><div><p class="eyebrow">THE PEOPLE AT THE OTHER END</p><h2>Made by curious people.</h2><p>A student journal by Christos &amp; Dávid.</p></div><div class="footer-members">{"".join(members)}</div></div><div class="footer-bottom"><span>{escape(config["course"])} · {escape(config["semester"])}</span><span>Python, experiments &amp; a little help from an LLM.</span><a href="{prefix}index.html">Back to the switchboard ↗</a></div></div></footer>'


def page_path(value: str, parent: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or not (parent / path).resolve().is_relative_to(parent.resolve()) or path.suffix != ".html":
        raise ValueError(f"Page paths must be relative HTML files: {value}")
    return path


def hero_svg(network: dict, summary: dict) -> str:
    """A patch-panel drawing of actual edges, using the Python force layout."""
    nodes = {n["id"]: n for n in network["nodes"]}
    point = lambda n: (22 + n["x"] * 632, 35 + n["y"] * 555)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 650" role="img" aria-labelledby="title desc">',
             '<title id="title">Crosstalk: the Marvel Wikipedia switchboard</title>',
             f'<desc id="desc">{summary["nodes"]} pages and {summary["edges"]} directed links, drawn without arrows. The largest weak component contains {summary["largest_component"]} pages. Small components are positioned in a separate observation lane. Circle size shows in-degree.</desc>',
             '<rect width="680" height="650" fill="#172a48"/>',
             '<g fill="none" stroke="#b0bdd9" stroke-opacity=".15" stroke-width=".7">',
             '<rect x="20" y="65" width="496" height="502" rx="12"/><rect x="542" y="65" width="116" height="502" rx="12"/>']
    for x in range(44, 510, 40):
        parts.append(f'<path d="M{x} 67V565" stroke-opacity=".25"/>')
    for y in range(87, 564, 40):
        parts.append(f'<path d="M22 {y}H514" stroke-opacity=".25"/>')
    parts.append('<path d="M532 64V564" stroke-dasharray="3 7"/></g>')
    parts.append('<g stroke="#a3bdab" stroke-opacity=".14" stroke-width=".7">')
    for edge in network["edges"]:
        x1, y1 = point(nodes[edge["source"]]); x2, y2 = point(nodes[edge["target"]])
        parts.append(f'<path d="M{x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f}"/>')
    parts.append('</g>')
    top = {n["id"] for n in summary["top_in"][:5]}
    for node in sorted(nodes.values(), key=lambda n: n["in_degree"]):
        x, y = point(node)
        radius = 1.7 + math.sqrt(node["in_degree"]) * .7
        color = "#ff956d" if node["id"] in top else "#adc5f5" if node["component"] == 0 else "#ecdba9"
        if node["id"] in top:
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius+5:.2f}" fill="{color}" opacity=".10"/>')
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" opacity=".92"><title>{escape(node["label"])}: {node["in_degree"]} incoming / {node["out_degree"]} outgoing</title></circle>')
    parts.append('<g font-family="Consolas, monospace" font-size="9" fill="#b0c4b5">')
    parts.append('<text x="30" y="38" letter-spacing="1.3">THE MAIN EXCHANGE</text><text x="548" y="38" letter-spacing="1">QUIET LINES</text>')
    # Labels are offsets for readability, not changes to measured coordinates.
    offsets = {"Spider-Man": (27, -34), "Hulk": (-45, -30), "Wolverine_(character)": (30, 37), "Doctor_Strange": (-42, 9), "Deadpool": (40, 10)}
    for record in summary["top_in"][:5]:
        n = nodes[record["id"]]; x, y = point(n)
        dx, dy = offsets.get(n["id"], (12, -12)); anchor = "end" if dx < 0 else "start"
        parts.append(f'<path d="M{x:.2f},{y:.2f} L{x+dx*.8:.2f},{y+dy-3:.2f} H{x+dx:.2f}" fill="none" stroke="#dfa27b" stroke-width=".6" opacity=".65"/>')
        parts.append(f'<text x="{x+dx:.2f}" y="{y+dy:.2f}" text-anchor="{anchor}" fill="#f4c6a0" stroke="#172a48" stroke-width="3" paint-order="stroke">{escape(n["label"])}</text>')
    parts.append(f'<text x="34" y="610" fill="#f3aa83">{summary["largest_component"]} CONNECTED PAGES</text><text x="34" y="629" fill="#a9bddb">One weak component. Many possible routes.</text>')
    parts.append(f'<text x="647" y="610" text-anchor="end" fill="#f3aa83">{summary["isolate_count"]} SILENT LINES</text><text x="647" y="629" text-anchor="end" fill="#a9bddb">+ a nine-page island</text>')
    parts.append('</g></svg>')
    return "\n".join(parts) + "\n"


def render() -> list[Path]:
    config = read_json(ROOT / "site.json")
    network = read_json(ROOT / "assets/data/network.json")
    summary = read_json(ROOT / "assets/data/summary.json")
    nodes = {n["id"]: n for n in network["nodes"]}
    # The prose is specifically a Week 1 report. A changed release needs an edit,
    # rather than silently mixing a new graph with old scientific statements.
    if (summary["nodes"], summary["edges"], summary["isolate_count"],
            [c["size"] for c in summary["weak_components"]]) != (303, 1784, 17, [277, 9] + [1] * 17):
        raise ValueError("This Week 1 report expects the official 303-page release; review the prose before using another dataset.")
    spider = nodes["Spider-Man"]
    leader = summary["top_out"][0]
    island = summary["weak_components"][1]
    label_counts = Counter(n["label"] for n in nodes.values())

    def display_name(n: dict) -> str:
        return n["name"] if label_counts[n["label"]] > 1 else n["label"]

    def inspect_button(node_id: str, css: str = "isolate-token") -> str:
        return f'<button type="button" class="{css} inspect-character" data-character="{escape(node_id, quote=True)}">{escape(nodes[node_id]["label"])} <span aria-hidden="true">↗</span></button>'

    ranking = '<ol class="rank-list">' + ''.join(
        f'<li><button class="rank-button inspect-character" data-character="{escape(n["id"], quote=True)}"><span class="rank-number">{i:02}</span><span class="rank-name">{escape(n["label"])}</span><strong>{n["value"]}</strong><i class="rank-bar" style="width:{n["value"]/spider["in_degree"]*100:.2f}%"></i></button></li>'
        for i, n in enumerate(summary["top_in"][:5], 1)) + '</ol>'
    plain = {
        "TITLE": config["title"], "GROUP_NAME": config["group_name"],
        "COURSE": config["course"], "SEMESTER": config["semester"],
        "MEMBERS": " · ".join(config["members"]) or "A student expedition in network science.",
        "REPO": config["repository_url"], "NODES": f'{summary["nodes"]:,}',
        "EDGES": f'{summary["edges"]:,}', "ISOLATE_COUNT": summary["isolate_count"],
        "GIANT": summary["largest_component"], "GIANT_SHARE": f'{summary["largest_component"]/summary["nodes"]*100:.1f}',
        "SPIDER_IN": spider["in_degree"], "SPIDER_OUT": spider["out_degree"],
        "SPIDER_SHARE": f'{spider["in_degree"]/(summary["nodes"]-1)*100:.1f}',
        "OUT_LEADER": leader["label"], "OUT_MAX": leader["value"], "OUT_ID": leader["id"],
        "OUTSIDE_GIANT": summary["nodes"]-summary["largest_component"],
        "GIANT_WITHOUT_SPIDER": next(s["targeted_largest_component"] for s in summary["hub_removal"]["steps"] if s["removed"] == 1),
        "DETACHED_WITHOUT_SPIDER": summary["largest_component"] - 1 - next(s["targeted_largest_component"] for s in summary["hub_removal"]["steps"] if s["removed"] == 1),
        "SMALL_COMPONENT_DESCRIPTION": "one separate nine-page island",
        "ISLAND_NOTE": 'Three of the island’s page IDs carry the qualifier “Morituri”: Radian, Scatterbrain, and Snapdragon. A clue to shared context—but the frozen edge list does not explain why this island formed.'
    }
    values = {key: escape(str(value), quote=True) for key, value in plain.items()}
    values.update({
        "RANKING": ranking,
        "ISOLATE_BUTTONS": "\n".join(inspect_button(i) for i in summary["isolates"]),
        "ISLAND_MEMBERS": '<div class="isolate-list">' + "\n".join(inspect_button(i) for i in island["nodes"]) + '</div>',
        "CHARACTER_OPTIONS": "\n".join(f'<option value="{escape(display_name(n), quote=True)}">{escape(n["name"])}</option>' for n in sorted(nodes.values(), key=display_name))
    })
    weeks = config["weeks"]
    if len({week["number"] for week in weeks}) != len(weeks):
        raise ValueError("Each week needs a unique number in site.json.")
    published = sorted((week for week in weeks if week["status"] == "published"), key=lambda w: w["number"])
    if not published:
        raise ValueError("Add at least one published week before building the journal.")
    latest = published[-1]
    for week in published:
        page_path(week["path"], ROOT)
        page_path(week["template"], ROOT / "templates")
    archive = []
    for week in sorted(weeks, key=lambda w: w["number"]):
        number = week["number"]
        content = f'<span class="week-number">{number:02}</span><span class="week-label">Week {number}</span>'
        if week["status"] == "published":
            archive.append(f'<a class="week-entry published" href="{escape(week["path"], quote=True)}" aria-label="Week {number}: {escape(week["title"], quote=True)}">{content}<span class="week-state">Read the story ↗</span></a>')
        else:
            archive.append(f'<div class="week-entry upcoming">{content}<span class="week-state">Coming soon</span></div>')
    values.update({
        "WEEK_ENTRIES": "\n".join(archive),
        "PUBLISHED_COUNT": str(len(published)), "UPCOMING_COUNT": str(len(weeks) - len(published)),
        "LATEST_NUMBER": str(latest["number"]), "LATEST_URL": escape(latest["path"], quote=True),
        "LATEST_TITLE": escape(latest["title"]), "LATEST_SUMMARY": escape(latest["summary"]),
    })
    pages = [(Path("home.html"), Path("index.html"), "home"),
             (Path("play.html"), Path("play/index.html"), "play")]
    pages += [(Path(week["template"]), Path(week["path"]), "journal") for week in published]
    if len({destination for _, destination, _ in pages}) != len(pages):
        raise ValueError("Every page needs a unique output path.")
    for source, destination, current in pages:
        prefix = "../" * (len(destination.parts) - 1)
        page_values = dict(values, ROOT=prefix, HEADER=header(config, prefix, current), FOOTER=footer(config, prefix))
        template = (ROOT / "templates" / source).read_text(encoding="utf-8")
        result = re.sub(r"@@([A-Z_]+)@@", lambda match: page_values[match[1]], template)
        target = ROOT / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result, encoding="utf-8", newline="\n")
    payload = json.dumps({"network": network, "summary": summary}, ensure_ascii=True, separators=(",", ":"))
    (ROOT / "assets/data/network.js").write_text("window.CROSSTALK_DATA = " + payload + ";\n", encoding="utf-8", newline="\n")
    puzzles = make_puzzles(network)
    (ROOT / "assets/data/puzzles.json").write_text(json.dumps(puzzles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (ROOT / "assets/data/puzzles.js").write_text("window.CROSSTALK_PUZZLES = " + json.dumps(puzzles, ensure_ascii=True, separators=(",", ":")) + ";\n", encoding="utf-8", newline="\n")
    (ROOT / "assets/figures/hero-network.svg").write_text(hero_svg(network, summary), encoding="utf-8", newline="\n")
    favicon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="#f6f1e7"/><path d="M10 17h10c17 0 7 30 24 30h10" fill="none" stroke="#2849c7" stroke-width="5"/><path d="M10 47h10c17 0 7-30 24-30h10" fill="none" stroke="#dc512f" stroke-width="5"/><g fill="#2849c7"><circle cx="10" cy="17" r="5"/><circle cx="54" cy="47" r="5"/></g><g fill="#dc512f"><circle cx="10" cy="47" r="5"/><circle cx="54" cy="17" r="5"/></g></svg>\n'
    (ROOT / "assets/favicon.svg").write_text(favicon, encoding="utf-8", newline="\n")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    return [destination for _, destination, _ in pages] + [Path(name) for name in (
        "style.css", "app.js", "home.js", "game.js", "game.css", ".nojekyll", "assets/favicon.svg",
        "assets/data/network.js", "assets/data/network.json", "assets/data/summary.json",
        "assets/data/puzzles.js", "assets/data/puzzles.json",
        "assets/figures/hero-network.svg", "assets/figures/degree-linear.svg", "assets/figures/degree-loglog.svg",
        "data/raw/week1_nodes.tsv", "data/raw/week1_edges.tsv", "data/raw/README.md"
    )]


def stage(output: Path, files: list[Path]) -> None:
    output = output.resolve()
    if not output.is_relative_to(ROOT) or output == ROOT:
        raise ValueError("The staging directory must be a child of this repository.")
    page_folders = {p.parts[0] for p in files if len(p.parts) > 1 and p.suffix == ".html"}
    if output.parts[len(ROOT.parts)] in {".git", ".agents", ".codex", ".preview", "scripts", "tests", "templates", "assets", "data"} | page_folders:
        raise ValueError("Use a dedicated staging directory such as _site, not a source directory.")
    if output.exists():
        unexpected = {p.relative_to(output) for p in output.rglob("*") if p.is_file()} - set(files)
        if unexpected:
            raise ValueError(f"Staging directory contains unexpected files; use an empty directory: {sorted(map(str, unexpected))}")
    for relative in files:
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Also stage the public files in a dedicated directory, e.g. _site")
    args = parser.parse_args()
    files = render()
    if args.output:
        stage(ROOT / args.output, files)
    print(f"Built Crosstalk from the frozen network ({len(files)} public files).")


if __name__ == "__main__":
    main()
