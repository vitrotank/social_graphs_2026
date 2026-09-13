#!/usr/bin/env python3
"""Build the Crosstalk's data and SVG figures using Python's stdlib.

Input: the course's frozen week-1 roster and directed edge list. The complete
roster is loaded first, including characters that never appear in an edge.
No data is downloaded or invented. Run ``python scripts/analyze.py --help``.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
from html import escape
import json
import math
from pathlib import Path
import random
import re
import statistics
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://sunelehmann.com/socialgraphs2026-web/data/"
SNAPSHOT_DATE = "2026-08-26"


def content_rows(path: Path) -> Iterable[list[str]]:
    """Read UTF-8 TSV, ignoring the course's # comments and empty lines."""
    if not path.is_file():
        raise ValueError(f"Missing input: {path}. Supply the official node roster and edge list; no demo data is substituted.")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.reader((line for line in handle if line.strip() and not line.lstrip().startswith("#")), delimiter="\t")


def load_graph(nodes_path: Path, edges_path: Path) -> tuple[dict, list[tuple[str, str]]]:
    """Validate identifiers, duplicate rows and edge endpoints before analysis."""
    rows = iter(content_rows(nodes_path))
    header = next(rows, None)
    if not header or "node_id" not in header or "name" not in header:
        raise ValueError("Node roster must have a TSV header containing node_id and name.")
    nodes = {}
    for number, row in enumerate(rows, 2):
        if len(row) != len(header):
            raise ValueError(f"Node record {number} has {len(row)} fields; expected {len(header)}.")
        data = dict(zip(header, row))
        node_id = data["node_id"].strip()
        if not node_id or not data["name"].strip():
            raise ValueError(f"Node record {number} has an empty identifier or name.")
        if node_id in nodes:
            raise ValueError(f"Duplicate node identifier: {node_id}")
        nodes[node_id] = data
    if not nodes:
        raise ValueError("The node roster is empty.")
    edges = []
    seen = set()
    for number, row in enumerate(content_rows(edges_path), 1):
        if number == 1 and row == ["source", "target"]:
            continue
        if len(row) != 2:
            raise ValueError(f"Edge record {number} must have exactly two tab-separated fields.")
        source, target = (part.strip() for part in row)
        unknown = {source, target} - nodes.keys()
        if unknown:
            raise ValueError(f"Edge record {number} references nodes missing from the roster: {', '.join(sorted(unknown))}")
        if (source, target) in seen:
            raise ValueError(f"Duplicate directed edge: {source} -> {target}")
        seen.add((source, target))
        edges.append((source, target))
    return nodes, sorted(edges)


def adjacency(node_ids: Iterable[str], edges: list[tuple[str, str]]) -> tuple[dict, dict, dict]:
    outgoing = {node: set() for node in node_ids}
    incoming = {node: set() for node in outgoing}
    neighbors = {node: set() for node in outgoing}
    for source, target in edges:
        outgoing[source].add(target)
        incoming[target].add(source)
        if source != target:
            neighbors[source].add(target)
            neighbors[target].add(source)
    return outgoing, incoming, neighbors


def weak_components(neighbors: dict, removed: set | None = None) -> list[list[str]]:
    unseen = set(neighbors) - (removed or set())
    components = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        members, stack = [], [start]
        while stack:
            node = stack.pop()
            members.append(node)
            new = neighbors[node] & unseen
            unseen.difference_update(new)
            stack.extend(sorted(new, reverse=True))
        components.append(sorted(members))
    return sorted(components, key=lambda group: (-len(group), group[0]))


def strong_components(outgoing: dict, incoming: dict) -> list[list[str]]:
    """Iterative Kosaraju algorithm; no recursion or optional dependencies."""
    seen, finishing = set(), []
    for start in sorted(outgoing):
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(sorted(outgoing[start])))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                finishing.append(node)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(sorted(outgoing[child]))))
    seen, components = set(), []
    for start in reversed(finishing):
        if start in seen:
            continue
        seen.add(start)
        members, stack = [], [start]
        while stack:
            node = stack.pop()
            members.append(node)
            children = incoming[node] - seen
            seen.update(children)
            stack.extend(sorted(children, reverse=True))
        components.append(sorted(members))
    return sorted(components, key=lambda group: (-len(group), group[0]))


