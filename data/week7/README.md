# Week 7: Close words. Long way round.

**Question:** Do pages that sound alike sit close in the hyperlink network?
This is the reproducible exercise 7.13 contribution. It uses one lexical
representation, one graph measurement and one percentage-bar figure, then
checks deliberately selected exceptions in the underlying frozen text.

From the repository root:

```powershell
python scripts/analyze_week7.py
python -m unittest discover -s tests -p test_week7.py
python scripts/build.py
```

Only Python's standard library and the committed inputs are needed. No model,
dependency, API key, seed, external request or live Wikipedia content is used.
The script deterministically writes `assets/data/week7.json`,
`assets/data/week7.js` (`window.WEEK7_DATA`) and
`assets/figures/week7-distance.svg` and a reflowed phone layout of that same
figure, `assets/figures/week7-distance-mobile.svg`, with identical bars and counts.

## Frozen inputs and provenance

The archive and graph share the course snapshot **26 August 2026**. The roster
has **303 pages** and the original edge list has **1,784 directed hyperlinks**.
The existing loaders verify the complete corpus/roster match and reject
duplicate nodes, unknown edge endpoints and duplicate directed edges.

| Input | Course source | SHA-256 |
| --- | --- | --- |
| `data/raw/marvel_pages.zip` | <https://sunelehmann.com/socialgraphs2026-web/data/marvel_pages.zip> | `36023ca077053b3df5bd55630754cb514c3f9dbecbd70afcb2283e5bcc0017ee` |
| `data/raw/week1_nodes.tsv` | <https://sunelehmann.com/socialgraphs2026-web/data/week1_nodes.tsv> | `a10ec309ac60ea8b72bcc1a18aba801414896676dac172619def0435e585391e` |
| `data/raw/week1_edges.tsv` | <https://sunelehmann.com/socialgraphs2026-web/data/week1_edges.tsv> | `87be017a35e8f27a1f1bc0912ebb5723c0084e460cb2dbd0d2abd0e83fc644b2` |

The script hashes the actual committed bytes and exports these records in
`corpus.inputs`. The node and edge copies were already committed locally;
this analysis does not assert fresh remote verification. Today's Wikipedia
pages can differ. Every evidence record includes the original article URL,
literal excerpt, before/after context, and half-open Python character offsets
`[start:end]` into the decoded UTF-8-sig archive text. These are character,
not byte, offsets. Canonical qualifiers remain in display labels whenever
removing them would merge distinct pages, such as Human Torch and its android.

## Representation and measurement

1. Reuse Week 6's **globally title-masked TF-IDF** exactly. Tokenize Unicode
   letter words, case-fold, normalize apostrophes and remove terminal
   possessive `'s`. Hyphens split words and numerals are excluded. There is
   no function-word stoplist, stemming or smoothing.
2. Build the global mask from all canonical Wikipedia node IDs: URL-decode,
   replace underscores, remove parenthetical qualifiers, tokenize, and keep
   tokens of at least two letters except `and/of/the/for/in`. Remove all
   occurrences of those **369 types** from every page. This leaves
   **650,993 tokens** and **24,980 observed types**. The mask is a coarse
   title-word sensitivity control, not complete name removal.
3. Weight retained counts with `tf * ln(303 / df)` and normalize each vector
   to unit L2 length. Cosine is their dot product. All-document words have
   zero weight. Empty vectors would have cosine zero; none occur here.
   This is **lexical similarity, not dense embeddings or pure semantics**.
4. Ignore hyperlink direction and collapse reciprocal edges into **1,434
   undirected edges**. Keep all 303 roster nodes, including the **17 isolates**.
   Use unweighted breadth-first search from every node. Sorted neighbors
   choose one reproducible shortest path among ties. A disconnected pair has
   `distance: null` and an empty path; it is never counted in `4+`.
5. Compute all **45,753 unordered pairs** and rank by full-precision cosine,
   descending, then canonical source/target IDs. Every source page chooses
   its highest-cosine alternative among all 302 others, including unreachable
   targets. Ties choose the lexicographically first canonical target ID.
   The exported nearest rows are **303 directed source choices**; reciprocal
   choices count for both sources. Scores are rounded only after ranking.

## One figure and its baseline

The figure compares the graph-distance distribution of each page's lexical
neighbor with the distribution over **all eligible source-target choices**.
There are 303 neighbor choices and `303 * 302 = 91,506` baseline choices.
Every source has 302 alternatives, so both distributions weight each source
equally. Using all unordered pairs would give the same baseline percentages,
but the figure prints ordered counts to keep the interpretation consistent.

