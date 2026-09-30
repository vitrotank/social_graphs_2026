# Crosstalk

**Small signals. Strange connections.** A newspaper of network investigations by Christos Diamantis (s253102), Dávid Weiner (s253347), and Evangelos Panagiotopoulos (s263125), for DTU 02805 Social Graphs and Interactions, Fall 2026.

[Website](https://vitrotank.github.io/social_graphs_2026/) · [Source](https://github.com/vitrotank/social_graphs_2026)

## Read, explore, or play

The front page is a directory: every published week has an explicit story link and an experiment or game link. The shared header links directly to Weeks 1–3. Future weeks remain visibly unpublished.

| Destination | What is there |
| --- | --- |
| `index.html` | Latest story, all eight week slots, and the games room |
| `week1/index.html` | Marvel's 303 pages, degree, isolates, searchable network, hub removal |
| `week2/index.html` | Models, friendship paradox, and what a null comparison can establish |
| `week3/index.html` | The paths and centrality story: bridge characters, removal curves, and shortest-route findings |
| `week4/index.html` | Philosopher communities: weighted seeded Louvain, null comparison, and interpretation |
| `play/louvain.html` | Exercise 4.12: a vanilla JavaScript two-phase Louvain toy |
| `play/index.html` | Crossed Wires: three weekly rounds and twelve practice puzzles |
| `play/cerebro.html` | The Popularity Trap: prediction game and model illustration console |
| `play/switchboard.html` | The Switchboard: Week 3's character-removal experiment, blackout dial, and route finder to Spider-Man |
| `grunge/index.html` | The Week 3 B-side: paths and centrality in a separate Wikipedia musician network, plus grunge radio |

Body text is larger, stories have contents links, and extended explanations use expandable panels. The Marvel journal retains its cream, ink, blue, and orange telephone identity; the extra uses charcoal and acid yellow with a record-store treatment.

## Run locally

Python 3.10+ is sufficient. There are no pip or npm dependencies.

```sh
python scripts/build.py
python -m http.server 8000
```

Open [localhost:8000](http://localhost:8000). Committed data makes the build independent of Wikipedia access. Local relative links and bundled JavaScript also let you open `index.html` directly from disk.

The grunge radio uses external YouTube playback and needs a connection. Browsers can block sound until a visitor interacts: use **Play radio** to start, and the player controls to pause or change tracks. A direct listening link remains available when embedding is blocked. The network analysis itself runs offline.

## Reproduce the analyses and check the site

```sh
python scripts/analyze.py
python scripts/analyze_week3.py
python scripts/analyze_week4.py
python scripts/crawl_grunge.py
python scripts/generate_week2_svgs.py
python scripts/build.py --output _site
python -m unittest discover -s tests
python scripts/browser_smoke.py
```

`crawl_grunge.py` rebuilds from the frozen snapshot by default; `--refresh` explicitly fetches a new Wikipedia snapshot. Its provenance and inclusion rules are in [data/grunge/README.md](data/grunge/README.md). The public extra is separate from the shared Marvel assignment data.

The browser check uses an existing Chrome or Chromium installation. Pass `--browser PATH` if necessary. Its ignored `.preview/` folder contains screenshots and check results. No browser or dependencies are installed by the check.

## Data and interpretation

The Marvel source is the course's frozen **26 August 2026** roster: **303 nodes, 1,784 directed edges, 17 isolates**. Its weak components contain 277 pages, 9 pages, and seventeen singletons. Raw TSV files, provenance, and checksums live in [data/raw](data/raw/README.md). The graph measures Wikipedia references, not friendships or alliances.

Week 3 collapses reciprocal edges for its undirected removal experiments. Betweenness is exact, normalized over the full roster, and excludes endpoints. Targeted removal ranks are fixed at the start. The random comparison uses 200 reproducible permutations. The separate Switchboard page lets readers disconnect characters, compare removal orders, and find routes using real arrow directions or the undirected projection; unreachable pages are reported explicitly. Methods, raw results, and the downloadable figure remain in the issue, which links directly to both the game and its grunge B-side.

Week 2's empirical friendship-paradox results come from the real graph. Its model curves and preset shuffle gauges are labeled **illustrative**; they are not fitted models or retained null ensembles. The report makes no significance claim from those sketches.

The B-side uses an explicitly sampled set of 15 musicians and 55 observed links. The full Wikipedia API crawl was unavailable; the snapshot preserves browser-observed hyperlink evidence and its sampling limits. A hyperlink between musician pages does not establish a musical collaboration.

Week 4 uses the course's **15 September 2026** philosopher release (1,444 nodes and 11,135 directed links). Directed links are projected to an undirected weighted graph; reciprocal links add weight. The seeded (2026) Louvain run reports modularity and six degree-preserving approximate stub-shuffle nulls. The null is a comparison baseline, not a significance test. Exercise 4.13 applies the result in the article; exercise 4.12 is the standalone browser toy.

## Add an issue

1. Create `templates/week4.html` with `@@HEADER@@`, `@@FOOTER@@`, and `@@ROOT@@` for shared paths.
2. Set its entry in `site.json` to `published`, with `title`, `summary`, `path`, and `template`. Optional `topic`, `short_title`, `experience_path`, and `experience_label` control its directory listing.
3. Add any new assets to the explicit publication allowlist in `scripts/build.py` and the isolated build inputs in `tests/test_site.py`.
4. Build and check; commit both templates and generated pages for root-based GitHub Pages publishing.

The header, latest story, quick directory, and full archive follow the registry. Shared layout lives in `style.css`; each experiment keeps its own JavaScript. The old homepage's report bookmarks still redirect through `home.js`.

## Crossed Wires schedule

A new three-round shift opens every **Wednesday at 19:00 Copenhagen / Paris time**. The configured 52 shifts run from 9 September 2026 through 1 September 2027; old shifts and practice stay available. UTC release timestamps account for daylight saving. Availability uses the device clock. The schedule is configured in `site.json`.

Puzzle generation is deterministic and checks unique solutions. Clues describe the selected puzzle edges. Progress, hints, ratings, and unfinished boards stay in the browser. Copying a repair receipt does not publish anything.

## Repository and publishing

Templates and generated HTML are both intentional: templates keep editing consistent, while generated pages support the repository's current **main → / (root)** Pages configuration. JSON downloads and their JavaScript bundles are likewise intentional; bundles support offline use. The raw datasets, generators, and tests are retained for reproducibility.

Unused legacy raster figures, the obsolete homepage CSS, and the empty dependency manifest have been removed. `_site`, `.preview`, Python caches, credentials, and local environments are ignored.

The **Publish Crosstalk** workflow recomputes the frozen analyses, builds, and tests. If Pages uses GitHub Actions as its source, the workflow also deploys the allowlisted `_site` artifact. With branch-based Pages, committed root files are published by Pages itself. The allowlist keeps scripts, tests, repository metadata, and browser profiles out of the staged artifact.
