# Week 5 — When Marvel pages share words, are they sharing stories?

This analysis uses the **actual course corpus**, not an LLM-generated corpus.
Run from the repository root:

```powershell
python scripts/analyze_week5.py
python -m unittest discover -s tests -p test_week5.py
```

The Python 3.11 script uses only the standard library. It writes
`assets/data/week5.json` and `assets/data/week5.js`; the latter assigns
`window.WEEK5_DATA` for the static GitHub Pages website. No network access is
needed to reproduce the analysis from the committed inputs.

## Frozen inputs and provenance

- Official archive: https://sunelehmann.com/socialgraphs2026-web/data/marvel_pages.zip
- Acquired on 3 October 2026; snapshot **26 August 2026**.
- Local archive: `data/raw/marvel_pages.zip`, 1,833,017 bytes.
- SHA-256: `36023ca077053b3df5bd55630754cb514c3f9dbecbd70afcb2283e5bcc0017ee`.
- Source and target metadata: `data/raw/week1_nodes.tsv` and
  `data/raw/week1_edges.tsv`, the existing frozen network.

The course describes these as full plain-text Wikipedia articles after its
crawl preprocessing. Shared navigation templates, infoboxes and reference
markers were removed upstream; headings and house phrasing remain. Our
analysis does **not** assume that all remaining prose is fictional narration.
The zip README says each filename is the URL-encoded Week 1 node identifier.
We decode filenames and require the exact same set of 303 identifiers, rejecting
missing, extra or duplicate pages. `README.txt` and directory entries are
excluded. Every character article is retained.

The input is a frozen archive; the current Wikipedia pages can differ. The
interactive evidence records original character offsets and original text,
as well as a Wikipedia source URL. The archive is available on the site for
inspection of the frozen source. Wikipedia source prose is attributed to its
contributing articles and available under Wikipedia's Creative Commons
Attribution-ShareAlike license; article histories identify contributors.

## Candidate questions and decision

Three candidates were measured before choosing the story:

1. **Do better-connected characters have longer articles?** Token length versus
   undirected distinct-neighbor degree has Spearman correlation **0.83207**,
   with average ranks for ties. This is a strong association, but longer pages
   also have more opportunities to link. It does not measure fictional fame.
2. **Which pages sound alike as bags of words?** Cosine similarity of raw token
   counts after an explicit 78-word function-word stoplist gives Eddie Brock /
   Venom **0.917211**, Spider-Man / Spider-Man Noir **0.874096**, and Mayday Parker /
   Spider-Girl **0.871438**. Related names and identities dominate the top
   examples, while word order and the source location disappear. The exact
   stoplist and five top pairs are in the browser JSON.
3. **When pages share words, are they sharing stories?** Consecutive n-grams
   provide a directly inspectable answer: almost every pair seems related at
   short phrase lengths, but nearly all of that overlap can be explained by
   one editorial phrase. Long matches then reveal several distinct kinds of
   shared material. This was selected for its evidence and visual explanation.

TF-IDF is **not** used: the course explicitly reserves it for the following
week. The selected contribution uses Week 5 tokenization, counts, n-grams and
context inspection. The optional candidate uses Week 5 bag-of-words cosine.

## Definition and exact algorithm

A token is a sequence of Unicode letters, optionally containing internal
straight or curly apostrophes. We case-fold text and replace curly apostrophes
with straight ones. Hyphens separate tokens. Numbers and punctuation are
excluded. No stopwords, names or headings are removed, and no stemming is
performed. The corpus contains **727,203 tokens** under this definition.

We split each article at blank-line paragraph boundaries. A matching run may
span sentences or a single newline, including a section heading. It cannot
cross a blank line. **Exact** means an identical normalized word sequence;
punctuation, letter case and excluded numerals may differ in the source text.

An inverted index stores every eight-word seed with its page, paragraph and
word offset. For each seed that occurs in different articles, we extend the
match until the tokens diverge. Seeds with an identical predecessor are
skipped because the longer run starts earlier. We retain the longest run for
each **unordered pair of distinct pages**. Equal-length ties choose the earliest
source position deterministically. This finds all runs of at least eight words,
without sampling. Intra-article repetition is not counted.

At threshold *k*, a pair counts once if its longest run is at least *k* words.
The denominator is all **45,753** possible pairs of the 303 articles. The chart
reports the complete corpus census at each integer threshold 8–60; there is no
sampling confidence interval. If using a logarithmic count axis, the axis and
its ticks must explicitly say so.

