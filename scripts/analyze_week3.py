#!/usr/bin/env python3
"""Exact Week 3 path and removal experiments on the frozen Marvel roster.

Standard library only. No crawl, approximation, or invented network is used.
Run: python scripts/analyze_week3.py
"""
from __future__ import annotations

from collections import deque
import hashlib
from html import escape
import json
import math
from pathlib import Path
import random
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import adjacency, load_graph, weak_components, SNAPSHOT_DATE, SOURCE_URL

ROOT = Path(__file__).resolve().parents[1]


def betweenness(neighbors: dict[str, set[str]]) -> dict[str, float]:
    """Exact normalized node betweenness, undirected, endpoints excluded.

    Brandes accumulation counts both directions. Dividing by (n-1)(n-2)
    consequently yields the usual normalized undirected score. Unreachable
    pairs contribute zero; the denominator uses the complete roster.
    """
    result = dict.fromkeys(neighbors, 0.0)
    for source in sorted(neighbors):
        stack = []
        predecessors = {node: [] for node in neighbors}
        paths = dict.fromkeys(neighbors, 0)
        paths[source] = 1
        distance = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            stack.append(node)
            for other in sorted(neighbors[node]):
                if other not in distance:
                    distance[other] = distance[node] + 1
                    queue.append(other)
                if distance[other] == distance[node] + 1:
                    paths[other] += paths[node]
                    predecessors[other].append(node)
        dependency = dict.fromkeys(neighbors, 0.0)
        while stack:
            node = stack.pop()
            for previous in predecessors[node]:
                dependency[previous] += paths[previous] / paths[node] * (1 + dependency[node])
            if node != source:
                result[node] += dependency[node]
    denominator = (len(neighbors) - 1) * (len(neighbors) - 2)
    return {node: value / denominator if len(neighbors) > 2 else 0.0
            for node, value in result.items()}


def shortest_path(neighbors: dict[str, set[str]], source: str, target: str) -> list[str] | None:
    """BFS; sorted IDs make ties deterministic. None means no route exists."""
    if source not in neighbors or target not in neighbors:
        raise ValueError("Both endpoints must belong to the roster.")
    previous = {source: None}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        if node == target:
            route = []
            while node is not None:
                route.append(node)
                node = previous[node]
            return route[::-1]
        for other in sorted(neighbors[node]):
            if other not in previous:
                previous[other] = node
                queue.append(other)
    return None


def removal_curve(neighbors: dict[str, set[str]], order: list[str]) -> list[int]:
    """Largest component after k removals, k=0..n, using reverse union-find."""
    if len(order) != len(neighbors) or set(order) != set(neighbors):
        raise ValueError("A removal order must be a permutation of the full roster.")
    parent, size = {}, {}
    largest = 0
    curve = [0] * (len(order) + 1)

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for index in range(len(order) - 1, -1, -1):
        node = order[index]
        parent[node], size[node] = node, 1
        largest = max(largest, 1)
        for other in sorted(neighbors[node]):
            if other not in parent:
                continue
            a, b = find(node), find(other)
            if a != b:
                if size[a] < size[b]:
                    a, b = b, a
                parent[b] = a
                size[a] += size[b]
                largest = max(largest, size[a])
        curve[index] = largest
    return curve


