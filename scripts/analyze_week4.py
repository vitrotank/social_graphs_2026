#!/usr/bin/env python3
"""Reproducible Week 4 communities on the course's philosopher graph.

The primary result follows the course setup: the largest connected component
of an undirected, unweighted projection. The explorer compares this with the
sum of directed article-link counts and applies a disparity filter to those
weights. All computation uses the Python standard library.
"""
from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://sunelehmann.com/socialgraphs2026-web/data/"
SNAPSHOT_DATE = "2026-09-15"


def load(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader((x for x in f if x.strip() and not x.startswith("#")), delimiter="\t")]
    header, body = rows[0], rows[1:]
    return header, [dict(zip(header, r)) for r in body]


def weighted_graph(nodes, edges):
    """Return the legacy weighted projection (useful for compatibility/tests)."""
    g = {n["node_id"]: {} for n in nodes}
    for e in edges:
        a, b, w = e["source"], e["target"], float(e.get("weight", 1))
        if a == b:
            continue
        g[a][b] = g[a].get(b, 0) + w
        g[b][a] = g[b].get(a, 0) + w
    return g


def unweighted_graph(nodes, edges):
    g = {n["node_id"]: set() for n in nodes}
    for e in edges:
        a, b = e["source"], e["target"]
        if a != b:
            g[a].add(b)
            g[b].add(a)
    return g


def giant_component(g):
    seen, components = set(), []
    for start in g:
        if start in seen:
            continue
        stack, component = [start], set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            component.add(node)
            stack.extend(g[node] - seen)
        components.append(component)
    keep = max(components, key=lambda c: (len(c), min(c)))
    return {n: {x for x in g[n] if x in keep} for n in sorted(keep)}, keep


def modularity(g, communities, resolution=1.0):
    weight = lambda v: sum(v.values()) if isinstance(v, dict) else len(v)
    degree = {n: weight(v) + (v.get(n, 0) if isinstance(v, dict) else 0) for n, v in g.items()}
    m = sum(degree.values()) / 2
    if not m:
        return 0.0
    internal = defaultdict(float)
    for a, nbrs in g.items():
        for b, value in (nbrs.items() if isinstance(nbrs, dict) else ((b, 1) for b in nbrs)):
            if communities[a] == communities[b]:
                internal[communities[a]] += value * (2 if a == b else 1)
    return sum(internal[c] / (2 * m) - resolution * (sum(degree[n] for n in communities if communities[n] == c) / (2 * m)) ** 2 for c in set(communities.values()))


def _local_move(g, seed, resolution=1.0):
    rng = random.Random(seed)
    labels = {n: i for i, n in enumerate(sorted(g))}
    weight = lambda v: sum(v.values()) if isinstance(v, dict) else len(v)
    neighbors = lambda v: v.items() if isinstance(v, dict) else ((n, 1) for n in sorted(v))
    degree = {n: weight(v) + (v.get(n, 0) if isinstance(v, dict) else 0) for n, v in g.items()}
    total = sum(degree.values()) / 2
    for _ in range(50):
        order = list(g)
        rng.shuffle(order)
        moved = False
        community_degree = defaultdict(float)
        for n, c in labels.items():
            community_degree[c] += degree[n]
        for node in order:
            old = labels[node]
            community_degree[old] -= degree[node]
            weights = defaultdict(float)
            for neighbor, edge_weight in neighbors(g[node]):
                if neighbor != node:
                    weights[labels[neighbor]] += edge_weight
            # Self-loops stay internal whichever group receives the node. They
            # affect its degree, but cancel from comparisons between groups.
            best = old
            best_gain = weights[old] / total - resolution * degree[node] * community_degree[old] / (2 * total * total)
            for community in sorted(weights):
                gain = weights[community] / total - resolution * degree[node] * community_degree[community] / (2 * total * total)
                if gain > best_gain + 1e-12 or (abs(gain - best_gain) <= 1e-12 and community < best):
                    best, best_gain = community, gain
            labels[node] = best
            community_degree[best] += degree[node]
            if best != old:
                moved = True
        if not moved:
            break
    return labels


