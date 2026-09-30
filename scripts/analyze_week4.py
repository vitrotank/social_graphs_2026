#!/usr/bin/env python3
"""Reproducible Week 4 communities on the course's philosopher graph.

The published analysis follows the course setup: the largest connected
component of an undirected, unweighted projection is analysed.  Reciprocal
edge counts are retained only as optional provenance metadata.
"""
from __future__ import annotations

import csv
import json
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
                weights[labels[neighbor]] += edge_weight * (2 if neighbor == node else 1)
            best, best_gain = old, 0.0
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
            new[ca][cb] = new[ca].get(cb, 0) + edge_weight
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
    edges = [(a, b) for a in out for b in out[a] if a < b]
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
    return {
        "schema_version": 2, "source_url": SOURCE_URL, "snapshot_date": SNAPSHOT_DATE,
        "nodes": len(keep), "source_nodes": len(nodes), "directed_edges": len(edges),
        "undirected_edges": sum(len(v) for v in g.values()) // 2,
        "giant_component_fraction": len(keep) / len(nodes), "seed": seed,
        "modularity": score, "community_count": len(by), "community_sizes": _community_sizes(partition),
        "runs": runs, "stability": {"metric": "pairwise same-community agreement", "mean": statistics.mean(agreements), "minimum": min(agreements), "comparisons": len(agreements)},
        "null": {"type": "degree-preserving double-edge swaps", "trials": null_trials, "seed": seed + 1, "scores": null_scores, "mean": statistics.mean(null_scores), "p95": sorted(null_scores)[-1]},
        "partition": [{"id": n, "name": names[n], "community": remap[c], "degree": len(g[n])} for n, c in sorted(partition.items())],
        "communities": communities,
        "optional_weighted_metadata": {"description": "Not used for the primary result; reciprocal links are retained only as metadata.", "undirected_edges": weighted_edges},
        "definitions": "Primary graph is the undirected, unweighted giant component. Louvain performs repeated local-moving and aggregation phases, then unpacks assignments to original nodes. Nulls preserve the exact degree sequence by double-edge swaps on the same node set."
    }


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
