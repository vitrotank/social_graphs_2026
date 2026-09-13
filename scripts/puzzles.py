"""Build small, uniquely solvable direction puzzles from the frozen network.

Every wire is a real, non-reciprocal Wikipedia link. A puzzle deliberately uses
a selection of links, not the full induced subgraph or full-network degrees.
The solver exhaustively checks all 2**m orientations (at most 256 per puzzle).
Only Python's standard library is needed; generation makes no network requests.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from itertools import product
import random
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


def _make_practice_puzzles(network: dict) -> dict:
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


def release_timestamp(day: date, release_hour: int = 19) -> str:
    """Return a Wednesday's Copenhagen release instant, including summer time.

    Python on Windows may have neither system IANA data nor the optional tzdata
    package. In that case the published EU summer-time calendar supplies the
    same offset for Wednesdays in this release window. It is deliberately
    bounded; extending beyond 2031 needs an updated calendar or IANA data.
    Calendar sources:
    https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52021XC0427(01)
    https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52026XC01660
    """
    if day.weekday() != 2:
        raise ValueError("Crossed Wires releases must fall on a Wednesday.")
    if not isinstance(release_hour, int) or not 0 <= release_hour <= 23:
        raise ValueError("The release hour must be an integer from 0 to 23.")
    try:
        local_zone = ZoneInfo("Europe/Copenhagen")
    except ZoneInfoNotFoundError:
        if not 2026 <= day.year <= 2031:
            raise ValueError("Install IANA timezone data to schedule releases outside 2026-2031.") from None
        march_end = date(day.year, 3, 31)
        october_end = date(day.year, 10, 31)
        summer_start = march_end - timedelta(days=(march_end.weekday() + 1) % 7)
        summer_end = october_end - timedelta(days=(october_end.weekday() + 1) % 7)
        # All releases are Wednesdays, away from Sunday's ambiguous local hour.
        offset = 2 if summer_start < day < summer_end else 1
        local_zone = timezone(timedelta(hours=offset))
    instant = datetime.combine(day, time(hour=release_hour), tzinfo=local_zone)
    return instant.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _weekly_board(nodes: dict, eligible: list[tuple[str, str]], neighbors: dict,
                  active: list[str], used: set, rng: random.Random, *, board_id: str,
                  stage: int, preferred: str, title: str) -> dict:
    """Find one new connected board; every accepted answer is checked exactly."""
    difficulty, node_count, edge_count = (
        ("easy", 3, 3), ("medium", 4, 5), ("hard", 6, 8)
    )[stage - 1]
    for attempt in range(10_000):
        anchor = preferred if preferred in neighbors and neighbors[preferred] and attempt < 1000 else rng.choice(active)
        selected = {anchor}
        while len(selected) < node_count:
            frontier = sorted(set().union(*(neighbors[node] for node in selected)) - selected)
            if not frontier:
                break
            weights = [1 + 5 * sum(candidate in neighbors[node] for node in selected) ** 2 for candidate in frontier]
            selected.add(rng.choices(frontier, weights=weights, k=1)[0])
        if len(selected) != node_count:
            continue
        candidates = [(a, b) for a, b in eligible if a in selected and b in selected]
        if len(candidates) < edge_count:
            continue
        wires = sorted(rng.sample(candidates, edge_count))
        signature = tuple(wires)
        node_ids = sorted(selected)
        if signature in used or not _connected(node_ids, wires):
            continue
        incoming = Counter(target for _, target in wires)
        if count_solutions(node_ids, wires, incoming) != 1:
            continue
        used.add(signature)
        outgoing = Counter(source for source, _ in wires)
        labels = {node: nodes[node].get("label", nodes[node].get("name", node)) for node in node_ids}
        label_counts = Counter(labels.values())
        return {
            "id": board_id,
            "title": title,
            "difficulty": difficulty,
            "stage": stage,
            "nodes": [{
                "id": node,
                "name": nodes[node].get("name", node) if label_counts[labels[node]] > 1 else labels[node],
                "in_target": incoming[node],
                "out_target": outgoing[node],
            } for node in node_ids],
            "edges": [{"a": min(a, b), "b": max(a, b), "source": a, "target": b} for a, b in wires],
            "explanation": "Every restored arrow is a real Wikipedia link in the frozen week-1 snapshot. Targets count only this board's selected wires. There is exactly one solution.",
        }
    raise ValueError(f"The network cannot furnish uniquely solvable weekly board {board_id} ({difficulty}).")


def make_puzzles(network: dict, *, week_count: int = 52, release_hour: int = 19,
                 first_release: str = "2026-09-09") -> dict:
    """Build the practice archive and a year of distinct, weekly three-board shifts.

    Releases are precomputed so a static GitHub Pages site can unlock them at
    their actual Copenhagen instant without waiting for a scheduled build.
    The calendar and each week's seed are stable: expanding week_count appends
    shifts without changing already published boards or saved progress IDs.
    """
    if not isinstance(week_count, int) or not 1 <= week_count <= 260:
        raise ValueError("Generate between 1 and 260 weekly shifts.")
    first_day = date.fromisoformat(first_release)
    # Validate the calendar before doing any expensive puzzle generation.
    releases = [(first_day + timedelta(weeks=week), release_timestamp(first_day + timedelta(weeks=week), release_hour))
                for week in range(week_count)]
    result = _make_practice_puzzles(network)
    nodes = {node["id"]: node for node in network["nodes"]}
    directed = {(edge["source"], edge["target"]) for edge in network["edges"]}
    eligible = sorted((a, b) for a, b in directed if a != b and (b, a) not in directed)
    neighbors = {node: set() for node in nodes}
    for a, b in eligible:
        neighbors[a].add(b)
        neighbors[b].add(a)
    active = sorted(node for node in nodes if neighbors[node])
    used = {tuple(sorted((edge["source"], edge["target"]) for edge in board["edges"])) for board in result["puzzles"]}
    themes = [
        ("The midnight connection", "Moon_Knight"),
        ("Storm on the switchboard", "Storm_(Marvel_Comics)"),
        ("A strange frequency", "Doctor_Strange"),
        ("The friendly neighborhood hotline", "Spider-Man"),
        ("Please hold for the Hulk", "Hulk"),
        ("Claws in the cable", "Wolverine_(character)"),
        ("The red receiver", "Black_Widow_(Natasha_Romanova)"),
        ("An unusually chatty caller", "Deadpool"),
        ("After hours in Harlem", "Luke_Cage"),
        ("The case of the missing arrow", "She-Hulk"),
        ("A tangled appointment", "Spider-Woman_(Jessica_Drew)"),
        ("The cosmic collect call", "Adam_Warlock"),
        ("All lines lead somewhere", "Captain_America"),
    ]
    weeks = []
    for index, (day, release_at) in enumerate(releases):
        number = index + 1
        theme, preferred = themes[index % len(themes)]
        repeat = index // len(themes)
        title = theme if not repeat else f"{theme} / transmission {repeat + 1}"
        shift_id = f"shift-{number:02}"
        rng = random.Random(303_1784 + number * 1_000_003)
        boards = [_weekly_board(nodes, eligible, neighbors, active, used, rng,
                                board_id=f"{shift_id}-stage-{stage}", stage=stage,
                                preferred=preferred, title=stage_title)
                  for stage, stage_title in enumerate(("Find the signal", "Untangle the exchange", "Connect the night shift"), 1)]
        weeks.append({"id": shift_id, "number": number, "title": title,
                      "release_at": release_at, "date": day.isoformat(), "puzzles": boards})
    result.update({
        "version": 2,
        "schedule": {"timezone": "Europe/Copenhagen", "release_hour": release_hour,
                     "week_count": week_count, "first_release": first_release},
        "weeks": weeks,
    })
    return result
