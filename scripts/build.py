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
    routes = [
        ("home", "index.html", "Journal", None),
        ("explore", "explore/index.html", "Networks", None),
        ("games", "index.html#games", "Laboratory", None),
    ]
    items = []
    for key, url, label, week in routes:
        active = ' aria-current="page"' if key == current else ''
        if week:
            items.append(f'<a href="{prefix}{url}" class="nav-game-link"{active}><span class="nav-game-title">{label}</span><small class="nav-game-badge">{week}</small></a>')
        else:
            items.append(f'<a href="{prefix}{url}"{active}>{label}</a>')
    links = ''.join(items)
    mark = '<svg class="brand-mark" viewBox="0 0 40 40" aria-hidden="true"><path d="M20 3v34M3 20h34M8 8l24 24M8 32 32 8" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="20" cy="20" r="4" fill="currentColor"/></svg>'
    issues = ''.join(f'<a href="{prefix}{escape(w["path"], quote=True)}"' + (' aria-current="page"' if current == f'week{w["number"]}' else '') + f'><span>{w["number"]:02}</span> Week {w["number"]}</a>' for w in config["weeks"] if w["status"] == "published")
    return f'<header class="site-header"><div class="shell header-inner"><a class="brand" href="{prefix}index.html" aria-label="Crosstalk home">{mark}<span class="brand-copy"><strong>{escape(config["title"])}</strong><small>LINKS, LANGUAGE &amp; THE SPACE BETWEEN</small></span></a><nav class="nav-links" aria-label="Main navigation">{links}<a href="{escape(config["repository_url"], quote=True)}">Source ↗</a></nav></div><div class="issue-nav-wrap"><nav class="shell issue-nav" aria-label="Weekly issues">{issues}<a class="all-issues" href="{prefix}index.html#journal">All issues ↓</a></nav></div></header>'


def footer(config: dict, prefix: str) -> str:
    members = []
    for member in config["members"]:
        match = re.fullmatch(r"(.+?)\s*\((s\d+)\)", member)
        name = escape(match[1] if match else member)
        student_id = match[2] if match else ""
        profile_url = config.get("member_urls", {}).get(student_id)
        if profile_url:
            name = f'<a href="{escape(profile_url, quote=True)}">{name}</a>'
        members.append(f'<div class="member"><strong>{name}</strong><small>{escape(student_id)}</small></div>')
    return f'<footer id="team" class="site-footer"><div class="shell"><div class="footer-top"><div><h2>Crosstalk.</h2><p>A student journal of social graphs.<br>Made with Python, curiosity, and an LLM.</p></div><div class="footer-members">{"".join(members)}</div></div><div class="footer-bottom"><span>{escape(config["course"])} · {escape(config["semester"])}</span><a href="https://sunelehmann.com/socialgraphs2026-web/index.html">Course &amp; assignments ↗</a><a href="{prefix}index.html">Back to the journal ↑</a></div></div></footer>'


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


