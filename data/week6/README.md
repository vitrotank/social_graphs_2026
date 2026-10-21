# Week 6: the name trap, measured

**Question:** How much do character-title words change the Marvel corpus's
nearest textual neighbors? This is the reproducible exercise 6.11 contribution.
It complements the existing Week 6 lesson and Vector Drift game.

From the repository root:

```powershell
python scripts/analyze_week6.py
python -m unittest discover -s tests -p test_week6.py
```

Python's standard library is sufficient; no downloads, model training, API key,
random seed or installed NLP package is required. The script writes
`assets/data/week6.json`, `assets/data/week6.js` (`window.WEEK6_DATA`) and
`assets/figures/week6-name-audit.svg`. All three are deterministic outputs.

## Inputs and provenance

The frozen official archive is `data/raw/marvel_pages.zip`, from
<https://sunelehmann.com/socialgraphs2026-web/data/marvel_pages.zip>.
The course snapshot is **26 August 2026**. Its SHA-256 is
`36023ca077053b3df5bd55630754cb514c3f9dbecbd70afcb2283e5bcc0017ee`.
The existing Week 1 roster and directed hyperlink list supply node identifiers,
article titles, source URLs and auxiliary link status. The loader from
`scripts/analyze_week5.py` verifies that the decoded archive filenames match
**all 303 roster identifiers**, with no additional or missing articles.

Current Wikipedia content may differ. Evidence offsets refer to the decoded
UTF-8 frozen article, not today's web page. Each record includes the original
article URL, exact text, half-open Python character offsets `[start:end]`, and
up to 110 original characters on each side. These are character offsets, not
byte offsets. Wikipedia text is attributed to its contributing articles and
available under Creative Commons Attribution-ShareAlike; linked article
histories identify contributors.

## The two representations

1. Reuse Week 5's Unicode letter tokenizer: case-fold, retain internal
   apostrophes, normalize curly apostrophes, split at hyphens, exclude numerals.
   Remove a terminal possessive `'s` **in both conditions**. This keeps
   `Storm` and `Storm's` together before testing name sensitivity. No stemming
   or function-word stoplist is used. The corpus has **727,203 tokens**.
2. Compute raw term frequency times `ln(N / df)` with `N = 303` and `df` the
   number of articles containing the token. No smoothing is used. Normalize
   each vector to unit L2 length, so its dot product is cosine similarity.
   Relative TF would yield the same cosine because it only rescales a whole
   document. All-document words have zero weight; these are exactly `a`,
   `and`, `by`, `character`, `comics`, `in`, `is`, `marvel`, `of`, `the`, `to`.
3. Build one global mask from **canonical node IDs**, not hand-selected names:
   URL-decode, replace underscores with spaces, strip every parenthetical
   qualifier, then tokenize with the same rules. Keep words of at least two
   letters except the five function words `and/of/the/for/in`. Thus a
   disambiguator such as `(Marvel Comics)` or `(android)` does not enter the
   mask, while meaningful words such as `storm`, `iron` and `black` do.
   The complete sorted **369-word mask** is exported in JSON.
4. Remove every occurrence of every masked type from every document, refit
   TF-IDF, renormalize and recompute every pair. All 303 articles stay in the
   denominator. Since the removal is global by word type, every retained
   type's DF and IDF is exactly unchanged; the script asserts this. Refitting
   is consistent, but its only effects are removing dimensions and changing
   vector norms. A cosine may therefore rise after removal.
5. Each article selects the highest-cosine article among the other 302.
   Equal full-precision scores choose the lexicographically first node ID.
   These are **303 directed nearest-neighbor choices**, with reciprocal
   choices counted for both source articles. They are not 303 unique pairs.
   Empty weighted vectors would have cosine zero; none occur in this corpus.

This is intentionally a title-word **sensitivity check**, not a claim that the
mask detects every name or isolates pure meaning. No threshold was fitted to
maximize the change count. The mask is fixed by the roster and the simple rule
above; the inspected examples do not affect the corpus calculation.

