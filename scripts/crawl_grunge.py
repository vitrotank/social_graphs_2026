#!/usr/bin/env python3
"""Freeze the direct Wikipedia grunge roster and analyze its hyperlink network.

Default: rebuild assets from data/grunge/snapshot.json without a connection.
Use --refresh explicitly to fetch Wikipedia. Python standard library only.
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import adjacency, layout_components, weak_components

ROOT = Path(__file__).resolve().parents[1]
CATEGORY = "Category:Grunge musicians"
API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "CrosstalkStudentProject/1.0 (https://github.com/vitrotank/social_graphs_2026; educational network analysis)"


def api(**params):
    url = API + "?" + urlencode(dict(format="json", formatversion=2, **params))
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=45) as response:
                payload = json.load(response)
            if "error" in payload:
                raise RuntimeError(payload["error"])
            return payload
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def crawl():
    members, continuation = [], {}
    while True:
        payload = api(action="query", list="categorymembers", cmtitle=CATEGORY,
                      cmnamespace=0, cmtype="page", cmlimit=500, **continuation)
        members.extend(payload["query"]["categorymembers"])
        if "continue" not in payload:
            break
        continuation = payload["continue"]
    excluded = [m for m in members if m["title"].startswith("List of ")]
    members = [m for m in members if m not in excluded]
    pages = []
    for index, member in enumerate(sorted(members, key=lambda x: x["title"]), 1):
        # Pin the parsed hyperlinks to this revision, rather than combining
        # a revision identifier with the links from a newer live revision.
        meta = api(action="query", pageids=member["pageid"], prop="revisions",
                   rvprop="ids|timestamp", rvlimit=1)["query"]["pages"][0]
        revision = meta["revisions"][0]
        parsed = api(action="parse", oldid=revision["revid"], prop="links")["parse"]
        links = sorted({link["title"] for link in parsed["links"] if link.get("ns") == 0})
        pages.append(dict(title=meta["title"], pageid=meta["pageid"],
                          revision_id=revision["revid"], revision_timestamp=revision["timestamp"],
                          links=links))
        print(f"[{index}/{len(members)}] {meta['title']}: {len(links)} article targets", flush=True)
        time.sleep(.15)
    return dict(category=CATEGORY, category_url="https://en.wikipedia.org/wiki/Category:Grunge_musicians",
                retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                extraction="MediaWiki API categorymembers namespace 0; parse links at each recorded revision; direct category only; List of pages excluded; no redirect alias resolution",
                excluded=excluded, pages=pages)


def betweenness(neighbors):
    """Exact normalized undirected Brandes centrality, including isolates."""
    scores = dict.fromkeys(neighbors, 0.0)
    for source in neighbors:
        stack, predecessors = [], {v: [] for v in neighbors}
        paths, distances = dict.fromkeys(neighbors, 0.0), dict.fromkeys(neighbors, -1)
        paths[source], distances[source] = 1.0, 0
        queue = deque([source])
        while queue:
            vertex = queue.popleft()
            stack.append(vertex)
            for target in sorted(neighbors[vertex]):
                if distances[target] < 0:
                    queue.append(target)
                    distances[target] = distances[vertex] + 1
                if distances[target] == distances[vertex] + 1:
                    paths[target] += paths[vertex]
                    predecessors[target].append(vertex)
        dependencies = dict.fromkeys(neighbors, 0.0)
        while stack:
            target = stack.pop()
            for vertex in predecessors[target]:
                dependencies[vertex] += paths[vertex] / paths[target] * (1 + dependencies[target])
            if target != source:
                scores[target] += dependencies[target]
    scale = (len(neighbors) - 1) * (len(neighbors) - 2)
    return {node: value / scale if scale > 0 else 0 for node, value in scores.items()}


def analyze(snapshot):
    pages = {page["title"]: page for page in snapshot["pages"]}
    edges = sorted({(name, target) for name, page in pages.items() for target in page["links"]
                    if target in pages and target != name})
    outgoing, incoming, neighbors = adjacency(pages, edges)
    components = weak_components(neighbors)
    positions = layout_components(components, neighbors, 230)
    centrality = betweenness(neighbors)
    nodes = []
    for name in sorted(pages):
        page = pages[name]
        x, y = positions[name]
        nodes.append(dict(id=name, label=name, url="https://en.wikipedia.org/wiki/" + quote(name.replace(" ", "_")),
                          revision_url=f"https://en.wikipedia.org/w/index.php?oldid={page['revision_id']}" if page.get("revision_id") else None,
                          in_degree=len(incoming[name]), out_degree=len(outgoing[name]), degree=len(neighbors[name]),
                          betweenness=round(centrality[name], 8), x=round(x, 6), y=round(y, 6),
                          component=next(i for i, group in enumerate(components) if name in group)))
    def ranking(key):
        return sorted(nodes, key=lambda node: (-node[key], node["id"]))[:5]
    return dict(meta={key: value for key, value in snapshot.items() if key != "pages"}, nodes=nodes,
                edges=[dict(source=s, target=t) for s, t in edges],
                summary=dict(nodes=len(nodes), directed_edges=len(edges),
                             undirected_edges=sum(map(len, neighbors.values())) // 2,
                             components=[len(c) for c in components],
                             isolates=[node for node in neighbors if not neighbors[node]],
                             top_in=ranking("in_degree"), top_bridge=ranking("betweenness")))


def write_assets(snapshot):
    data = analyze(snapshot)
    data["meta"]["snapshot_sha256"] = hashlib.sha256((ROOT / "data/grunge/snapshot.json").read_bytes()).hexdigest()
    output = ROOT / "assets/data"
    output.mkdir(parents=True, exist_ok=True)
    (output / "grunge.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "grunge.js").write_text("window.CROSSTALK_GRUNGE = " + json.dumps(data, ensure_ascii=True, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(json.dumps(data["summary"], indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Download a new real Wikipedia snapshot")
    args = parser.parse_args()
    path = ROOT / "data/grunge/snapshot.json"
    if args.refresh:
        snapshot = crawl()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    write_assets(snapshot)


if __name__ == "__main__":
    main()