def analyze_week3(nodes: dict, edges: list[tuple[str, str]], trials: int = 200, seed: int = 2026) -> dict:
    if trials < 1:
        raise ValueError("At least one random trial is required.")
    outgoing, _, neighbors = adjacency(nodes, edges)
    components = weak_components(neighbors)
    giant = set(components[0]) if components else set()
    scores = betweenness(neighbors)
    degree_order = sorted(nodes, key=lambda node: (-len(neighbors[node]), node))
    between_order = sorted(nodes, key=lambda node: (-scores[node], node))
    degree_rank = {node: i for i, node in enumerate(degree_order, 1)}
    between_rank = {node: i for i, node in enumerate(between_order, 1)}
    deletion = []
    for node in sorted(nodes):
        groups = weak_components(neighbors, {node})
        largest = len(groups[0]) if groups else 0
        # Count separation from the original giant, excluding the deleted node.
        main_groups = [sorted(set(group) & giant) for group in groups]
        main_groups = [group for group in main_groups if group]
        main_groups.sort(key=lambda group: (-len(group), group))
        detached = [member for group in main_groups[1:] for member in group]
        deletion.append({"id": node, "name": nodes[node]["name"],
                         "degree": len(neighbors[node]), "degree_rank": degree_rank[node],
                         "betweenness": scores[node], "betweenness_rank": between_rank[node],
                         "largest_component": largest, "component_count": len(groups),
                         "extra_components": len(groups) - len(components),
                         "detached_from_original_giant": len(detached), "detached_ids": detached})
    deletion.sort(key=lambda row: (row["largest_component"], -row["detached_from_original_giant"], row["id"]))
    rng = random.Random(seed)
    permutations = [rng.sample(sorted(nodes), len(nodes)) for _ in range(trials)]
    random_curves = [removal_curve(neighbors, order) for order in permutations]
    random_stats = []
    for removed in range(len(nodes) + 1):
        values = sorted(curve[removed] for curve in random_curves)
        random_stats.append({"removed": removed, "mean": statistics.mean(values),
                             "p05": values[math.floor((trials - 1) * .05)],
                             "p95": values[math.ceil((trials - 1) * .95)]})
    routes = {}
    if "Spider-Man" in nodes:
        for mode, graph in (("undirected", neighbors), ("directed", outgoing)):
            found = {node: shortest_path(graph, node, "Spider-Man") for node in sorted(nodes)}
            reachable = {node: route for node, route in found.items() if route is not None}
            longest = max(len(route) - 1 for route in reachable.values())
            routes[mode] = {"reachable": len(reachable), "unreachable": len(nodes) - len(reachable),
                            "maximum_distance": longest,
                            "farthest": [{"id": node, "path": route} for node, route in reachable.items() if len(route) - 1 == longest],
                            "paths": found}
    return {"schema_version": 1, "snapshot_date": SNAPSHOT_DATE, "source_url": SOURCE_URL,
            "nodes": len(nodes), "directed_edges": len(edges),
            "undirected_edges": sum(len(value) for value in neighbors.values()) // 2,
            "component_sizes": [len(group) for group in components],
            "single_removal": deletion, "betweenness_leader": between_order[0] if between_order else None,
            "degree_leader": degree_order[0] if degree_order else None,
            "removal": {"seed": seed, "trials": trials, "denominator": len(nodes),
                        "degree_order": degree_order, "betweenness_order": between_order,
                        "degree": removal_curve(neighbors, degree_order),
                        "betweenness": removal_curve(neighbors, between_order),
                        "random": random_stats}, "routes": routes,
            "definitions": {
                "connectivity": "Undirected simple projection: reciprocal arcs collapse; loops excluded; all roster nodes retained.",
                "betweenness": "Exact shortest-path betweenness; endpoints excluded; normalized by all pairs of other roster nodes. Unreachable pairs contribute zero.",
                "ranking": "Original undirected degree or original betweenness descending, ties by node ID. Ranks are static, never recomputed after removal.",
                "random": f"Uniform random permutations of the full roster, one continuous trajectory per trial; {trials} trials with Python random seed {seed}. Shaded band is pointwise empirical 5th–95th percentiles, not a confidence interval.",
                "denominator": "Largest remaining component divided by original complete roster size, including original isolates, at every step.",
                "routes": "A shortest route from the selected page to Spider-Man. Directed mode follows article hyperlinks; undirected mode permits either orientation. Sorted node IDs break ties. No route is not an infinite displayed distance."}}


