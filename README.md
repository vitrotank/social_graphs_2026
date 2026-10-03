# Crosstalk

**Read between the links.** A journal of social graphs and language by Christos Diamantis (s253102), Dávid Weiner (s253347), and Evangelos Panagiotopoulos (s263125), for DTU 02805, Fall 2026.

[Public website](https://vitrotank.github.io/social_graphs_2026/) · [Repository](https://github.com/vitrotank/social_graphs_2026)

The Marginalia redesign puts one investigation on the cover, gives each published week a direct navigation link, and separates reading from optional methods and experiments. Shared typography, paper, wine-red annotations, and accessible controls run through every route. Analytical figures keep their own clearly labeled encodings.

| Route | Investigation or experiment |
| --- | --- |
| `index.html` | Latest investigation, compact Weeks 1–5 index, laboratory |
| `week1/index.html` | Marvel degree, 17 isolates, directed atlas, hub removal |
| `week2/index.html` | Measured friendship paradox; explicitly illustrative model comparisons |
| `week3/index.html` | Exact paths, bridge characters, 200-trial removal comparison |
| `week4/index.html` | Philosopher communities, weighted overlap and disparity backbone |
| `week5/index.html` | Eight words. 282 pages. Shared phrases, with paired source evidence |
| `explore/index.html` | Selected network previews, relocated from the cover |
| `play/index.html` | Crossed Wires: weekly shifts and practice puzzles |
| `play/cerebro.html` | The Popularity Trap: predictions and model illustrations |
| `play/switchboard.html` | Marvel character removal and real shortest routes |
| `play/louvain.html` | Two-phase Louvain workshop |
| `grunge/index.html` | Separate Wikipedia musician sample and optional radio |

## Preview and build

Only Python 3.10+ is required; no npm or pip dependencies.

```sh
python scripts/build.py --output _site
python -m http.server 8000 --bind 127.0.0.1
```

Open [localhost:8000](http://localhost:8000/index.html). All analyses use committed snapshots. JavaScript bundles support direct disk viewing; static figures, article text and downloads remain available without JavaScript. External Wikipedia links and optional YouTube playback need a connection.

## Reproduce and check

```sh
python scripts/analyze.py
python scripts/analyze_week3.py
python scripts/analyze_week4.py
python scripts/analyze_week5.py
python scripts/crawl_grunge.py
python scripts/generate_week2_svgs.py
python scripts/build.py --output _site
python -m unittest discover -s tests
python scripts/browser_smoke.py --editorial-only
python scripts/browser_smoke.py --week4-only
python scripts/browser_smoke.py
python scripts/inspect_site.py
```

Browser checks use installed Chrome/Edge and the Python standard library. They exercise keyboard/touch controls, evidence filters, responsive layouts, offline bundles, static fallbacks and exact data readouts. Screenshots and check reports are written to ignored `.preview/`. `inspect_site.py --references` records the supplied reference websites separately.

## Week 5: shared words, different meanings

The official frozen archive contains the same 303 articles as the Week 1 roster: 727,203 Unicode letter tokens under our stated tokenizer. We measure each unordered pair's longest consecutive normalized word run, keeping paragraph boundaries, and recompute thresholds 8–60.

40,570 pairs share at least eight words. The phrase “in American comic books published by Marvel Comics” appears in 282 articles and accounts for 39,621 of those pairs (97.66%). Only 71 pairs reach twenty words and 13 reach forty. Longer matches include fictional narration, publication history, powers and bibliography; they still require reading.

The visualization offers exact threshold counts, a comparison after removing first paragraphs, 71 inspected long-match pairs, category and frozen-hyperlink filters, short source excerpts, and expandable complete matches with paragraph/character offsets. Labels use LLM-assisted inspection. Matches establish neither copying direction nor fictional relationships.

The compressed original corpus, SHA-256, definitions, candidate questions, sensitivity results, algorithm and counterexamples are documented in [data/week5/README.md](data/week5/README.md). Downloadable JSON and its browser bundle contain the same results. Wikipedia text is attributed to its contributing article pages and histories.

## Earlier evidence

The Marvel snapshot has 303 pages, 1,784 directed edges and 17 isolates. Week 3 uses exact normalized undirected betweenness, fixed original removal ranks and 200 seeded random permutations. Week 2's empirical friendship-paradox result is distinct from its illustrative model/null curves.

Week 4 uses the 1,374-node philosopher giant with 9,139 ties. Seeded Louvain finds nine communities, modularity 0.5024; weighted comparison NMI is 0.6223, with 383 movers after maximum-overlap alignment. Its disparity filter, null baselines, layout and limits remain documented in the article. The grunge sample is separate; [its provenance](data/grunge/README.md) describes its selection limits.

## Structure and publication

`site.json` owns published weeks and shared navigation. Templates are the editing source; generated root HTML intentionally supports the existing **main → / (root)** GitHub Pages configuration. `design.css` is injected by the builder into every page; story styles and experiments remain separate. JSON downloads and matching JavaScript bundles are intentional for reproducibility and disk mode.

To add a week, create its template using `@@HEADER@@`, `@@FOOTER@@`, `@@ROOT@@`; publish its registry entry; add its assets to the explicit build allowlist and isolated test inputs; build and commit the generated pages. The homepage, navigation and latest issue follow the registry. Legacy Week 1 homepage bookmarks still redirect correctly.

The Pages workflow recomputes frozen analyses, tests and stages an allowlisted `_site`. It deploys that artifact only if the repository uses GitHub Actions for Pages; branch-based Pages publishes committed root files. Workspace metadata, scripts, tests, browser profiles and credentials are excluded from the artifact. Local builds do not push or deploy.

Crossed Wires retains its 52 deterministic Wednesday 19:00 Paris/Copenhagen shifts, starting 9 September 2026, with daylight-saving-aware release timestamps. Progress stays in the visitor's browser. The grunge radio begins only after interaction and provides direct listening links.

[Coursework audit](docs/course-audit.md) records required public posts, optional exercises, and the remaining group actions of sharing Week 5 in Teams and giving peer feedback. [Design review](docs/design-review.md) records the concept, references and refinement decisions.