def _aggregate(g, labels):
    groups = defaultdict(list)
    for node, community in labels.items():
        groups[community].append(node)
    mapping = {c: i for i, c in enumerate(sorted(groups, key=lambda c: (min(groups[c]), c)))}
    new = {mapping[c]: {} for c in groups}
    for a, nbrs in g.items():
        for b, edge_weight in (sorted(nbrs.items()) if isinstance(nbrs, dict) else ((b, 1) for b in sorted(nbrs))):
            ca, cb = mapping[labels[a]], mapping[labels[b]]
            # A diagonal stores an undirected loop once. Off-diagonal entries
            # store one weight in each direction; degree counts loops twice.
            amount = edge_weight / 2 if ca == cb and a != b else edge_weight
            new[ca][cb] = new[ca].get(cb, 0) + amount
    return new, mapping


def louvain(g, seed=2026, resolution=1.0):
    """Run complete local-move/aggregation Louvain and unpack original nodes."""
    current = {n: (dict(v) if isinstance(v, dict) else set(v)) for n, v in g.items()}
    original_to_current = {n: n for n in current}
    level_seed, levels = seed, 0
    while levels < 50:
        labels = _local_move(current, level_seed, resolution)
        levels += 1
        groups = set(labels.values())
        if len(groups) == len(current):
            break
        current, mapping = _aggregate(current, labels)
        original_to_current = {n: mapping[labels[c]] for n, c in original_to_current.items()}
        level_seed += 1
    # A final local move can be needed when aggregation produced new ties.
    communities = {n: original_to_current[n] for n in g}
    normalized = {c: i for i, c in enumerate(sorted(set(communities.values()), key=lambda c: (min(n for n in communities if communities[n] == c), c)))}
    communities = {n: normalized[c] for n, c in communities.items()}
    return communities, modularity(g, communities, resolution)


def degree_preserving_null(g, seed, swaps=None):
    """Double-edge swaps preserve every degree in the same unweighted graph."""
    rng = random.Random(seed)
    out = {n: set(v) for n, v in g.items()}
    edges = [(a, b) for a in sorted(out) for b in sorted(out[a]) if a < b]
    swaps = swaps or min(8 * len(edges), 100_000)
    for _ in range(swaps):
        i, j = rng.sample(range(len(edges)), 2)
        a, b = edges[i]
        c, d = edges[j]
        if len({a, b, c, d}) < 4 or d in out[a] or b in out[c]:
            continue
        out[a].remove(b); out[b].remove(a); out[c].remove(d); out[d].remove(c)
        out[a].add(d); out[d].add(a); out[c].add(b); out[b].add(c)
        edges[i], edges[j] = (min(a, d), max(a, d)), (min(c, b), max(c, b))
    # The course comparison is also on a giant component.  Reject the rare
    # disconnected rewiring so every null has the same node set and definition.
    seen, stack = set(), [next(iter(out))]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(out[node] - seen)
    if len(seen) != len(out):
        return degree_preserving_null(g, seed + 1_000_003, swaps)
    return out


def _community_sizes(partition):
    counts = defaultdict(int)
    for c in partition.values():
        counts[c] += 1
    return sorted(counts.values(), reverse=True)


def _pair_agreement(a, b, seed=2026, samples=50_000):
    rng = random.Random(seed)
    nodes = list(a)
    if len(nodes) < 2:
        return 1.0
    same = 0
    for _ in range(samples):
        x, y = rng.sample(nodes, 2)
        same += (a[x] == a[y]) == (b[x] == b[y])
    return same / samples


def normalized_mutual_information(a, b):
    """Exact label-invariant NMI, using the arithmetic mean of entropies."""
    if set(a) != set(b):
        raise ValueError("NMI partitions must contain the same nodes")
    if not a:
        return 1.0
    ca, cb, joint = defaultdict(int), defaultdict(int), defaultdict(int)
    for node in a:
        ca[a[node]] += 1
        cb[b[node]] += 1
        joint[a[node], b[node]] += 1
    n = len(a)
    entropy = lambda counts: -sum((count / n) * math.log(count / n) for count in counts.values())
    ha, hb = entropy(ca), entropy(cb)
    if ha + hb == 0:
        return 1.0
    information = sum(count / n * math.log(count * n / (ca[x] * cb[y])) for (x, y), count in joint.items())
    return min(1.0, max(0.0, 2 * information / (ha + hb)))