| Undirected distance | Lexical neighbor / 303 | All alternatives / 91,506 |
| --- | ---: | ---: |
| 1 link | 194 (64.03%) | 2,868 (3.13%) |
| 2 links | 46 (15.18%) | 27,906 (30.50%) |
| 3 links | 31 (10.23%) | 37,620 (41.11%) |
| 4+ links | 11 (3.63%) | 8,130 (8.88%) |
| Disconnected | 21 (6.93%) | 14,982 (16.37%) |

Lexical neighbors are usually one link away in this snapshot. That finding
does not make every high-cosine pair semantically related, nor make every
far pair a missing fictional relationship. This is a census and descriptive
contrast; reciprocal choices are dependent and no causal or independent
significance test is claimed.

There are **38,262 connected unordered pairs**, with exact distance counts
`1: 1434, 2: 13953, 3: 18810, 4: 3803, 5: 257, 6: 5`, and **7,491
disconnected unordered pairs**. Among the connected pairs, **4,065** have a
path of at least four links. The `4+` cutoff is an exploratory display choice,
not a learned threshold, and disconnected pairs were kept separate throughout.

## Read the exceptions

We inspected exactly the **three highest-cosine pairs at finite distance >=4**,
plus the highest-cosine disconnected pair. This is deliberately selected
evidence, not a random semantic validation set. All literal case excerpts are
asserted against the frozen text when the analysis is rerun.

- **Backhand / Scatterbrain:** cosine **0.522864**, distance **4**, global
  pair rank **18**, far-pair rank **1**. `morituri` supplies **81.47%** of
  cosine and `strikeforce` another **6.75%**. Both pages explicitly identify
  the Strikeforce: Morituri team and describe a power-granting process that
  kills its recipients within a year. This is real shared story vocabulary,
  not matching individual powers. `Morituri` survives because qualifiers
  such as `(Morituri)` were excluded from the Week 6 mask. The chosen route
  is Backhand → Shear → Radian → Scaredycat → Scatterbrain.
- **Blue Eagle / Hyperion:** cosine **0.373425**, distance **4**, global
  rank **79**, far rank **2**. `squadron` and `supreme` supply **94.17%**.
  Their passages describe membership of the same alternate-Earth Squadron
  Supreme and the Overmind aftermath. Hyperion's page nevertheless combines
  several versions and realities. The frozen shortest route goes via Black
  Widow (Natasha Romanova), Adam Warlock and Genis-Vell.
- **Ruby Summers / Scarlet Scarab:** cosine **0.256983**, distance **4**,
  global rank **159**, far rank **3**. `layla` supplies **98.10%**. Ruby's
  page means **Layla Miller**; Scarlet Scarab's means **Layla El-Faouly**.
  The retained shared first name is a false friend. Neither Layla is a
  canonical title token in this roster, so the mask did not remove it.
  The route goes via Cyclops, Doctor Nemesis and Human Torch (android).
- **Happy Sam Sawyer / Junior Juniper:** cosine **0.409495**, no path,
  global rank **62**. Their text calls Sawyer the Howling Commandos'
  commanding officer and Juniper a founding member. This is the strongest
  disconnected lexical match. An absent path in this restricted snapshot
  clearly does not establish an absent fictional relationship.

## What the export lets you inspect

`comparison` contains the five figure bins with both counts and fractions.
`nearest` contains all 303 source choices: canonical IDs, distinct labels,
source URLs, cosine, graph distance, deterministic shortest path, global pair
rank and ten largest per-term cosine contributions and shares. Each explorer
row has an exact frozen-text passage around the **first occurrence of the
largest-contributing term in each article**. This deterministic passage rule
is an inspection aid, not a relevance model or a claim that the first mention
explains the entire document's score. Before/after context is retained too.

`cases` adds interpretations and curated exact excerpts for the three ranked
far matches. `disconnected_case` keeps the highest-cosine no-path example
separate. `top_far_pairs` exports the first 20 eligible pairs and ranks without
duplicating all evidence. `characters` resolves every path ID to its label
and URL. All 45,753 pairs are computed and ranked during analysis; the complete
pair matrix is not bundled into the browser payload. The script and frozen
inputs reproduce it. No selected case changes the full-corpus comparison.

## Limits

TF-IDF ignores context, word order and entity identity. Title masking can erase
meaningful words while leaving civilian identities, teams, creators, pronouns
and bibliographies. The Layla case is a concrete failure after masking, so
high cosine must not be called semantic ground truth.

The graph is a frozen, roster-restricted article-link network with directions
ignored. Missing intermediate pages, incomplete links and editorial conventions
can lengthen or disconnect paths. Four links are not four story relationships,
and a no-path pair is not infinitely unrelated. Article length and franchises
may affect both text and links. Three ranked exceptions cannot estimate
semantic accuracy or generalize to all Wikipedia or Marvel characters.

Wikipedia prose remains attributable to its contributing articles under
Creative Commons Attribution-ShareAlike; the linked article histories identify
contributors. Generated figure/code and evidence offsets do not replace that
attribution.