def week5_svg(data: dict, *, cover: bool = False) -> str:
    """Draw exact frozen counts; a logarithmic axis makes the survivors legible."""
    if cover:
        x = lambda n: 40 + (n - 8) / 52 * 360
        y = lambda n: 250 - math.log10(max(1, n)) / 5 * 190
        points = ' '.join(f'{x(r["length"]):.2f},{y(r["pairs"]):.2f}' for r in data['thresholds'])
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 315" role="img" aria-label="Matching article pairs: 40,570 at eight shared words, 71 at twenty, and 13 at forty. Vertical counts use a logarithmic scale.">',
                 '<text x="40" y="24" fill="#ead0cd" font-size="12" font-family="monospace">MATCHING PAIRS / LOG SCALE</text>',
                 '<path d="M40 60H420M40 250H420" stroke="#ead0cd" stroke-opacity=".25"/>',
                 f'<polyline points="{points}" fill="none" stroke="#f4f0e8" stroke-width="3"/>']
        for length in (8, 20, 40, 60):
            row = next(r for r in data['thresholds'] if r['length'] == length)
            xx, yy = x(length), y(row['pairs'])
            parts.append(f'<circle cx="{xx}" cy="{yy}" r="4" fill="#f4f0e8"/><text x="{xx}" y="277" text-anchor="middle" fill="#ead0cd" font-family="monospace" font-size="14">{length}</text>')
            if length != 60:
                parts.append(f'<text x="{xx+10}" y="{yy-17}" fill="#f4f0e8" font-family="Georgia" font-size="32">{row["pairs"]:,}</text>')
        parts.append('<text x="220" y="309" text-anchor="middle" fill="#ead0cd" font-family="monospace" font-size="12">MINIMUM SHARED WORDS</text></svg>')
        return ''.join(parts)
    x = lambda n: 82 + (n - 8) / 52 * 810
    y = lambda n: 335 - math.log10(max(1, n)) / 5 * 270
    color = '#f4f0e8' if cover else '#8d293d'
    muted = '#ead0cd' if cover else '#64645b'
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 420" role="img" aria-labelledby="w5-static-title w5-static-desc">',
             '<title id="w5-static-title">How longer shared phrases shrink the overlap</title>',
             '<desc id="w5-static-desc">Matching unordered article pairs: 40,570 at eight words, 71 at twenty, 13 at forty, 8 at sixty. Vertical counts use a logarithmic scale. All 303 frozen articles are included.</desc>']
    for count in (1, 10, 100, 1000, 10000, 100000):
        yy = y(count)
        parts.append(f'<path d="M82 {yy:.2f}H914" stroke="{muted}" opacity=".25" stroke-dasharray="2 6"/><text x="66" y="{yy+5:.2f}" text-anchor="end" fill="{muted}" font-size="14" font-family="monospace">{count:,}</text>')
    points = ' '.join(f'{x(r["length"]):.2f},{y(r["pairs"]):.2f}' for r in data['thresholds'])
    parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="4"/>')
    for length in (8, 20, 40, 60):
        row = next(r for r in data['thresholds'] if r['length'] == length)
        xx, yy = x(length), y(row['pairs'])
        parts.append(f'<circle cx="{xx}" cy="{yy}" r="5" fill="{color}"/><text x="{xx}" y="365" text-anchor="middle" fill="{muted}" font-family="monospace" font-size="16">{length}</text>')
        if length != 60:
            parts.append(f'<text x="{xx+15}" y="{yy-15}" fill="{color}" font-family="Georgia" font-size="31">{row["pairs"]:,}</text>')
    parts.append(f'<text x="82" y="28" fill="{muted}" font-family="monospace" font-size="13">ARTICLE PAIRS / LOG SCALE</text><text x="500" y="405" text-anchor="middle" fill="{muted}" font-family="monospace" font-size="13">MINIMUM CONSECUTIVE WORDS SHARED</text></svg>')
    return ''.join(parts)


