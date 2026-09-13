"""Build small, uniquely solvable direction puzzles from the frozen network.

Every wire is a real, non-reciprocal Wikipedia link. A puzzle deliberately uses
a selection of links, not the full induced subgraph or full-network degrees.
The solver exhaustively checks all 2**m orientations (at most 64 per puzzle).
Only Python's standard library is needed; generation makes no network requests.
"""
from __future__ import annotations

from collections import Counter
from itertools import product
import random


def count_solutions(node_ids: list[str], edges: list[tuple[str, str]], targets: dict[str, int]) -> int:
    """Count wire orientations satisfying each socket's incoming-link target."""
    count = 0
    for bits in product((0, 1), repeat=len(edges)):
        incoming = Counter(edge[bit] for edge, bit in zip(edges, bits))
        count += all(incoming[node] == targets[node] for node in node_ids)
    return count


def _connected(node_ids: list[str], edges: list[tuple[str, str]]) -> bool:
    reached = {node_ids[0]}
    while True:
        enlarged = reached | {v for a, b in edges if a in reached or b in reached for v in (a, b)}
        if enlarged == reached:
            return len(reached) == len(node_ids)
        reached = enlarged


def make_puzzles(network: dict) -> dict:
    """Return twelve reproducible puzzles, with answers traceable to input links.

    Stable sorting makes the result independent of input record order. Anchors
    curate the characters; a fixed PRNG explores their real neighborhoods.
    Fail explicitly if the supplied network cannot furnish the requested set.
    """
    nodes = {node["id"]: node for node in network["nodes"]}
    directed = {(edge["source"], edge["target"]) for edge in network["edges"]}
    eligible = sorted((a, b) for a, b in directed if a != b and (b, a) not in directed)
    neighbors = {node: set() for node in nodes}
    for a, b in eligible:
        if a not in nodes or b not in nodes:
            raise ValueError("Puzzle edge endpoint is missing from the node roster.")
        neighbors[a].add(b)
        neighbors[b].add(a)

    recipes = [
        ("easy", 3, 3, "Spider-Man", "Your first connection"),
        ("easy", 3, 3, "Hulk", "A little green interference"),
        ("easy", 3, 3, "Doctor_Strange", "A strange reception"),
        ("easy", 3, 3, "Storm_(Marvel_Comics)", "Weather on the line"),
        ("medium", 4, 4, "Black_Widow_(Natasha_Romanova)", "The switchboard thickens"),
        ("medium", 4, 4, "Luke_Cage", "A call from the neighborhood"),
        ("medium", 4, 5, "She-Hulk", "Please hold"),
        ("medium", 4, 5, "Wolverine_(character)", "Some crossed claws"),
        ("hard", 5, 6, "Moon_Knight", "The night shift"),
        ("hard", 5, 6, "Deadpool", "An unusually chatty caller"),
        ("hard", 5, 6, "Spider-Woman_(Jessica_Drew)", "A tangled appointment"),
        ("hard", 5, 6, "Adam_Warlock", "The final connection"),
    ]
    rng = random.Random(303_1784)
    used = set()
    puzzles = []
    active = sorted(node for node in nodes if neighbors[node])
    if not active:
        raise ValueError("The network has no non-reciprocal links for Crossed Wires.")
    for number, (difficulty, n_count, e_count, preferred, title) in enumerate(recipes, 1):
        chosen = None
        for attempt in range(6000):
            anchor = preferred if preferred in nodes and neighbors[preferred] and attempt < 3000 else rng.choice(active)
            selected = {anchor}
            while len(selected) < n_count:
                frontier = sorted(set().union(*(neighbors[node] for node in selected)) - selected)
                if not frontier:
                    break
                # Favor shared neighbors, so small sets have enough real wires.
                weights = [1 + 5 * sum(candidate in neighbors[node] for node in selected) ** 2 for candidate in frontier]
                selected.add(rng.choices(frontier, weights=weights, k=1)[0])
            if len(selected) != n_count:
                continue
            candidates = [(a, b) for a, b in eligible if a in selected and b in selected]
            if len(candidates) < e_count:
                continue
            wires = sorted(rng.sample(candidates, e_count))
            signature = tuple(wires)
            node_ids = sorted(selected)
            if signature in used or not _connected(node_ids, wires):
                continue
            incoming = Counter(target for _, target in wires)
            if count_solutions(node_ids, wires, incoming) != 1:
                continue
            chosen = (node_ids, wires, incoming)
            used.add(signature)
            break
        if chosen is None:
            raise ValueError(f"The network cannot furnish uniquely solvable puzzle {number} ({difficulty}).")
        node_ids, wires, incoming = chosen
        outgoing = Counter(source for source, _ in wires)
        label_counts = Counter(nodes[node].get("label", nodes[node].get("name", node)) for node in node_ids)
        socket_records = []
        for node in node_ids:
            label = nodes[node].get("label", nodes[node].get("name", node))
            socket_records.append({
                "id": node,
                "name": nodes[node].get("name", node) if label_counts[label] > 1 else label,
                "in_target": incoming[node],
                "out_target": outgoing[node],
            })
        puzzles.append({
            "id": f"line-{number:02}", "title": title, "difficulty": difficulty,
            "nodes": socket_records,
            "edges": [{"a": min(a, b), "b": max(a, b), "source": a, "target": b} for a, b in wires],
            "explanation": "These arrows reproduce actual Wikipedia links in the frozen week-1 snapshot. The counts apply only to the selected wires on this board; other links between these pages may exist. Each board has exactly one solution.",
        })
    return {
        "version": 1,
        "title": "Crossed Wires",
        "description": "The links are real. The arrowheads are missing. Restore their directions using each character's incoming and outgoing targets.",
        "puzzles": puzzles,
    }
