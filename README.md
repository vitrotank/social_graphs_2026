# Crosstalk

**Small signals. Strange connections.** A playful network science notebook by Christos Diamantis (s253102) and Dávid Weiner (s253347), for DTU 02805 Social Graphs and Interactions.

[Visit the website](https://vitrotank.github.io/social_graphs_2026/)

The site is a little telephone switchboard: a simple homepage connects the weekly journal and an original game. The telephone language is a visual metaphor. The actual network consists of directed references between Wikipedia pages, not conversations, friendships, or Marvel alliances.

## Three places to explore

- **Home — `index.html`:** the group, latest published post, and all eight week slots. Unwritten weeks have no broken or empty links.
- **Week 1 — `week1/index.html`:** the complete Marvel analysis, searchable network, linear/log–log degree plots, isolates, and hub-removal experiment.
- **Crossed Wires — `play/index.html`:** twelve logic puzzles made from real links. Restore erased arrow directions to match the displayed incoming/outgoing counts.

## Run locally

Python 3.10 or newer is sufficient. The analysis, site builder, and puzzle generator use only the standard library. Run these commands from the repository directory:

```sh
python scripts/analyze.py
python scripts/build.py
python -m unittest discover -s tests
python -m http.server 8000
```

Open [localhost:8000](http://localhost:8000). You can also open `index.html` directly: the three pages use relative links and bundled JavaScript data, so the site works offline. No external fonts, API keys, or package downloads are required. Python prepares the data and pages; JavaScript handles the browser interactions.

For optional browser checks, run `python scripts/build.py --output _site`, then `python scripts/browser_smoke.py`. An existing Chrome or Chromium installation is required; pass `--browser PATH` if needed. Screenshots and results go in the ignored `.preview/` folder. The checks do not install anything.

## Add the next week

1. Create `templates/week2.html` with the next story. Use `@@HEADER@@`, `@@FOOTER@@`, and the `@@ROOT@@` prefix on shared asset and navigation paths; see `templates/week1.html` for an example.
2. Update the Week 2 entry in `site.json`:

```json
{
  "number": 2,
  "title": "Your next question",
  "summary": "A short invitation to read the new experiment.",
  "status": "published",
  "path": "week2/index.html",
  "template": "week2.html"
}
```

3. Run the build and tests. The builder creates the new page, links it in the archive, and features the latest published week on the homepage.
4. Commit the generated pages along with their templates and push to `main`.

Edit `site.json` for names, the site identity, and the week registry. Shared styling lives in `style.css`; Week 1 interactions in `app.js`; the game in `game.js` and `game.css`. The small `home.js` preserves bookmarks to the original report's anchors by taking visitors to Week 1.

## Where the numbers and puzzles come from

`scripts/analyze.py` loads the complete node roster before adding edges, preserving the 17 isolated characters. It writes `assets/data/network.json`, `summary.json`, and downloadable SVG plots. The frozen release contains 303 nodes, 1,784 directed links, and weak component sizes of 277, 9, and seventeen singletons.

`scripts/puzzles.py` selects small connected sets of real, non-reciprocal links. The clues are the incoming/outgoing degrees **within the selected puzzle**, not the full graph and not necessarily the entire induced subgraph. Exhaustive enumeration verifies that each puzzle has exactly one solution. Generation is deterministic. No Marvel trivia or live Wikipedia access is needed to solve them.

`scripts/build.py` renders all published pages, generates the puzzle payload, and bundles data for offline use. Its publication allowlist excludes repository metadata, control files, source scripts, tests, and browser profiles. The full source remains available in GitHub.

The data is the frozen 26 August 2026 Week 1 release from the [course data page](https://sunelehmann.com/socialgraphs2026-web/data/), based on Wikipedia's [Marvel Comics superheroes category](https://en.wikipedia.org/wiki/Category:Marvel_Comics_superheroes). Original TSV files, provenance, and checksums are in [data/raw](data/raw/README.md). Git attributes preserve the raw release bytes across operating systems.

## GitHub Pages

The public repository already publishes from **main → / (root)**. Push generated HTML, CSS, JavaScript, and data along with the Python source. GitHub Pages publishes the committed pages; the **Publish Crosstalk** workflow separately rebuilds and tests them.

If the repository is switched to **GitHub Actions** as its Pages source, the same workflow detects that mode and deploys the allowlisted `_site` artifact. To inspect that artifact locally:

```sh
python scripts/build.py --output _site
python -m http.server 8000 --directory _site
```

Share the live site link in the week's Teams channel and leave constructive feedback on another group's work as required by the course. The site build does not send messages on your behalf.
