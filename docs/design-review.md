# Marginalia design review

## Three directions considered before implementation

1. **Marginalia:** an interactive publication about reading between links. Warm paper, serif scale, quiet navigation and wine-red annotations; selecting a result reveals its passage. Evidence connects the statistical argument to the reading experience.
2. **The observatory:** a dark atlas with luminous connections. A lens switch compares structure with vocabulary. Strong for network exploration, but less directly suited to a text-focused Week 5 story.
3. **The cutting room:** an editorial workspace with stark typography and red editing marks. Removing words reveals what survives preprocessing. Strong methodological interaction, but less coherent for the existing four network investigations.

Marginalia was selected because links and language can share one editorial identity, while each issue keeps its own analytical composition. The site retains the project's Crosstalk name; the identity interprets the findings rather than borrowing Marvel costume graphics.

## References verified

Both supplied websites were inspected in live Chrome at 1440px and 390px. Screenshots and inspected routes are retained in ignored `.preview/reference-*` and `reference-review.json`. The web reader initially could not access them; direct browser rendering resolved that gap.

[Movega / Varmel](https://movega.github.io/02805-Social-graphs-and-interactions/index.html) establishes identity with a single large Atlas cover, restrained navigation and a coherent typographic hierarchy. Its illustrated weekly entries are linked as whole compositions. Those choices make the entry into a complex collection legible.

[Oddvar / Capes & Edges](https://oddvar112.github.io/Social-Graphs-and-Interactions/index.html) exposes weekly routes immediately and leads with findings. Its Week 5 link was followed and rendered. Short measured summaries and separate games give readers clear choices between reading and experimenting.

We adopt clear entry points and finding-led text, while using source passages as the central discovery interaction. We do not import their artwork, code or figures.

## Content audit and changes

The old homepage repeated a quick directory, an eight-slot directory, network preview, observation deck and games catalogue. The new cover has one featured issue, one compact published-week index, and a quieter laboratory. Future slots no longer crowd the reading surface. The selected network preview remains functional at `explore/index.html`.

Weeks 1–4 retain their measured results, identifiers, controls, source links and downloads. Duplicate chapter lists and introductory ornament were removed. Supporting fact strips and methods use native disclosures; the shared reading guide remains. Covers now lead with measured evidence. Week 4's null comparison explicitly concerns modularity.

Week 5 starts with the actual eight-word phrase, its 282-page reach and a clearly specified 97.7% pair denominator. The dominant plot shows all exact phrase-length thresholds on a labeled logarithmic scale. Selecting a length updates the count and passage directory; evidence comparisons expose original excerpts, context and frozen offsets. The optional first-paragraph comparison stays distinct from the full-article evidence directory.

## Substantive refinement

Initial desktop/phone renders exposed an overfull mobile masthead, repeated Week 5 action links, an unwanted word join at a removed line break, and a phone chart that needed horizontal scrolling with small labels. The masthead was reduced to one row; redundant cover navigation and actions were removed; the quoted phrase now wraps naturally with its original spacing. The phone plot now redraws with its own geometry, compact ticks and larger labels, keeping the entire scale visible. Passage excerpts are short by default, with complete matched context behind native controls.

The contrast, focus indication, reduced-motion handling, source attribution and separate sensitivity legend were reviewed alongside interaction checks. Full test results and screenshots are stored by the project tooling. No claims of user testing or copying direction are made.