def force_layout(members: list[str], neighbors: dict, iterations: int = 180) -> dict:
    """Deterministic Fruchterman-Reingold-style layout of one component."""
    count = len(members)
    if count == 1:
        return {members[0]: (0.5, 0.5)}
    lookup = {name: i for i, name in enumerate(members)}
    links = [(i, lookup[target]) for i, source in enumerate(members)
             for target in sorted(neighbors[source]) if target in lookup and i < lookup[target]]
    rng = random.Random(2026)
    points = [[rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5)] for _ in members]
    ideal = math.sqrt(1 / count)
    for iteration in range(iterations):
        displacement = [[0.0, 0.0] for _ in members]
        for i in range(count):
            xi, yi = points[i]
            for j in range(i):
                dx, dy = xi - points[j][0], yi - points[j][1]
                distance2 = max(dx * dx + dy * dy, 0.000001)
                factor = ideal * ideal / distance2
                fx, fy = dx * factor, dy * factor
                displacement[i][0] += fx
                displacement[i][1] += fy
                displacement[j][0] -= fx
                displacement[j][1] -= fy
        for i, j in links:
            dx, dy = points[i][0] - points[j][0], points[i][1] - points[j][1]
            factor = math.hypot(dx, dy) / ideal
            fx, fy = dx * factor, dy * factor
            displacement[i][0] -= fx
            displacement[i][1] -= fy
            displacement[j][0] += fx
            displacement[j][1] += fy
        temperature = 0.07 * (1 - iteration / iterations) + 0.001
        for i in range(count):
            dx = displacement[i][0] - points[i][0] * 0.1
            dy = displacement[i][1] - points[i][1] * 0.1
            length = max(math.hypot(dx, dy), 0.000001)
            scale = min(length, temperature) / length
            points[i][0] += dx * scale
            points[i][1] += dy * scale
    xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
    extent = max(xmax - xmin, ymax - ymin, 0.000001)
    return {name: ((point[0] - (xmin + xmax) / 2) / extent + 0.5,
                   (point[1] - (ymin + ymax) / 2) / extent + 0.5)
            for name, point in zip(members, points)}


def layout_components(components: list[list[str]], neighbors: dict, iterations: int) -> dict:
    positions = {}
    for component_id, members in enumerate(components):
        layout = force_layout(members, neighbors, iterations)
        if component_id == 0:
            width = 0.72 if len(components) > 1 else 0.88
            for name, (x, y) in layout.items():
                positions[name] = (round(0.04 + width * x, 6), round(0.06 + 0.88 * y, 6))
        else:
            # Detached components have their own right-hand observation lane.
            rows = math.ceil((len(components) - 1) / 2)
            row, col = divmod(component_id - 1, 2)
            cell_height = 0.84 / rows
            for name, (x, y) in layout.items():
                positions[name] = (round(0.83 + col * 0.1 + (x - 0.5) * 0.07, 6),
                                   round(0.08 + (row + 0.5) * cell_height + (y - 0.5) * cell_height * 0.6, 6))
    return positions


def distribution(degrees: Iterable[int]) -> list[dict]:
    counts = Counter(degrees)
    size = sum(counts.values())
    return [{"degree": degree, "count": count, "probability": count / size}
            for degree, count in sorted(counts.items())]


def hub_removal(neighbors: dict, ranking: list[str], trials: int = 100) -> dict:
    """Fixed original in-degree ranking versus seeded, uniform node deletion."""
    size = len(neighbors)
    steps = sorted({value for value in (0, 1, 3, 5, 10, 20, 40, 80) if value < size})
    rng = random.Random(2026)
    ids = sorted(neighbors)
    permutations = [rng.sample(ids, size) for _ in range(trials)]
    results = []
    for removed_count in steps:
        remaining = size - removed_count
        targeted_components = weak_components(neighbors, set(ranking[:removed_count]))
        giant = len(targeted_components[0]) if targeted_components else 0
        random_giants = []
        for permutation in permutations:
            groups = weak_components(neighbors, set(permutation[:removed_count]))
            random_giants.append(len(groups[0]) if groups else 0)
        ordered = sorted(random_giants)
        results.append({"removed": removed_count, "remaining_nodes": remaining,
                        "targeted_largest_component": giant,
                        "targeted_fraction_original": giant / size,
                        "targeted_fraction_remaining": giant / remaining,
                        "random_mean_largest_component": statistics.mean(random_giants),
                        "random_p05_largest_component": ordered[math.floor((trials - 1) * 0.05)],
                        "random_p95_largest_component": ordered[math.ceil((trials - 1) * 0.95)]})
    return {"method": "Remove nodes by initial in-degree, descending; ties by node_id. Ranking is not recomputed. Connectivity ignores arrow direction.",
            "random_trials": trials, "seed": 2026, "ranking": ranking, "steps": results}


