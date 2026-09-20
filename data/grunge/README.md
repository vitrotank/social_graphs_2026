# Grunge FM: the observed link sampler

This bonus is an explicitly **sampled** Wikipedia hyperlink network: 15 selected
musicians, 55 observed directed links, and 35 undirected connections. It is not
the complete grunge category or a census of every link in the selected articles.

## Source and inclusion rule

The roster was selected from the direct page members of
[Category:Grunge musicians](https://en.wikipedia.org/wiki/Category:Grunge_musicians).
The browser-visible category contained 68 pages at collection time, including
the excluded `List of grunge bands`. We selected 15 recognizable musicians across
several bands and recording production. This is a purposive editorial sample;
it has no random-sampling interpretation. Subcategories were not followed.

`snapshot.json` contains the roster, collection timestamps, article URLs, the
observed excerpt line spans, and a source/target URL pair and link label for
every recorded edge. Each link was visibly a Wikipedia hyperlink, and its target
was clicked to confirm the destination article. The record contains link facts,
not copied article prose. Article revisions were not exposed by this collection
method; `revision_id` is null rather than a fabricated revision number.

The browser supplied excerpts, not complete article HTML. An unrecorded link is
**unobserved**, not known to be absent. We record exact roster-name link labels;
alternate labels may be missed. Article excerpts may include infoboxes and other
editorial elements. This edge sample is frozen for reproducibility, but live
Wikipedia pages can change.

## Reproduce the frozen analysis

From the repository root:

```powershell
python scripts/crawl_grunge.py
python -m unittest discover -s tests -p test_grunge.py
python scripts/build.py
```

The default command requires only Python's standard library and performs no
network requests. It regenerates `assets/data/grunge.json` and `grunge.js` from
the committed snapshot. The public artifact records the snapshot SHA-256.

Directed edges are unique source-target pairs within the roster, with self-links
removed. In-degree counts incoming observed edges. For undirected analysis a
connection exists if either direction was observed. Weak components and exact
Brandes betweenness include every sampled node. Undirected betweenness excludes
endpoints and is normalized by `(n - 1)(n - 2)/2`; an unordered pair contributes
the fraction of its shortest paths through the node. The implementation sums
ordered source traversals and therefore divides by `(n - 1)(n - 2)`.

The browser uses breadth-first search and alphabetical tie-breaking to return
one shortest path. The graph drawing is a circular display, not an inference
about physical distance or similarity. Radio selections do not modify the data.

No null-model test is claimed here. Paths, ranks, and components only describe
this incomplete, observed graph. The main Week 3 Marvel investigation remains
the assignment's main network analysis.

## Optional complete future crawl

```powershell
python scripts/crawl_grunge.py --refresh
```

This explicitly requests network access and replaces the snapshot. It queries
MediaWiki category members (article namespace, directly included pages only),
excludes list pages, then parses each page at its recorded revision. Parsed links
include templates and infoboxes. Self-links and duplicate edges are removed in
analysis; redirect aliases are not resolved. API continuation is followed for
category members. The complete refresh was not performed for this release:
direct API access was unavailable during collection, so the checked-in artifact
uses the documented browser-evidence sample instead. Review the page's sampling
description and presentation before publishing a full-crawl replacement.

## Grunge FM

The radio lazily loads YouTube's IFrame API on the first play click and embeds
official music videos. It does not bundle, extract, or rehost audio. Playback
state comes from the actual player events; animation starts only on `PLAYING`.
There is a randomly chosen starting station on each page visit, pause and station
controls, an autoplay-blocked message, and a direct YouTube fallback link.
Browsers usually require a user gesture before audible playback. Offline use,
third-party blocking, embedding restrictions, or regional availability can stop
the player; the analysis and navigation continue to work without it.

- [Nirvana — Come As You Are, official video](https://www.youtube.com/watch?v=vabnZ9-ex7o)
- [Alice In Chains — Would?, official video](https://www.youtube.com/watch?v=Nco_kh8xJDs)
- [Soundgarden — Black Hole Sun](https://www.youtube.com/watch?v=3mbBbFH9fAg), also linked by [On A&M Records](https://www.onamrecords.com/artists/soundgarden/videography/united-states/a-m-records/none-114)
- [YouTube IFrame API documentation](https://developers.google.com/youtube/iframe_api_reference)

Wikipedia contributors are credited through the category and every article's
source URL. See [Wikipedia's reuse terms](https://en.wikipedia.org/wiki/Wikipedia:Reusing_Wikipedia_content).
