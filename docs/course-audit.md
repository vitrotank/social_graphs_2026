# Course requirements and preservation audit

The [course overview](https://sunelehmann.com/socialgraphs2026-web/index.html),
all Builder exercises in Weeks 1–5, [Week 5 in full](https://sunelehmann.com/socialgraphs2026-web/weeks/week5.html),
and the [Week 1 standing Go nuts rules](https://sunelehmann.com/socialgraphs2026-web/weeks/week1.html#go-nuts)
were read from the official course pages during this redesign on 3 October 2026.
This audit was extended on 21 October 2026 for the supplied Week 6 exercise 6.11
brief and the colleague's existing Week 6 article and Vector Drift game.

## What belongs on the public site

Each week requires one free-form group post using the week's tools on the shared
playground. The site must be public and identify the group. The standing rules
ask students to publish a question, method, figure or table, and something that
surprised them. Week 5 adds explicit underlying-text inspection and a meaningful
limitation. An inconclusive or contradictory result is a valid outcome when
reported honestly.

| Week | Public post | Other Builder exercises |
| --- | --- | --- |
| [1 · Networks](https://sunelehmann.com/socialgraphs2026-web/weeks/week1.html) | Exercise 1.8: launch the group site and investigate the frozen Marvel network. | Exercise 1.3 is a toolbox/notebook setup and hand-check exercise; it does not prescribe a separate public notebook submission. |
| [2 · Models and nulls](https://sunelehmann.com/socialgraphs2026-web/weeks/week2.html) | Exercise 2.11: investigate a question using models or null models. | Exercise 2.10, Ship an explorable, is an optional stretch. |
| [3 · Paths and centrality](https://sunelehmann.com/socialgraphs2026-web/weeks/week3.html) | Exercise 3.12: investigate paths, centrality, mixing, or cliques. | Exercise 3.11, Ship an explorable, is an optional stretch. |
| [4 · Communities and backbones](https://sunelehmann.com/socialgraphs2026-web/weeks/week4.html) | Exercise 4.13: investigate communities, overlap, weights, or backbones. The philosopher snapshot is the default; Marvel is allowed. | Exercise 4.4, the OpenAlex modularity-paper investigation, and Exercise 4.12, Ship an explorable, are optional. |
| [5 · Language](https://sunelehmann.com/socialgraphs2026-web/weeks/week5.html) | Exercise 5.9: one compelling question and convincing figure about the Marvel text corpus, with inspected text evidence. | Exercise 5.8, Ship an explorable, is an optional stretch. |
| [6 · Representations](https://sunelehmann.com/socialgraphs2026-web/weeks/week6.html) | Exercise 6.11: ask one question about the Marvel corpus using a representation from the week; include one convincing figure or table, a surprise, inspected underlying text, and one limitation. | Exercise 6.10, Ship an explorable, is an optional stretch; Vector Drift remains a companion to the post. |

Weeks 2–4 also allow crawling another Wikipedia category and applying that week's
tools. The existing grunge extension uses this standing option. Learn-mode
exercises concern individual understanding and the closed-book tests; this audit
does not invent a requirement to submit their answers or notebooks publicly.

## Week 5 scope and evidence

The week's methods include tokenization, stated preprocessing, token/type/hapax
counts, relative frequency, rank-frequency comparisons, concordances, n-grams,
collocations, Bag of Words, document-term matrices, and cosine similarity.
TF-IDF is introduced the following week. Exercise 5.9 explicitly favors one
question and one convincing figure over a collection of methods, and requires
checking the underlying text before believing a claim.

The [official data page](https://sunelehmann.com/socialgraphs2026-web/data/)
provides [marvel_pages.zip](https://sunelehmann.com/socialgraphs2026-web/data/marvel_pages.zip):
303 articles from the 26 August 2026 crawl that produced the Week 1 graph.
The supplied prose excludes templates, infoboxes, reference markers, and
navigation; headings and Wikipedia phrasing remain. URL-decoding archive
filenames is necessary to match all network identifiers, including
`Mark_Hazzard:_Merc`. All 303 roster nodes, including 17 isolates, belong to the
shared playground.

## Week 6 scope and evidence

Exercise 6.11 offers TF-IDF and cosine similarity, term contrasts, topic mixtures,
PPMI context vectors, and Word2Vec as ways to ask a question. It favors one good
question and convincing figure over collecting methods, and explicitly requires
reading the underlying text before believing a claim. A separate answer to every
suggested opener is not required.

The added investigation follows the "Names or meaning?" opener. It compares
TF-IDF nearest neighbors before and after applying one global mask of
title-derived words to every article in the frozen Marvel corpus. The figure
and source excerpts make the sensitivity
check inspectable. Title words are a proxy for names: ordinary words may be
removed, and aliases or civilian names can remain. Neighbor changes therefore
need passage inspection rather than automatic name-driven labels.

The colleague's article and Vector Drift game are preserved. The game export
contains 28 characters, 18 palette terms, and five missions. The browser moves
through exported three-dimensional coordinates and displacements and scores
Euclidean distance to the target. It does not calculate navigation using the
stored 100-dimensional vectors. No trainer, PCA transform, or axis seed lists
are committed, so the export's original model and projection cannot be
independently reconstructed from this repository. The new standard-library
TF-IDF analysis provides separately reproducible corpus evidence.

Run `python scripts/analyze_week6.py` to regenerate
[`assets/data/week6.json`](../assets/data/week6.json), its matching offline
JavaScript bundle, and
[`assets/figures/week6-name-audit.svg`](../assets/figures/week6-name-audit.svg).
The exact tokenizer, TF-IDF definition, mask construction, rankings, source
offsets, and provenance are documented in
[`data/week6/README.md`](../data/week6/README.md).

## Existing work retained by the redesign

| Story and measured work | Public path | Companion or supporting path |
| --- | --- | --- |
| Week 1: 303 pages, 1,784 directed links, degree distributions, isolates, and the nine-page island | `week1/index.html` | Character atlas within the story; raw TSVs in `data/raw/`; `play/index.html` |
| Week 2: friendship paradox for 250 of 286 linked pages; models and null-model illustrations explicitly identified as illustrative | `week2/index.html` | `play/cerebro.html`; downloadable SVG figures in `assets/figures/` |
| Week 3: exact centrality, character removals, random-removal comparison, and shortest paths | `week3/index.html` | `play/switchboard.html`; `grunge/index.html`; `assets/data/week3.json` |
| Week 4: philosopher communities, weighted/unweighted overlap, and disparity backbones | `week4/index.html` | Atlas within the story; `play/louvain.html`; `assets/data/week4.json` |
| Week 5: corpus investigation with reproducible measurements and traceable passages | `week5/index.html` | `scripts/analyze_week5.py`; `assets/data/week5.json`; corpus provenance in `data/raw/` |
| Week 6: title-word sensitivity of TF-IDF neighbors, with inspected source passages; existing vector discussion | `week6/index.html` | `scripts/analyze_week6.py`; `assets/data/week6.json`; `data/week6/README.md`; preserved Vector Drift at `play/vector-voyage.html` |
| Optional selected network preview, relocated from the crowded homepage | `explore/index.html` | Links to the complete Week 1 and Week 4 atlases |

The Python analysis scripts, original frozen inputs, downloadable results,
source attribution, legacy story fragments, and companion URLs remain available.
Generated HTML remains compatible with root-based GitHub Pages publishing.

## Actions for the group

The standing rules also require posting the site URL in the week's Teams channel
by Monday evening and leaving constructive, friendly criticism on at least one
other group's post. These are external group actions for each weekly post,
including Week 6; this website work does not send the Teams link or peer feedback.
The group should also read the new analysis and be prepared to explain and defend
its choices, as the course overview requires for Builder work.