def analyze(nodes: dict, edges: list[tuple[str, str]], iterations: int = 180) -> tuple[dict, dict]:
    outgoing, incoming, neighbors = adjacency(nodes, edges)
    components = weak_components(neighbors)
    strong = strong_components(outgoing, incoming)
    positions = layout_components(components, neighbors, iterations)
    memberships = {name: i for i, members in enumerate(components) for name in members}
    isolates = [node for node in sorted(nodes) if not outgoing[node] and not incoming[node]]
    in_rank = sorted(nodes, key=lambda node: (-len(incoming[node]), node))
    out_rank = sorted(nodes, key=lambda node: (-len(outgoing[node]), node))

    def label(node: str) -> str:
        return re.sub(r"\s+\([^()]*\)$", "", nodes[node]["name"])

    def leaders(ranking: list[str], direction: dict) -> list[dict]:
        return [{"id": node, "label": label(node), "value": len(direction[node]),
                 "in_degree": len(incoming[node]), "out_degree": len(outgoing[node])}
                for node in ranking[:10]]

    nonloop_edges = {(a, b) for a, b in edges if a != b}
    reciprocal_arcs = sum((b, a) in nonloop_edges for a, b in nonloop_edges)
    mean_degree = len(edges) / len(nodes)
    network = {
        "schema_version": 1,
        "meta": {"source_url": SOURCE_URL, "snapshot_date": SNAPSHOT_DATE,
                 "directed": True, "layout": "Deterministic force layout; disconnected components positioned separately. Distances are visual, not measurements."},
        "nodes": [{"id": node, "name": nodes[node]["name"], "label": label(node),
                   "url": nodes[node].get("url", ""), "wikidata_id": nodes[node].get("wikidata_id", ""),
                   "description": nodes[node].get("description", ""),
                   "in_degree": len(incoming[node]), "out_degree": len(outgoing[node]),
                   "degree": len(neighbors[node]), "total_degree": len(incoming[node]) + len(outgoing[node]),
                   "component": memberships[node], "x": positions[node][0], "y": positions[node][1]}
                  for node in sorted(nodes)],
        "edges": [{"source": source, "target": target} for source, target in edges],
    }
    summary = {
        "schema_version": 1, "snapshot_date": SNAPSHOT_DATE, "source_url": SOURCE_URL,
        "nodes": len(nodes), "edges": len(edges), "isolates": isolates, "isolate_count": len(isolates),
        "weak_component_count": len(components), "largest_component": len(components[0]),
        "weak_components": [{"id": i, "size": len(members), "nodes": members} for i, members in enumerate(components)],
        "strong_component_count": len(strong), "largest_strong_component": len(strong[0]),
        "strong_component_sizes": [len(group) for group in strong],
        "self_loops": len(edges) - len(nonloop_edges),
        "reciprocity": reciprocal_arcs / len(nonloop_edges) if nonloop_edges else None,
        "reciprocal_pairs": reciprocal_arcs // 2,
        "mean_in_degree": mean_degree, "mean_out_degree": mean_degree,
        "median_in_degree": statistics.median(len(value) for value in incoming.values()),
        "median_out_degree": statistics.median(len(value) for value in outgoing.values()),
        "zero_in_degree": sum(not value for value in incoming.values()),
        "zero_out_degree": sum(not value for value in outgoing.values()),
        "top_in": leaders(in_rank, incoming), "top_out": leaders(out_rank, outgoing),
        "degree_distributions": {"in": distribution(len(value) for value in incoming.values()),
                                 "out": distribution(len(value) for value in outgoing.values())},
        "hub_removal": hub_removal(neighbors, in_rank),
        "definitions": {"edge": "A directed edge A -> B means A's article links to B's article within the frozen roster.",
                        "in_degree": "Number of roster pages linking to this page.",
                        "out_degree": "Number of roster pages this page links to.",
                        "degree": "Number of distinct neighbors, ignoring arrow direction and excluding self-loops.",
                        "total_degree": "In-degree plus out-degree.",
                        "weak_component": "Pages connected by paths when arrow direction is ignored.",
                        "reciprocity": "Fraction of directed, non-self edges with a reverse edge.",
                        "distribution": "P(k) = number of nodes of degree k / complete roster size. Zero degrees remain in the data; omitted on logarithmic axes."},
    }
    return network, summary