def align_partitions(reference, other):
    """Maximize retained node labels with a one-to-one Hungarian matching."""
    left, right = sorted(set(reference.values())), sorted(set(other.values()))
    li, ri = {c: i for i, c in enumerate(left)}, {c: i for i, c in enumerate(right)}
    size = max(len(left), len(right))
    overlaps = [[0] * size for _ in range(size)]
    for node in reference:
        overlaps[ri[other[node]]][li[reference[node]]] += 1
    # The Hungarian algorithm minimizes cost; negate overlap counts.
    u, v, p, way = [0] * (size + 1), [0] * (size + 1), [0] * (size + 1), [0] * (size + 1)
    for row in range(1, size + 1):
        p[0], col = row, 0
        minimum, used = [float("inf")] * (size + 1), [False] * (size + 1)
        while True:
            used[col] = True
            current_row, delta, next_col = p[col], float("inf"), 0
            for candidate in range(1, size + 1):
                if not used[candidate]:
                    reduced = -overlaps[current_row - 1][candidate - 1] - u[current_row] - v[candidate]
                    if reduced < minimum[candidate]:
                        minimum[candidate], way[candidate] = reduced, col
                    if minimum[candidate] < delta:
                        delta, next_col = minimum[candidate], candidate
            for candidate in range(size + 1):
                if used[candidate]:
                    u[p[candidate]] += delta
                    v[candidate] -= delta
                else:
                    minimum[candidate] -= delta
            col = next_col
            if p[col] == 0:
                break
        while col:
            previous = way[col]
            p[col], col = p[previous], previous
    assignment = {p[col] - 1: col - 1 for col in range(1, size + 1)}
    mapping, records, next_id = {}, [], max(left, default=-1) + 1
    for original in right:
        row, col = ri[original], assignment[ri[original]]
        matched = left[col] if col < len(left) else None
        aligned = matched if matched is not None else next_id
        if matched is None:
            next_id += 1
        mapping[original] = aligned
        records.append({"weighted": original, "aligned": aligned, "unweighted": matched,
                        "overlap": overlaps[row][col], "size": sum(c == original for c in other.values())})
    return {node: mapping[c] for node, c in other.items()}, records


def disparity_edges(g):
    """OR disparity rule: an edge's threshold is its minimum endpoint tail.

    A degree-one endpoint has no allocation to compare against other edges;
    the formula's exponent is zero, so its tail is 1. Its neighbor's test can
    still retain the edge. This convention reproduces the course benchmarks.
    """
    strength = {node: sum(neighbors.values()) for node, neighbors in g.items()}
    degree = {node: len(neighbors) for node, neighbors in g.items()}
    endpoint = lambda node, weight: (1 - weight / strength[node]) ** (degree[node] - 1) if degree[node] > 1 else 1.0
    return [{"source": a, "target": b, "weight": weight,
             "alpha": min(endpoint(a, weight), endpoint(b, weight))}
            for a in sorted(g) for b, weight in sorted(g[a].items()) if a < b]


