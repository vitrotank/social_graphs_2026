# Frozen week-1 input

These TSV files are byte-for-byte copies of the week-1 release already present
in the local course exercise directory, `Exercises/Exercise Session 01 - Fall
2026/data/`. The file comments identify the snapshot as **2026-08-26**, with
303 characters, 1,784 directed edges and 17 characters absent from the edge list.
The adjacent exercise notebook, `marvel_degree_distributions.ipynb`, records
the following original course URLs:

- [Course data page](https://sunelehmann.com/socialgraphs2026-web/data/)
- [Node roster](https://sunelehmann.com/socialgraphs2026-web/data/week1_nodes.tsv)
- [Directed edge list](https://sunelehmann.com/socialgraphs2026-web/data/week1_edges.tsv)

No fresh download or Wikipedia crawl was performed for this site. These local
copies were not revalidated against the remote server. Their SHA-256 hashes are:

| File | SHA-256 |
| --- | --- |
| `week1_nodes.tsv` | `a10ec309ac60ea8b72bcc1a18aba801414896676dac172619def0435e585391e` |
| `week1_edges.tsv` | `87be017a35e8f27a1f1bc0912ebb5723c0084e460cb2dbd0d2abd0e83fc644b2` |

Run `python scripts/analyze.py` from the repository root to validate and analyze
the files. The script loads the full roster before adding edges, rejects unknown
endpoints and duplicate nodes or edges, and computes every published statistic
from the inputs. It records these hashes in `assets/data/summary.json` and
`assets/data/network.json`. Inputs are not rewritten or silently repaired.

An arrow A → B means that A's Wikipedia article links to B's within this roster.
Degree is a property of the snapshot's article links, not a measure of character
strength, friendship, or readership. The exercise notebook describes the edge
collection as running article text with redirects resolved and shared navigation
templates excluded. An absent link does not establish an absent fictional
relationship. Roster labels and descriptions are preserved as supplied; the
display label only removes a trailing disambiguation phrase in parentheses.

The visual layout is deterministic but not geographic: arrow directions are
ignored for its forces, and disconnected components occupy a separate lane.
The JSON provides incoming, outgoing, total and distinct-neighbor degrees
explicitly to avoid confusing their definitions. Logarithmic degree figures
omit zero-degree points, state how many were omitted, and retain all 303 pages
in the probability denominator. They do not claim a fitted power law.

## Week 4 philosopher input

The philosopher files are the course's frozen **2026-09-15** release, downloaded
from the [course data page](https://sunelehmann.com/socialgraphs2026-web/data/)
when Week 4 was implemented. It contains 1,444 philosophers (the seven
pre-1900 lists) and 11,135 weighted directed links. SHA-256:

| File | SHA-256 |
| --- | --- |
| `week4_philosophers_nodes.tsv` | `c5bd92ba8319fed505cc1a67f02fb3c62691595175c55abed2144140cfaac45` |
| `week4_philosophers_edges.tsv` | `ddc0cac2c763e6ade9acb336ffb391af43952a0c0fc75c4c370bd593b16e438b` |

Run `python scripts/analyze_week4.py` to regenerate the committed browser JSON.