def degree_svg(summary: dict, logarithmic: bool = False) -> str:
    """Standalone publication/download artifact; zero handling is explicit."""
    width, height = 960, 600
    left, right, top, bottom = 88, 916, 92, 490
    rows = summary["degree_distributions"]
    max_degree = max(row["degree"] for points in rows.values() for row in points)
    max_probability = max(row["probability"] for points in rows.values() for row in points)
    x_max = max(10, math.ceil(max_degree / 20) * 20)
    y_max = math.ceil(max_probability * 10) / 10 or 1
    y_min = 1 / summary["nodes"] / 1.3
    title = "Every hero has a degree" if not logarithmic else "The long tail, under a different lens"
    subtitle = "Degree distributions · full frozen roster · linear axes" if not logarithmic else "Degree distributions · positive degrees only · logarithmic axes"

    def px(degree: float) -> float:
        value = math.log10(degree) / math.log10(x_max) if logarithmic else degree / x_max
        return left + value * (right - left)

    def py(probability: float) -> float:
        value = ((math.log10(probability) - math.log10(y_min)) / (math.log10(y_max) - math.log10(y_min))) if logarithmic else probability / y_max
        return bottom - value * (bottom - top)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
             f'<title id="title">{escape(title)}</title><desc id="description">{escape(subtitle)}. In-degree in orange; out-degree in teal. Each point is the fraction of the complete node roster having that degree.</desc>',
             '<rect width="960" height="600" fill="#f6f1e7"/>',
             '<g font-family="Arial, sans-serif" fill="#232927">',
             f'<text x="40" y="38" font-size="24" font-weight="700">{escape(title)}</text>',
             f'<text x="40" y="65" font-size="13" fill="#586866">{escape(subtitle)}</text>']
    xticks = [1, 2, 5, 10, 20, 50, 100] if logarithmic else list(range(0, x_max + 1, 20))
    yticks = [value for value in (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1) if y_min <= value <= y_max] if logarithmic else [y_max * i / 5 for i in range(6)]
    for tick in xticks:
        if tick > x_max:
            continue
        x = px(tick)
        parts.append(f'<path d="M{x:.2f},{top} V{bottom}" stroke="#d5d9cf"/><text x="{x:.2f}" y="514" text-anchor="middle" font-size="12">{tick}</text>')
    for tick in yticks:
        y = py(tick)
        parts.append(f'<path d="M{left},{y:.2f} H{right}" stroke="#d5d9cf"/><text x="76" y="{y + 4:.2f}" text-anchor="end" font-size="12">{tick:.3g}</text>')
    for index, (direction, color) in enumerate((("in", "#dc512f"), ("out", "#2849c7"))):
        for row in rows[direction]:
            if logarithmic and row["degree"] == 0:
                continue
            parts.append(f'<circle cx="{px(row["degree"]):.2f}" cy="{py(row["probability"]):.2f}" r="4.3" fill="{color}" fill-opacity=".75"><title>{direction}-degree {row["degree"]}: {row["count"]} pages</title></circle>')
        legend_x = 674 + index * 122
        parts.append(f'<circle cx="{legend_x}" cy="37" r="5" fill="{color}"/><text x="{legend_x + 12}" y="42" font-size="13">{direction}-degree</text>')
    note = f'P(k) = count / {summary["nodes"]}. '
    note += f'Zero-degree pages excluded from this plot: in {summary["zero_in_degree"]}, out {summary["zero_out_degree"]}. No power-law fit.' if logarithmic else 'Zero-degree pages included. One point per observed degree; no binning.'
    parts.extend(['<text x="500" y="544" text-anchor="middle" font-size="14">Degree k</text>',
                  '<text x="23" y="300" transform="rotate(-90 23 300)" text-anchor="middle" font-size="14">Fraction of pages P(k)</text>',
                  f'<text x="40" y="578" font-size="12" fill="#586866">{escape(note)}</text>', '</g></svg>'])
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", type=Path, default=ROOT / "data/raw/week1_nodes.tsv")
    parser.add_argument("--edges", type=Path, default=ROOT / "data/raw/week1_edges.tsv")
    parser.add_argument("--output", type=Path, default=ROOT / "assets/data")
    parser.add_argument("--figures", type=Path, default=ROOT / "assets/figures")
    parser.add_argument("--layout-iterations", type=int, default=180)
    args = parser.parse_args()
    if args.layout_iterations < 1:
        parser.error("--layout-iterations must be positive")
    try:
        nodes, edges = load_graph(args.nodes, args.edges)
        network, summary = analyze(nodes, edges, args.layout_iterations)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    provenance = {"nodes": {"file": args.nodes.name, "sha256": hashlib.sha256(args.nodes.read_bytes()).hexdigest()},
                  "edges": {"file": args.edges.name, "sha256": hashlib.sha256(args.edges.read_bytes()).hexdigest()},
                  "source": SOURCE_URL, "snapshot_date": SNAPSHOT_DATE}
    network["meta"]["provenance"] = provenance
    summary["provenance"] = provenance
    args.output.mkdir(parents=True, exist_ok=True)
    args.figures.mkdir(parents=True, exist_ok=True)
    for name, data in (("network", network), ("summary", summary)):
        (args.output / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, log in (("degree-linear", False), ("degree-loglog", True)):
        (args.figures / f"{name}.svg").write_text(degree_svg(summary, logarithmic=log), encoding="utf-8")
    print(f"Built {len(nodes)} nodes, {len(edges)} directed edges, {summary['isolate_count']} isolates.")
    print(f"Weak components: {summary['weak_component_count']}; largest: {summary['largest_component']}.")
    print(f"Data: {args.output}\nFigures: {args.figures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
