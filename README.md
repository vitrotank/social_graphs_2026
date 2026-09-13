# EARTH—303 · The Bureau of Missing Connections

A fictional field bureau investigating a real Wikipedia network. Week 1 turns the course's frozen Marvel superhero snapshot into an interactive data story: follow the hubs, compare incoming and outgoing links, and look for the characters outside the giant component.

The analysis and static-site build use Python's standard library. The interactive browser experience uses plain JavaScript and CSS. No API key, package installation, or live Wikipedia connection is needed to reproduce the post.

## Run locally

Use Python 3.10 or newer. From the repository directory:

```sh
python scripts/analyze.py
python scripts/build.py
python -m unittest discover -s tests
python -m http.server 8000
```

Open [localhost:8000](http://localhost:8000). The generated site also includes the data needed to explore it by opening `index.html` directly, without an internet connection.

The analysis reads `data/raw/week1_nodes.tsv` and `data/raw/week1_edges.tsv`, then writes `assets/data/network.json` and `assets/data/summary.json`. The node roster is loaded before the edges so isolated nodes remain in the network. `scripts/build.py` renders `templates/index.html` to `index.html`.

For an optional browser check, run `python scripts/build.py --output _site`, then `python scripts/browser_smoke.py`. This requires an already installed Chrome or Chromium browser (or pass `--browser PATH`). It checks search, link direction, degree plots, hub removal, and mobile overflow, and saves screenshots in `.preview/`. It does not install anything.

## Publish on GitHub Pages

The included workflow rebuilds and checks the site on a push to `main`, or when run manually from the Actions tab. It detects the repository's existing Pages publishing mode. With **Deploy from a branch**, GitHub publishes the generated files committed at the root of `main`. With **GitHub Actions**, the workflow publishes only the staged `_site` directory. The build has read-only repository/Pages access; the deployment job has the Pages and identity permissions it requires.

1. Keep this repository public for the course website.
2. Keep the existing **Deploy from a branch → main → / (root)** setting, or select **GitHub Actions** to deploy the Python build artifact.
3. Run the Python build and push the generated files to `main`. In Actions mode, you can also run **Publish EARTH—303** from **Actions**.
4. Wait for a successful deployment, then open the URL shown by the deployment job.

The intended address is [vitrotank.github.io/social_graphs_2026](https://vitrotank.github.io/social_graphs_2026/). This README does not confirm that publication has completed.

To inspect exactly what will be published:

```sh
python scripts/build.py --output _site
python -m http.server 8000 --directory _site
```

## Make it your group's site

Edit `site.json` for the group's details, `templates/index.html` for the story, `style.css` for the appearance, and `app.js` for the interactions. Run the build again after changing the template or configuration. Add a new post each week and keep the frozen Week 1 data unchanged so its findings remain reproducible.

In `site.json`, set `group_name` to your chosen group name and edit the members' names in the `members` list. The current group is Christos Diamantis (s253102) and Dávid Weiner (s253347). `title`, `course`, and `semester` control the other labels; `repository_url` and `site_url` identify your repository and published website.

The fictional bureau is a presentation device. A Wikipedia link measures a reference between pages; it does not establish a friendship, an alliance, a fight, or a character's importance in Marvel canon. The story's claims concern this snapshot and this restricted roster.

## Data and course credits

The network is the frozen Week 1 release for [Social Graphs and Interactions 2026](https://sunelehmann.com/socialgraphs2026-web/data/), based on Wikipedia's [Marvel Comics superheroes category](https://en.wikipedia.org/wiki/Category:Marvel_Comics_superheroes). The raw node and edge files are included for reproducibility. See [data/raw/README.md](data/raw/README.md) for local provenance and checksums.

After publication, share the live link in the week's Teams channel by Monday evening and leave constructive, friendly feedback on another group's post. Those course actions are separate from this site's build and deployment.