def removal_svg(data: dict) -> str:
    """A deterministic, standalone SVG of the complete removal trajectories."""
    n = data["nodes"]
    left, right, top, bottom = 92, 924, 116, 474
    x = lambda value: left + value / n * (right - left)
    y = lambda value: bottom - value / n * (bottom - top)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 620" role="img" aria-labelledby="title desc">',
             '<title id="title">Pull the plug: the Marvel network under node removal</title>',
             '<desc id="desc">Largest remaining weak component as a percentage of the original 303 pages. Static betweenness and degree removal compared with 200 uniform random deletion orders; band shows pointwise fifth to ninety-fifth percentiles.</desc>',
             '<rect width="1000" height="620" fill="#f6f1e7"/>',
             '<g font-family="Arial, sans-serif" fill="#172a48">',
             '<text x="40" y="43" font-size="26" font-weight="700">What happens when the switchboard goes down?</text>',
             '<text x="40" y="75" font-size="17">Static rankings · full roster · every removal, from 0 to 303</text>']
    for percent in (0, 25, 50, 75, 100):
        py = y(n * percent / 100)
        parts.append(f'<path d="M{left},{py:.2f}H{right}" stroke="#d6d2c7"/><text x="78" y="{py+6:.2f}" text-anchor="end" font-size="16">{percent}%</text>')
    for tick in (0, 50, 100, 150, 200, 250, n):
        px = x(tick)
        parts.append(f'<text x="{px:.2f}" y="501" text-anchor="middle" font-size="16">{tick}</text>')
    random_rows = data["removal"]["random"]
    band = [(x(row["removed"]), y(row["p95"])) for row in random_rows]
    band += [(x(row["removed"]), y(row["p05"])) for row in reversed(random_rows)]
    parts.append('<polygon points="' + ' '.join(f'{px:.2f},{py:.2f}' for px, py in band) + '" fill="#799080" opacity=".24"/>')
    for key, color, dash in (("random", "#426950", "6 5"), ("degree", "#244b93", ""), ("betweenness", "#c74929", "")):
        values = [row["mean"] for row in random_rows] if key == "random" else data["removal"][key]
        path = ' '.join(f'{"M" if index == 0 else "L"}{x(index):.2f},{y(value):.2f}' for index, value in enumerate(values))
        parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3.5" stroke-dasharray="{dash}"/>')
    parts.append('<text x="508" y="539" text-anchor="middle" font-size="18">Characters removed</text>')
    for offset, text_, color in ((80, "Betweenness first", "#c74929"), (380, "Degree first", "#244b93"), (650, "Random mean + 5–95% band", "#426950")):
        parts.append(f'<path d="M{offset},567h25" stroke="{color}" stroke-width="4"/><text x="{offset+35}" y="573" font-size="16">{escape(text_)}</text>')
    parts.append('<text x="40" y="607" font-size="14">Y = largest component / original 303 pages. Arrow direction ignored. Seed 2026. Ranks never recomputed.</text></g></svg>')
    return '\n'.join(parts) + '\n'


def main() -> None:
    nodes_file, edges_file = ROOT / "data/raw/week1_nodes.tsv", ROOT / "data/raw/week1_edges.tsv"
    data = analyze_week3(*load_graph(nodes_file, edges_file))
    data["provenance"] = {"nodes_sha256": hashlib.sha256(nodes_file.read_bytes()).hexdigest(),
                          "edges_sha256": hashlib.sha256(edges_file.read_bytes()).hexdigest(),
                          "script": "scripts/analyze_week3.py"}
    for path, value in ((ROOT / "assets/data/week3.json", json.dumps(data, ensure_ascii=False, indent=2) + '\n'),
                        (ROOT / "assets/data/week3.js", 'window.CROSSTALK_WEEK3 = ' + json.dumps(data, ensure_ascii=True, separators=(',', ':')) + ';\n'),
                        (ROOT / "assets/figures/week3-removal.svg", removal_svg(data))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8", newline="\n")
    print(f"Built Week 3: {data['nodes']} pages, exact centrality and paths, {data['removal']['trials']} random deletion trials.")
    first = data["single_removal"][0]
    print(f"Greatest single-removal loss: {first['name']}; largest component {data['component_sizes'][0]} -> {first['largest_component']}.")
    for mode, rows in data["routes"].items():
        print(f"{mode.capitalize()} routes: maximum {rows['maximum_distance']} hops, {len(rows['farthest'])} tied farthest pages, {rows['unreachable']} unreachable.")


if __name__ == "__main__":
    main()