## Measured results and source inspection

| Minimum shared run | Pairs | Articles involved | Pairs after removing first paragraph |
| --- | ---: | ---: | ---: |
| 8 words | 40,570 | 302 | 8,649 |
| 12 words | 8,111 | 286 | 655 |
| 16 words | 344 | 184 | 132 |
| 20 words | 71 | 77 | 37 |
| 24 words | 42 | 45 | 23 |
| 40 words | 13 | 19 | 13 |

The eight-word sequence “in American comic books published by Marvel Comics”
occurs in **282 articles**. Those articles alone produce **39,621** matching
pairs, or **97.66%** of the 40,570 pairs that share at least eight words.
This calculation counts article pairs, not occurrences of the phrase.

We separately indexed the first paragraph and remaining paragraphs of every
article for this exact normalized eight-word sequence. It appears in the first
paragraph of **all 282 containing articles**, and in later paragraphs of
**zero articles**. These counts are computed from the source tokens, not
assigned from the phrase's meaning: the short-phrase result is specifically a
shared publisher description in the leads. The JSON records
`standard_phrase_lead_documents` and `standard_phrase_body_documents`.

All 71 longest matches of at least 20 words were inspected in context and
assigned descriptive passage labels. Labels do not determine the measured
counts and are not exhaustive topic classifications. A pair can share several
kinds of material, but the explorer shows its **longest** run only. Of these 71
pairs, 31 have their longest match in both first paragraphs, and 44 have at least
one hyperlink between them in the frozen directed network.

Representative observations:

- **Story:** Mayday Parker and Spider-Woman share the longest run, **166 words**,
  in their *Spider-Man: Life Story* material. The passage describes Claire and
  Benjy's family chronology and Morlun's attack. This is an overlap between
  a character article and an article about identities using the Spider-Woman
  name, not evidence of a tie between two distinct fictional people.
- **Publication history:** Cyclops and Jean Grey share **102 words** discussing
  Jean's return, Cyclops leaving his family and the production of *X-Factor*.
  The surrounding discussion concerns writing decisions as well as fiction.
- **Powers and equipment:** Bucky and Rikki Barnes share **49 words** describing
  a bulletproof outfit and a vibranium-photonic shield. The general Bucky article
  summarizes the identity also covered by the individual character article.
- **Counterexample to “long means narrative”:** Spitfire and Union Jack (Joseph
  Chapman) share **103 normalized words** in a collected-editions bibliography.
  Several dates and issue numbers are omitted by the primary word tokenizer.
- **Counterexample to “long means unique prose”:** Radian and Scaredycat share a
  **34-word lead formula** naming Strikeforce: Morituri and its creators. A
  related group of pages uses the same introductory structure. Raising the
  threshold alone is not a semantic filter.
- **A short match:** Abomination and Adam Warlock share only **12 words** in
  their longest run, a publisher description. That match does not establish
  a meaningful fictional relationship.

The interpretation is that common editorial phrasing accounts for most short
overlaps. The measured collapse with longer thresholds does not establish who
copied whom, and the longest surviving passages mix story, production history,
quotation, bibliography and formula.

## Sensitivity and functional checks

Removing each article's **first blank-line-delimited paragraph** and rerunning
the whole analysis reduces the short overlap dramatically. It is a reproducible
proxy for removing leads, not a perfect heading-aware semantic extraction.
The unchanged count of 13 pairs at 40 words supports the persistence of body
passages independently of the introductions.

Retaining letter-or-number tokens yields **40,581 pairs at 8 tokens**, **82 at 20**
and **14 at 40**. The steep pattern persists. The longest result becomes 168
tokens; our main “166 words” excludes numerals by definition.

Tests check paragraph boundaries, maximal extension, deterministic ties,
normalization, numeric sensitivity, archive identity validation and every
published evidence offset. They verify that each displayed pair's two source
passages have identical normalized words and the stated length. The complete
threshold sequence must decline monotonically and retain one denominator.

## Meaningful limitation

Exact word runs miss paraphrases, while larger articles have more opportunities
to contain long overlaps. A phrase match is not evidence of plagiarism, reuse
direction or a fictional relationship. Editorial formulas, quotations and
bibliographies can survive long thresholds. This contribution therefore makes
a claim about **this frozen Wikipedia corpus**, not the originality or social
structure of Marvel stories.
