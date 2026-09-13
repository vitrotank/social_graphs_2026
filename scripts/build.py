#!/usr/bin/env python3
"""Render the field report and optionally stage an allowlisted GitHub Pages site.

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

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hero_svg(network: dict, summary: dict) -> str:
    """An astronomical drawing of actual edges, using the Python force layout."""
    nodes = {n["id"]: n for n in network["nodes"]}
    point = lambda n: (22 + n["x"] * 632, 35 + n["y"] * 555)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 650" role="img" aria-labelledby="title desc">',
             '<title id="title">EARTH–303: the Marvel Wikipedia constellation</title>',
             f'<desc id="desc">{summary["nodes"]} pages and {summary["edges"]} directed links, drawn without arrows. The largest weak component contains {summary["largest_component"]} pages. Small components are positioned in a separate observation lane. Circle size shows in-degree.</desc>',
             '<rect width="680" height="650" fill="#142a2b"/>',
             '<defs><radialGradient id="halo"><stop stop-color="#31544d" stop-opacity=".5"/><stop offset="1" stop-color="#142a2b" stop-opacity="0"/></radialGradient></defs>',
             '<circle cx="282" cy="315" r="268" fill="url(#halo)"/>',
             '<g fill="none" stroke="#90b19f" stroke-opacity=".13" stroke-width=".7">']
    for radius in (110, 176, 242):
        parts.append(f'<circle cx="280" cy="315" r="{radius}"/>')
    parts.append('<path d="M16 315H536M280 57V574" stroke-dasharray="2 7"/>')
    for angle in range(0, 360, 5):
        a = math.radians(angle)
        r = 249 if angle % 30 else 255
        parts.append(f'<path d="M{280 + 242 * math.cos(a):.2f},{315 + 242 * math.sin(a):.2f} L{280 + r * math.cos(a):.2f},{315 + r * math.sin(a):.2f}"/>')
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
        color = "#ef7954" if node["id"] in top else "#c7d6aa" if node["component"] == 0 else "#c6b696"
        if node["id"] in top:
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius+5:.2f}" fill="{color}" opacity=".10"/>')
        parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" opacity=".92"><title>{escape(node["label"])}: {node["in_degree"]} incoming / {node["out_degree"]} outgoing</title></circle>')
    parts.append('<g font-family="Consolas, monospace" font-size="9" fill="#b0c4b5">')
    parts.append('<text x="30" y="38" letter-spacing="1.3">THE MAINLAND</text><text x="548" y="38" letter-spacing="1">THE FRINGE</text>')
    # Labels are offsets for readability, not changes to measured coordinates.
    offsets = {"Spider-Man": (27, -34), "Hulk": (-45, -30), "Wolverine_(character)": (30, 37), "Doctor_Strange": (-42, 9), "Deadpool": (40, 10)}
    for record in summary["top_in"][:5]:
        n = nodes[record["id"]]; x, y = point(n)
        dx, dy = offsets.get(n["id"], (12, -12)); anchor = "end" if dx < 0 else "start"
        parts.append(f'<path d="M{x:.2f},{y:.2f} L{x+dx*.8:.2f},{y+dy-3:.2f} H{x+dx:.2f}" fill="none" stroke="#dfa27b" stroke-width=".6" opacity=".65"/>')
        parts.append(f'<text x="{x+dx:.2f}" y="{y+dy:.2f}" text-anchor="{anchor}" fill="#f4c6a0" stroke="#142a2b" stroke-width="3" paint-order="stroke">{escape(n["label"])}</text>')
    parts.append(f'<text x="34" y="610" fill="#df9b75">{summary["largest_component"]} ON THE MAINLAND</text><text x="34" y="629" fill="#8ca899">One weak component. Many possible routes.</text>')
    parts.append(f'<text x="647" y="610" text-anchor="end" fill="#df9b75">{summary["isolate_count"]} IN SILENCE</text><text x="647" y="629" text-anchor="end" fill="#8ca899">+ a nine-page island</text>')
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
    template = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    result = re.sub(r"@@([A-Z_]+)@@", lambda match: values[match[1]], template)
    (ROOT / "index.html").write_text(result, encoding="utf-8", newline="\n")
    payload = json.dumps({"network": network, "summary": summary}, ensure_ascii=True, separators=(",", ":"))
    (ROOT / "assets/data/network.js").write_text("window.EARTH303_DATA = " + payload + ";\n", encoding="utf-8", newline="\n")
    (ROOT / "assets/figures/hero-network.svg").write_text(hero_svg(network, summary), encoding="utf-8", newline="\n")
    favicon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#142a2b"/><g fill="none" stroke="#e9e6ce" stroke-width="2"><circle cx="32" cy="32" r="19"/><ellipse cx="32" cy="32" rx="28" ry="9" transform="rotate(-35 32 32)"/></g><circle cx="32" cy="32" r="5" fill="#ef7954"/></svg>\n'
    (ROOT / "assets/favicon.svg").write_text(favicon, encoding="utf-8", newline="\n")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    return [Path(name) for name in (
        "index.html", "style.css", "app.js", ".nojekyll", "assets/favicon.svg",
        "assets/data/network.js", "assets/data/network.json", "assets/data/summary.json",
        "assets/figures/hero-network.svg", "assets/figures/degree-linear.svg", "assets/figures/degree-loglog.svg",
        "data/raw/week1_nodes.tsv", "data/raw/week1_edges.tsv", "data/raw/README.md"
    )]


def stage(output: Path, files: list[Path]) -> None:
    output = output.resolve()
    if not output.is_relative_to(ROOT) or output == ROOT:
        raise ValueError("The staging directory must be a child of this repository.")
    if output.parts[len(ROOT.parts)] in {".git", ".agents", ".codex", "scripts", "tests", "templates", "assets", "data"}:
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
    print(f"Built EARTH-303 from the frozen network ({len(files)} public files).")


if __name__ == "__main__":
    main()