def render() -> list[Path]:
    config = read_json(ROOT / "site.json")
    network = read_json(ROOT / "assets/data/network.json")
    summary = read_json(ROOT / "assets/data/summary.json")
    week4 = read_json(ROOT / "assets/data/week4.json")
    week3 = read_json(ROOT / "assets/data/week3.json")
    week5 = read_json(ROOT / "assets/data/week5.json")
    if (week5['corpus']['documents'], week5['corpus']['tokens'],
        week5['result']['pairs_at_8'], week5['result']['pairs_at_20'], week5['result']['pairs_at_40'],
        week5['result']['standard_phrase_documents'], week5['result']['longest_words']) != (303, 727203, 40570, 71, 13, 282, 166):
        raise ValueError('This Week 5 story expects the documented frozen corpus and tokenizer; review the narrative before changing them.')
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
    explorer = week4["explorer"]
    comparison = explorer["weighted_comparison"]
    week4_values = {
        "W4_NODES": f'{week4["nodes"]:,}', "W4_EDGES": f'{week4["undirected_edges"]:,}',
        "W4_GROUPS": week4["community_count"], "W4_Q": f'{week4["modularity"]:.3f}',
        "W4_NULL": f'{week4["null"]["mean"]:.3f}',
        "W4_NMI": f'{comparison["nmi"]:.3f}', "W4_WEIGHTED_GROUPS": comparison["community_count"],
        "W4_MOVERS": comparison["mover_count"],
        "W4_Q_MIN": f'{min(run["modularity"] for run in week4["runs"]):.3f}',
        "W4_Q_MAX": f'{max(run["modularity"] for run in week4["runs"]):.3f}',
        "W4_WEIGHT_FINDING": (
            f'Agreement is substantial but incomplete: NMI {comparison["nmi"]:.3f}, '
            f'with {comparison["mover_count"]:,} of {week4["nodes"]:,} philosophers outside their matched group. '
            'Aristotle moves from the group anchored by Aristotle and Plato to one anchored by Aristotle and Thomas Aquinas. '
            'His links span eight unweighted communities. One assigned group does not capture the reach of his page.'
        ),
        "W4_BREAK_FINDING": (
            'We define the breaking point as the largest component falling below half the original 1,374 people. '
            'At α ≈ 0.169585, tightening the filter takes it from 699 to 677. '
            'Five ties share that cutoff, but Confucius—Voltaire is the only one joining the 22-node detached group to the giant. '
            'That group includes Confucius, Laozi, Han Fei, and Zhu Xi: several East Asian traditions, not one school.'
        ),
    }
    values.update({key: escape(str(value), quote=True) for key, value in week4_values.items()})
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
    for week in published:
        number = week["number"]
        content = f'<span class="week-number">{number:02}</span><span class="week-label">Week {number}</span>'
        if week["status"] == "published":
            archive.append(f'<div class="directory-row"><a class="week-entry published" href="{escape(week["path"], quote=True)}" aria-label="Read Week {number}: {escape(week["title"], quote=True)}"><span class="week-number">{number:02}</span><span class="directory-copy"><span class="week-label">WEEK {number} / {escape(week.get("topic", "FIELD NOTES"))}</span><strong>{escape(week.get("short_title", week["title"]))}</strong><span>{escape(week["summary"])}</span></span><span class="week-state">Read Week {number} ↗</span></a><a class="directory-extra" href="{escape(week.get("experience_path", week["path"]), quote=True)}">{escape(week.get("experience_label", "Explore the issue"))} <span aria-hidden="true">↗</span></a></div>')
        else:
            archive.append(f'<div class="week-entry upcoming">{content}<span class="week-state">Coming soon</span></div>')
    values.update({
        "WEEK_ENTRIES": "\n".join(archive),
        "QUICK_ISSUES": ''.join(f'<a class="quick-issue" href="{escape(w["path"], quote=True)}"><span>{w["number"]:02}</span><div><small>WEEK {w["number"]} / {escape(w.get("topic", "FIELD NOTES"))}</small><strong>{escape(w.get("short_title", w["title"]))}</strong></div><b aria-hidden="true">↗</b></a>' for w in published[-3:]),
        "PUBLISHED_COUNT": str(len(published)), "UPCOMING_COUNT": str(len(weeks) - len(published)),
        "LATEST_NUMBER": str(latest["number"]), "LATEST_URL": escape(latest["path"], quote=True),
        "LATEST_TITLE": escape(latest["title"]), "LATEST_SUMMARY": escape(latest["summary"]),
        "LATEST_PLATE": '<svg viewBox="0 0 440 250" role="img" aria-label="The Marvel roster has 303 pages, 1784 directed links and 17 isolated pages"><text x="0" y="65" fill="currentColor" font-size="66" font-family="Georgia">303</text><text x="0" y="95" fill="currentColor" font-size="12">PAGES</text><text x="200" y="65" fill="currentColor" font-size="66" font-family="Georgia">1,784</text><text x="200" y="95" fill="currentColor" font-size="12">DIRECTED LINKS</text><path d="M0 130H440" stroke="currentColor" opacity=".4"/><text x="0" y="205" fill="currentColor" font-size="66" font-family="Georgia">17</text><text x="110" y="180" fill="currentColor" font-size="14">Pages with no links</text><text x="110" y="203" fill="currentColor" font-size="14">inside this roster.</text></svg>',
        "LATEST_PLATE_CAPTION": 'The course’s frozen Marvel network. Links measure Wikipedia references.',
    })
    if latest['number'] == 5:
        values.update(LATEST_PLATE=week5_svg(week5, cover=True),
                      LATEST_PLATE_CAPTION='Shared words, vanishing pairs. 40,570 matches at eight words; 13 at forty. Vertical scale is logarithmic.')
    pages = [(Path("home.html"), Path("index.html"), "home"),
             (Path("explore.html"), Path("explore/index.html"), "explore"),
             (Path("play.html"), Path("play/index.html"), "play"),
             (Path("cerebro.html"), Path("play/cerebro.html"), "cerebro"),
             (Path("switchboard.html"), Path("play/switchboard.html"), "games"),
             (Path("louvain.html"), Path("play/louvain.html"), "games"),
             (Path("grunge.html"), Path("grunge/index.html"), "grunge")]
    pages += [(Path(week["template"]), Path(week["path"]), f'week{week["number"]}') for week in published]
    if len({destination for _, destination, _ in pages}) != len(pages):
        raise ValueError("Every page needs a unique output path.")
    for source, destination, current in pages:
        prefix = "../" * (len(destination.parts) - 1)
        page_values = dict(values, ROOT=prefix, HEADER=header(config, prefix, current), FOOTER=footer(config, prefix))
        template = (ROOT / "templates" / source).read_text(encoding="utf-8")
        result = re.sub(r"@@([A-Z][A-Z0-9_]*)@@", lambda match: page_values[match[1]], template)
        result = result.replace('</head>', f'<link rel="stylesheet" href="{prefix}design.css"></head>')
        target = ROOT / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result, encoding="utf-8", newline="\n")
    payload = json.dumps({"network": network, "summary": summary}, ensure_ascii=True, separators=(",", ":"))
    (ROOT / "assets/data/network.js").write_text("window.CROSSTALK_DATA = " + payload + ";\n", encoding="utf-8", newline="\n")
    # Small cover exhibits are explicit samples; full analyses stay on issues.
    philosopher_graph = week4["explorer"]
    cover_names = {"Aristotle", "Plato", "Confucius", "Voltaire", "Immanuel_Kant", "Friedrich_Nietzsche", "Thomas_Aquinas"}
    for community in philosopher_graph["communities"]:
        members = sorted((node for node in philosopher_graph["nodes"] if node["community"] == community["id"]), key=lambda node: (-node["strength"], node["id"]))
        cover_names.update(node["id"] for node in members[:8])
    cover_names.update(node["id"] for node in sorted(philosopher_graph["nodes"], key=lambda node: (-node["strength"], node["id"]))[:75])
    philosopher_cover_nodes = [{key: node[key] for key in ("id", "label", "community", "degree", "strength")} | {"x": round(node["x"] / 1000, 5), "y": round(node["y"] / 760, 5)}
                              for node in philosopher_graph["nodes"] if node["id"] in cover_names]
    philosopher_cover_edges = sorted((edge for edge in philosopher_graph["edges"] if edge["source"] in cover_names and edge["target"] in cover_names and edge["alpha"] < .5), key=lambda edge: (edge["alpha"], edge["source"], edge["target"]))[:500]
    marvel_cover_names = {node["id"] for node in network["nodes"] if node["component"] != 0}
    marvel_cover_names.update(node["id"] for node in sorted(network["nodes"], key=lambda node: (-node["degree"], node["id"]))[:85])
    marvel_cover_nodes = [{"id": node["id"], "label": node["label"], "x": node["x"], "y": node["y"], "degree": node["degree"], "strength": node["in_degree"], "community": 2 if node["degree"] == 0 else node["component"]}
                         for node in network["nodes"] if node["id"] in marvel_cover_names]
    marvel_pairs = sorted({tuple(sorted((edge["source"], edge["target"]))) for edge in network["edges"] if edge["source"] != edge["target"] and edge["source"] in marvel_cover_names and edge["target"] in marvel_cover_names})
    cover = {
        "philosophers": {"title": "The philosopher atlas", "fullNodes": week4["nodes"], "fullEdges": week4["undirected_edges"], "edgeLabel": "unique ties",
                         "nodes": philosopher_cover_nodes, "edges": [{key: edge[key] for key in ("source", "target", "alpha")} for edge in philosopher_cover_edges],
                         "communityLabels": {str(row["id"]): row["label"] for row in philosopher_graph["communities"]},
                         "sampleNote": "Selected philosophers and up to 500 real ties from the α = 0.50 backbone. Full-network totals; fixed positions from the α = 0.20 layout.", "path": "week4/index.html#atlas"},
        "marvel": {"title": "The Marvel exchange", "fullNodes": summary["nodes"], "fullEdges": summary["edges"], "edgeLabel": "directed links",
                   "nodes": marvel_cover_nodes, "edges": [{"source": a, "target": b} for a, b in marvel_pairs],
                   "communityLabels": {"0": "The main exchange", "1": "The nine-page island", "2": "The isolated pages"},
                   "sampleNote": "Selected pages and real linked pairs. Drawn pairs merge directions; totals count the original directed links. Size follows incoming links.", "path": "week1/index.html#atlas"},
    }
    (ROOT / "assets/data/cover.js").write_text("window.CROSSTALK_COVER = " + json.dumps(cover, ensure_ascii=True, separators=(",", ":")) + ";\n", encoding="utf-8", newline="\n")
    removal_figure = {"nodes": week3["nodes"], "removal": {key: week3["removal"][key] for key in ("trials", "seed", "denominator", "degree", "betweenness", "random")},
                      "ranking": sorted(week3["single_removal"], key=lambda node: node["betweenness_rank"])[:8]}
    (ROOT / "assets/data/week3-figure.js").write_text("window.CROSSTALK_WEEK3_FIGURE = " + json.dumps(removal_figure, ensure_ascii=True, separators=(",", ":")) + ";\n", encoding="utf-8", newline="\n")
    puzzles = make_puzzles(network, **config.get("arcade", {}))
    (ROOT / "assets/data/puzzles.json").write_text(json.dumps(puzzles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    (ROOT / "assets/data/puzzles.js").write_text("window.CROSSTALK_PUZZLES = " + json.dumps(puzzles, ensure_ascii=True, separators=(",", ":")) + ";\n", encoding="utf-8", newline="\n")
    (ROOT / "assets/figures/hero-network.svg").write_text(hero_svg(network, summary), encoding="utf-8", newline="\n")
    (ROOT / "assets/figures/week5-sieve.svg").write_text(week5_svg(week5), encoding="utf-8", newline="\n")
    favicon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="#f4f0e8"/><path d="M32 9v46M9 32h46M16 16l32 32M16 48l32-32" fill="none" stroke="#8d293d" stroke-width="3"/><circle cx="32" cy="32" r="5" fill="#8d293d"/></svg>\n'
    (ROOT / "assets/favicon.svg").write_text(favicon, encoding="utf-8", newline="\n")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    return [destination for _, destination, _ in pages] + [Path(name) for name in (
        "week1.css", "week2-figures.css", "week2-figures.js", "week3-story.css", "week3-story.js",
        "home.css", "design.css", "explore.css", "journal.css", "journal.js", "assets/data/cover.js", "assets/data/week3-figure.js",
        "week3.css", "week3.js", "week4.css", "week4.js", "week5.css", "week5.js", "louvain.js", "grunge.css", "grunge.js",
        "assets/data/week5.json", "assets/data/week5.js", "assets/figures/week5-sieve.svg", "data/raw/marvel_pages.zip", "data/week5/README.md",
        "assets/data/week3.json", "assets/data/week3.js", "assets/data/week4.json", "assets/data/week4.js", "assets/figures/week3-removal.svg",
        "assets/data/grunge.json", "assets/data/grunge.js", "data/grunge/snapshot.json", "data/grunge/README.md",
        "style.css", "app.js", "home.js", "game.js", "game.css", "week2.js", ".nojekyll", "assets/favicon.svg",
        "assets/data/network.js", "assets/data/network.json", "assets/data/summary.json",
        "assets/data/puzzles.js", "assets/data/puzzles.json",
        "assets/figures/hero-network.svg", "assets/figures/degree-linear.svg", "assets/figures/degree-loglog.svg",
        "assets/figures/hero-models.svg", "assets/figures/ccdf-models.svg", "assets/figures/ccdf-fit.svg",
        "assets/figures/clustering-nulls.svg", "assets/figures/growth-models.svg",
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