class _Components:
    def __init__(self, nodes):
        self.parent = {node: node for node in nodes}
        self.sizes = {node: 1 for node in nodes}
        self.count = len(self.parent)
        self.giant = min(1, self.count)

    def find(self, node):
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while node != root:
            node, self.parent[node] = self.parent[node], root
        return root

    def add(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b:
            return
        if self.sizes[a] < self.sizes[b]:
            a, b = b, a
        self.parent[b] = a
        self.sizes[a] += self.sizes.pop(b)
        self.count -= 1
        self.giant = max(self.giant, self.sizes[a])


def backbone_metrics(nodes, edges, alpha):
    retained = [edge for edge in edges if alpha >= 1 or edge["alpha"] < alpha]
    component, active = _Components(nodes), set()
    for edge in retained:
        a, b = edge["source"], edge["target"]
        component.add(a, b)
        active.update((a, b))
    total_weight = sum(edge["weight"] for edge in edges)
    return {"alpha": alpha, "nodes": len(active), "edges": len(retained),
            "giant_nodes": component.giant if retained else 0, "components": component.count,
            "node_fraction": len(active) / len(nodes), "edge_fraction": len(retained) / len(edges),
            "weight_fraction": sum(edge["weight"] for edge in retained) / total_weight,
            "giant_fraction": (component.giant if retained else 0) / len(nodes)}


def backbone_breakpoints(nodes, edges, names):
    """Exact edge-event thresholds when tightening the filter from the full graph.

    At an event alpha=a, every edge with tail a is removed simultaneously. The
    stricter state contains tails <a and the looser state contains tails <=a.
    A threshold therefore names a tied edge set, not necessarily one culprit.
    """
    component, groups = _Components(nodes), defaultdict(list)
    for edge in edges:
        groups[edge["alpha"]].append(edge)
    events = {}
    for alpha in sorted(groups):
        before = component.giant
        edges_at_event = groups[alpha]
        roots_before = {node: component.find(node) for edge in edges_at_event for node in (edge["source"], edge["target"])}
        sizes_before = dict(component.sizes)
        for edge in edges_at_event:
            component.add(edge["source"], edge["target"])
        after = component.giant
        if before < len(nodes) / 2 <= after or before < len(nodes) == after:
            bridges = [edge for edge in edges_at_event if roots_before[edge["source"]] != roots_before[edge["target"]]]
            bridges.sort(key=lambda edge: (-min(sizes_before[roots_before[edge["source"]]], sizes_before[roots_before[edge["target"]]]), edge["source"], edge["target"]))
            event = {"alpha": alpha, "giant_before_tightening": after, "giant_after_tightening": before,
                           "removed_edge_count": len(edges_at_event), "joining_edge_count": len(bridges),
                           "critical_edges": [{**edge, "source_label": names[edge["source"]], "target_label": names[edge["target"]],
                                               "source_component_nodes": sizes_before[roots_before[edge["source"]]],
                                               "target_component_nodes": sizes_before[roots_before[edge["target"]]]}
                                              for edge in bridges[:20]],
                           "definition": "first fragmentation" if after == len(nodes) else "giant falls below half of the original nodes"}
            if before < len(nodes) / 2 <= after:
                events["half_giant"] = {**event, "definition": "giant falls below half of the original nodes"}
            if before < len(nodes) == after:
                events["first_fragmentation"] = {**event, "definition": "first fragmentation"}
    return {"first_fragmentation": events.get("first_fragmentation"),
            "half_giant": events.get("half_giant"),
            "tie_rule": "At the reported alpha all edges with that exact minimum tail are removed together; retaining requires tail < alpha."}


def _summaries(partition, names, graph):
    groups = defaultdict(list)
    for node, community in partition.items():
        groups[community].append(node)
    summaries = []
    for community, members in sorted(groups.items()):
        leaders = sorted(members, key=lambda node: (-len(graph[node]), names[node]))[:5]
        summaries.append({"id": community, "label": " · ".join(names[node] for node in leaders[:2]),
                          "size": len(members), "leaders": [{"id": node, "label": names[node], "degree": len(graph[node])} for node in leaders]})
    return summaries


def explorer_layout(graph, partition, edges, seed=2026):
    """Stable community clusters, with springs taken only from alpha=.2 edges."""
    rng = random.Random(seed)
    communities = sorted(set(partition.values()))
    sizes = {c: sum(group == c for group in partition.values()) for c in communities}
    radii = {c: max(28, math.sqrt(sizes[c]) * 7) for c in communities}
    centers = {c: [500 + 265 * math.sqrt((i + .5) / len(communities)) * math.cos(i * 2.399963),
                   380 + 230 * math.sqrt((i + .5) / len(communities)) * math.sin(i * 2.399963)]
               for i, c in enumerate(communities)}
    # Pack differently sized clusters without overlapping; links tug nearby
    # clusters together. The full graph is used only for community labels.
    cross = defaultdict(int)
    retained = [edge for edge in edges if edge["alpha"] < .2]
    for edge in retained:
        a, b = partition[edge["source"]], partition[edge["target"]]
        if a != b:
            cross[min(a, b), max(a, b)] += 1
    for _ in range(220):
        force = {c: [0.0, 0.0] for c in communities}
        for i, a in enumerate(communities):
            for b in communities[i + 1:]:
                dx, dy = centers[a][0] - centers[b][0], centers[a][1] - centers[b][1]
                distance = max(.1, math.hypot(dx, dy))
                separation = radii[a] + radii[b] + 30
                push = max(0, separation - distance) * .13 + 100 / distance
                pull = math.log1p(cross.get((min(a, b), max(a, b)), 0)) * .06 * max(0, distance - separation)
                amount = push - pull
                for axis, delta in enumerate((dx, dy)):
                    force[a][axis] += delta / distance * amount
                    force[b][axis] -= delta / distance * amount
        for c in communities:
            centers[c][0] = min(985 - radii[c], max(15 + radii[c], centers[c][0] + force[c][0]))
            centers[c][1] = min(745 - radii[c], max(15 + radii[c], centers[c][1] + force[c][1]))
    points = {}
    for c in communities:
        members = sorted((node for node in graph if partition[node] == c), key=lambda node: (-len(graph[node]), node))
        for i, node in enumerate(members):
            radius, angle = radii[c] * .84 * math.sqrt(i / max(1, len(members) - 1)), i * 2.399963 + rng.random() * .1
            points[node] = [centers[c][0] + radius * math.cos(angle), centers[c][1] + radius * math.sin(angle)]
    anchors = {node: point[:] for node, point in points.items()}
    for _ in range(75):
        force = {node: [(anchors[node][axis] - points[node][axis]) * .065 for axis in (0, 1)] for node in points}
        bins = defaultdict(list)
        for node, (x, y) in points.items():
            bins[int(x // 20), int(y // 20)].append(node)
        for node, (x, y) in points.items():
            gx, gy = int(x // 20), int(y // 20)
            for bx in range(gx - 1, gx + 2):
                for by in range(gy - 1, gy + 2):
                    for other in bins.get((bx, by), ()):
                        if other <= node:
                            continue
                        dx, dy = x - points[other][0], y - points[other][1]
                        distance = max(.1, math.hypot(dx, dy))
                        if distance < 15:
                            push = (15 - distance) * .16
                            force[node][0] += dx / distance * push
                            force[node][1] += dy / distance * push
                            force[other][0] -= dx / distance * push
                            force[other][1] -= dy / distance * push
        for edge in retained:
            a, b = edge["source"], edge["target"]
            if partition[a] != partition[b]:
                continue
            dx, dy = points[b][0] - points[a][0], points[b][1] - points[a][1]
            distance = max(.1, math.hypot(dx, dy))
            pull = (distance - 20) * .012
            for axis, delta in enumerate((dx, dy)):
                force[a][axis] += delta / distance * pull
                force[b][axis] -= delta / distance * pull
        for node in points:
            for axis in (0, 1):
                points[node][axis] += max(-3, min(3, force[node][axis]))
    return {node: [round(x, 2), round(y, 2)] for node, (x, y) in points.items()}


def build_explorer(nodes, source_edges, graph, partition, names, seed):
    full_weighted = weighted_graph(nodes, source_edges)
    weighted = {node: {neighbor: value for neighbor, value in full_weighted[node].items() if neighbor in graph} for node in graph}
    weighted_original, weighted_modularity = louvain(weighted, seed)
    weighted_partition, alignment = align_partitions(partition, weighted_original)
    edges = disparity_edges(weighted)
    positions = explorer_layout(graph, partition, edges, seed)
    metadata = {node["node_id"]: node for node in nodes}
    summaries = _summaries(partition, names, graph)
    weighted_summaries = _summaries(weighted_partition, names, graph)
    movers = [{"id": node, "label": names[node], "from": partition[node], "to": weighted_partition[node], "degree": len(graph[node])}
              for node in graph if partition[node] != weighted_partition[node]]
    movers.sort(key=lambda node: (-node["degree"], node["label"]))
    matrix = defaultdict(int)
    for node in graph:
        matrix[partition[node], weighted_partition[node]] += 1
    aristotle = "Aristotle"
    neighbor_groups = defaultdict(list)
    for node in graph.get(aristotle, ()):
        neighbor_groups[partition[node]].append(node)
    neighbor_summaries = [{"community": community, "label": next(item["label"] for item in summaries if item["id"] == community),
                           "count": len(members), "weight": sum(weighted[aristotle][node] for node in members),
                           "neighbors": [{"id": node, "label": names[node], "weight": weighted[aristotle][node]}
                                         for node in sorted(members, key=lambda node: (-weighted[aristotle][node], names[node]))]}
                          for community, members in sorted(neighbor_groups.items(), key=lambda item: (-len(item[1]), item[0]))]
    curve = [backbone_metrics(graph, edges, i / 100) for i in range(101)]
    weight_histogram = defaultdict(int)
    for edge in edges:
        weight_histogram[str(int(edge["weight"]))] += 1
    threshold = [edge for edge in edges if edge["weight"] >= 3]
    threshold_nodes = {node for edge in threshold for node in (edge["source"], edge["target"])}
    return {
        "nodes": [{"id": node, "label": names[node], "community": partition[node], "weighted_community": weighted_partition[node],
                   "degree": len(graph[node]), "strength": sum(weighted[node].values()), "x": positions[node][0], "y": positions[node][1],
                   "era": metadata[node].get("era", "")} for node in sorted(graph)],
        "edges": edges, "communities": summaries, "weighted_communities": weighted_summaries,
        "weighted_comparison": {"nmi": normalized_mutual_information(partition, weighted_partition), "normalization": "arithmetic",
                                "modularity": weighted_modularity, "community_count": len(weighted_summaries),
                                "mover_count": len(movers), "mover_fraction": len(movers) / len(graph), "movers": movers,
                                "alignment": alignment, "matrix": [{"from": a, "to": b, "count": count} for (a, b), count in sorted(matrix.items())],
                                "weight_histogram": dict(weight_histogram), "maximum_weight": max(edge["weight"] for edge in edges)},
        "backbone": {"curve": curve, "presets": [backbone_metrics(graph, edges, alpha) for alpha in (.05, .1, .2, .3, .5, 1)],
                     "breakpoint": backbone_breakpoints(graph, edges, names),
                     "global_threshold": {"minimum_weight": 3, "edges": len(threshold), "nodes": len(threshold_nodes)},
                     "degree_one_rule": "A degree-one endpoint has tail 1; the other endpoint can still keep its edge. Full graph mode includes every edge."},
        "aristotle": {"id": aristotle, "community": partition.get(aristotle), "weighted_community": weighted_partition.get(aristotle),
                      "degree": len(graph.get(aristotle, ())), "strength": sum(weighted.get(aristotle, {}).values()),
                      "neighbor_communities": neighbor_summaries, "community_count": len(neighbor_summaries),
                      "overlap_note": "This is a neighborhood spanning communities, not an overlapping community-detection algorithm. Louvain assigns one group per node."},
        "methods": {"graph": "Same undirected 1,374-node giant component in both partitions; directed article-link counts summed in both directions for weighted analysis.",
                    "weights": "Weights measure repeated links within Wikipedia articles and reciprocal directions. They do not measure intellectual influence or historical agreement.",
                    "louvain": "Seeded repeated local-moving and aggregation, resolution 1; self-loops counted once as edges and twice in degree.",
                    "comparison": "Arithmetic normalized mutual information: 2I/(H_unweighted+H_weighted). Weighted IDs aligned one-to-one by maximum node overlap; movers use that alignment.",
                    "backbone": "For endpoint i, tail=(1-w/s_i)^(k_i-1). Degree-one endpoints have tail 1: no relative allocation can be tested there, but the other endpoint may retain the edge. Keep an edge when either tail is strictly below alpha (OR rule); full mode is unfiltered.",
                    "layout": "Fixed deterministic community clusters, with local force springs from the alpha=.20 backbone only. Communities computed on the complete unweighted giant; coordinates reused in every lens.",
                    "curve": "101 alpha samples from 0 to 1; active-node counts exclude isolates. Giant means the largest edge-attached component (0 when no edges survive); component counts include all original nodes, including isolates. Breakpoints use exact tied edge-event thresholds."}
    }


def analyze(nodes, edges, null_trials=6, seed=2026):
    full = unweighted_graph(nodes, edges)
    g, keep = giant_component(full)
    names = {n["node_id"]: n["name"] for n in nodes}
    seeds = [seed + i for i in range(10)]
    runs = []
    partitions = []
    for run_seed in seeds:
        partition, score = louvain(g, run_seed)
        runs.append({"seed": run_seed, "modularity": score, "community_count": len(set(partition.values())), "community_sizes": _community_sizes(partition)})
        partitions.append(partition)
    partition, score = partitions[0], runs[0]["modularity"]
    agreements = [_pair_agreement(partition, other, seed + i) for i, other in enumerate(partitions[1:], 1)]
    null_scores = [louvain(degree_preserving_null(g, seed + i + 1), seed + i + 1)[1] for i in range(null_trials)]
    by = defaultdict(list)
    for n, c in partition.items():
        by[c].append(n)
    ordered = sorted(by, key=lambda c: (-len(by[c]), min(by[c])))
    remap = {c: i for i, c in enumerate(ordered)}
    communities = [{"id": i, "size": len(by[c]), "members": sorted(by[c])[:80],
                    "label": names[min(by[c], key=lambda x: names[x])]} for i, c in enumerate(ordered)]
    weighted = weighted_graph(nodes, edges)
    weighted_edges = sum(len(v) for v in weighted.values()) // 2
    primary_partition = {n: remap[c] for n, c in partition.items()}
    result = {
        "schema_version": 2, "source_url": SOURCE_URL, "snapshot_date": SNAPSHOT_DATE,
        "nodes": len(keep), "source_nodes": len(nodes), "directed_edges": len(edges),
        "undirected_edges": sum(len(v) for v in g.values()) // 2,
        "giant_component_fraction": len(keep) / len(nodes), "seed": seed,
        "modularity": score, "community_count": len(by), "community_sizes": _community_sizes(partition),
        "runs": runs, "stability": {"metric": "pairwise same-community agreement", "mean": statistics.mean(agreements), "minimum": min(agreements), "comparisons": len(agreements)},
        "null": {"type": "degree-preserving double-edge swaps", "trials": null_trials, "seed": seed + 1, "scores": null_scores, "mean": statistics.mean(null_scores), "p95": sorted(null_scores)[-1]},
        "partition": [{"id": n, "name": names[n], "community": remap[c], "degree": len(g[n])} for n, c in sorted(partition.items())],
        "communities": communities,
        "optional_weighted_metadata": {"description": "Not used for the primary result; article-link counts summed in both directions are compared in the explorer.", "undirected_edges": weighted_edges},
        "definitions": "Primary graph is the undirected, unweighted giant component. Louvain performs repeated local-moving and aggregation phases, then unpacks assignments to original nodes. Nulls preserve the exact degree sequence by double-edge swaps on the same node set."
    }
    result["explorer"] = build_explorer(nodes, edges, g, primary_partition, names, seed)
    return result


def main():
    _, nodes = load(ROOT / "data/raw/week4_philosophers_nodes.tsv")
    _, edges = load(ROOT / "data/raw/week4_philosophers_edges.tsv")
    result = analyze(nodes, edges)
    out = ROOT / "assets/data/week4.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "assets/data/week4.js").write_text("window.CROSSTALK_WEEK4 = " + json.dumps(result, ensure_ascii=True, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("nodes", "undirected_edges", "modularity", "community_count", "community_sizes", "runs", "stability", "null")}, indent=2))


if __name__ == "__main__":
    main()