## Measured results

**158 of 303 articles (52.15%) change their nearest neighbor.** The remaining
145 keep it. The mask removes 76,210 token occurrences (**10.48%**), leaving
24,980 observed types. The median cosine of each article's original nearest
pair falls from **0.200793** to **0.160843**.

The figure holds each original pair fixed on both axes: x is its original
cosine, y its cosine after removal. Point color records whether this same
neighbor remains nearest when all alternatives are compared. It does not
compare the best old pair to a different best new pair on the y axis.
Reciprocal choices can overlap exactly. It is a complete corpus census, not a
sample with a sampling confidence interval.

## What was checked underneath the scores

Five examples were chosen for explanation after reading their actual passages;
they are not a random validation set or a quantitative semantic accuracy test.
All literal excerpts are asserted against the frozen text on every run.

- **Storm / Human Torch:** `storm` supplies **86.93%** of their original
  cosine. The passages distinguish Ororo Munroe's superhero name from Johnny
  Storm's surname. The pair falls **0.324746 → 0.097479**. Storm's replacement
  is Jean Grey (**0.429965**); both source passages explicitly identify X-Men
  membership. Retained `x/men` supply 46.22% of this new score.
- **Emma Frost / Jack Frost:** `frost` supplies **96.03%** of the initial
  cosine. Their passages describe telepathy and organic diamond versus ice
  and extreme cold. The pair falls **0.462873 → 0.058718**. Emma's new
  neighbor is Jean Grey (**0.503356**), whose inspected passage describes
  telepathy. The contribution includes telepathic and psychic language,
  although franchise terms and pronouns remain substantial.
- **Venom / Eddie Brock:** mutual nearest neighbors survive
  **0.866740 → 0.767564**. `symbiote` supplies **61.77%** after the mask.
  The source explicitly describes host bonding and states that Eddie's bond
  makes them Venom. A direct narrative connection survives the title words.
- **Black Panther / Shuri:** mutual nearest neighbors remain and their cosine
  rises **0.477592 → 0.723451**. However, `t'challa` now supplies **59.90%**:
  a civilian identity absent from canonical titles escaped the mask. The
  text confirms the sibling and Wakandan relationship, but the name removal
  is demonstrably incomplete.
- **Solomon Kane / Luke Cage:** title removal replaces Garrison Kane (where
  `kane` supplied **98.94%**) with Luke Cage at only **0.094308**. `isbn`
  supplies **34.53%** of the replacement cosine; `duffy` and `issue` follow.
  The inspected passages place ISBN in collected editions and bibliography,
  and Jo Duffy in publication history. Removing a surname can yield a new
  publishing-metadata match rather than a demonstrated fictional connection.

## Limits and interpretation

Changing 52% of nearest-neighbor choices establishes that this representation
is sensitive to title words. It does **not** mean 52% of original choices were
wrong or that the new choices are better. Names can encode real shared worlds
and family relationships; meaningful title words can be lost. Aliases, place
names, writers, franchise terms and pronouns survive, and bag-of-words cosine
cannot locate those words in narrative versus bibliography. We inspected five
contrasting cases, not all 303 replacements.

The JSON includes all original/replacement neighbors, cosine scores, ten
largest per-term cosine contributions and their shares, every article's
removed-token fraction, and exact evidence excerpts for the five cases.
The hyperlink field means at least one directed edge in either direction
between the pair in the frozen roster; it is auxiliary metadata, **not** a
ground-truth test for semantic relatedness. The 223 linked original choices
and 194 linked replacements therefore do not establish a gain or loss of
semantic quality.

The existing Word2Vec, PPMI, GloVe and game exports are a separate
lesson. This script does not claim to reconstruct those trained models or
their axes: the fully reproducible contribution here is the TF-IDF audit.
