#!/usr/bin/env python3
"""Week 7: compare title-masked lexical neighbors with frozen hyperlink paths.

Run ``python scripts/analyze_week7.py`` from the repository root. Only Python's
standard library and the committed frozen inputs are needed. No model is
trained, downloaded, or represented as a dense semantic embedding.
"""
from __future__ import annotations

from collections import Counter, deque
import hashlib
from html import escape
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import load_graph
from analyze_week5 import WORD, load_corpus
from analyze_week6 import (build_title_mask, display_name as short_name, fit_tfidf,
                           normalized_tokens, pair_scores, source_excerpt,
                           top_terms)

ROOT = Path(__file__).resolve().parents[1]
BUCKETS = (('1', '1 link'), ('2', '2 links'), ('3', '3 links'),
           ('4+', '4+ links'), ('disconnected', 'Disconnected'))


def display_name(node, nodes):
    """Retain canonical qualifiers when removing them would merge labels."""
    label = short_name(node, nodes)
    return nodes[node]['name'] if any(
        other != node and short_name(other, nodes) == label for other in nodes
    ) else label


def shortest_paths(nodes, edges):
    """Sorted-neighbor BFS, ignoring link directions and self links.

    Keep every roster node, including isolates. Missing distances mean no path;
    disconnected pairs never receive an artificial finite or infinite number.
    Return adjacency, distance maps, and parent maps for path reconstruction.
    """
    adjacent = {node: set() for node in sorted(nodes)}
    for source, target in edges:
        if source not in adjacent or target not in adjacent:
            raise ValueError('Edge endpoint is outside the node roster.')
        if source != target:
            adjacent[source].add(target)
            adjacent[target].add(source)
    adjacent = {node: sorted(neighbors) for node, neighbors in adjacent.items()}
    distances, parents = {}, {}
    for source in adjacent:
        distance, parent = {source: 0}, {source: None}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for neighbor in adjacent[node]:
                if neighbor not in distance:
                    distance[neighbor] = distance[node] + 1
                    parent[neighbor] = node
                    queue.append(neighbor)
        distances[source], parents[source] = distance, parent
    return adjacent, distances, parents


def shortest_path(source, target, parents):
    if target not in parents[source]:
        return []
    path = [target]
    while path[-1] != source:
        path.append(parents[source][path[-1]])
    return list(reversed(path))


def bucket(distance):
    if distance is None:
        return 'disconnected'
    return str(distance) if distance < 4 else '4+'


def term_excerpt(texts, nodes, node, term, limit=360):
    """An exact frozen-text window around the FIRST occurrence of a term.

    The term is the pair's largest positive cosine contribution. This is a
    deterministic inspection aid, not a sentence-level relevance model.
    """
    text = texts[node]
    match = next((match for match in WORD.finditer(text)
                  if normalized_tokens(match.group()) == [term]), None)
    if match is None:
        raise ValueError(f'Term {term!r} missing from source {node!r}.')
    paragraph_start = text.rfind('\n\n', 0, match.start()) + 2
    if paragraph_start == 1:
        paragraph_start = 0
    paragraph_end = text.find('\n\n', match.end())
    if paragraph_end < 0:
        paragraph_end = len(text)
    start, end = paragraph_start, paragraph_end
    if end - start > limit:
        start = max(paragraph_start, match.start() - limit // 2)
        end = min(paragraph_end, start + limit)
        if start > paragraph_start:
            space = text.find(' ', start, match.start())
            if space >= 0:
                start = space + 1
        if end < paragraph_end:
            space = text.rfind(' ', match.end(), end)
            if space >= 0:
                end = space
    return {'node': node, 'name': display_name(node, nodes),
            'url': nodes[node]['url'], 'start': start, 'end': end,
            'text': text[start:end], 'before': text[max(0, start-80):start],
            'after': text[end:end+80], 'term': term}


def pair_record(source, target, score, distance, vectors, texts, nodes,
                parents, ranks, evidence=True):
    terms = top_terms(source, target, vectors)
    sources = []
    if evidence and terms:
        sources = [term_excerpt(texts, nodes, node, terms[0]['term'])
                   for node in (source, target)]
    return {'source': source, 'target': target,
            'source_name': display_name(source, nodes),
            'target_name': display_name(target, nodes),
            'source_url': nodes[source]['url'], 'target_url': nodes[target]['url'],
            'similarity': round(score, 9), 'distance': distance,
            'global_rank': ranks[tuple(sorted((source, target)))],
            'path': shortest_path(source, target, parents),
            'terms': terms, 'sources': sources}


def curated_cases(far_pairs, vectors, texts, nodes, parents, ranks):
    """The first three far pairs, ranked before reading, then checked in text.

    The interpretations apply only to the frozen corpus; tiny test fixtures do
    not receive Marvel-specific interpretations or cherry-picked replacements.
    """
    specs = [
        ('morituri', 'Same team. Four links apart.',
         'Backhand_(character)', 'Scatterbrain_(Morituri)',
         'Both articles explicitly identify Strikeforce: Morituri membership. Their biographies describe a process that grants powers but kills recipients within a year. Morituri supplies 81.5% of their cosine and strikeforce another 6.8%. This is a shared team and story setting, not evidence that their individual powers are the same. Morituri survives the title mask because parenthetical qualifiers are deliberately excluded. The four-link route reflects the supplied roster and edge snapshot; it does not establish that these teammates are distant within the fiction.',
         [('Backhand_(character)', 'The character is usually depicted as a member of the Strikeforce: Morituri.'),
          ('Scatterbrain_(Morituri)', 'The character is depicted as a member of the Strikeforce: Morituri.'),
          ('Backhand_(character)', 'their lifespan was significantly reduced, due to an inescapable flaw in the process, which ensured their death within a year after taking the process.'),
          ('Scatterbrain_(Morituri)', 'However, the process is unstable and inevitably kills its recipients within a year.')]),
        ('squadron', 'A shared universe survives the long route.',
         'Blue_Eagle_(character)', 'Hyperion_(character)',
         'Squadron and supreme supply 94.2% of this match. Reading confirms that Blue Eagle joins the Squadron Supreme and that an Earth-712 Hyperion is a founding member of that reality\'s team. Both passages also discuss the Overmind aftermath. Shared team vocabulary is therefore a real connection here, although Hyperion\'s page combines multiple versions and universes. A roster-restricted path is a measure of these article links, not a complete map of fictional relationships.',
         [('Blue_Eagle_(character)', 'He began his career as a superhero when he inherited the mantle of the American Eagle from his father and joined the Squadron Supreme.'),
          ('Hyperion_(character)', "Hyperion, also known as Mark Milton, is a founding member of his reality's Squadron Supreme and the last known Eternal on his Earth."),
          ('Blue_Eagle_(character)', 'The Squadron Supreme, as a result of their conflict with the Overmind, institute the "Utopia Program".'),
          ('Hyperion_(character)', 'Following the societal instability caused by Overmind\'s takeover of Earth, Hyperion and the Squadron assume control of the United States government.')]),
        ('layla', 'One name. Two different people.',
         'Ruby_Summers', 'Scarlet_Scarab',
         'Layla supplies 98.1% of this cosine. Ruby\'s page discusses Layla Miller; Scarlet Scarab\'s page discusses Layla El-Faouly. Those are different full names in the source. The title mask removes character-title words, not every person mentioned in an article, so layla remains. This high-ranked far pair is a lexical collision, not demonstrated semantic kinship. Its failure is visible only when we read beyond the score.',
         [('Ruby_Summers', 'When Layla Miller and a man named Dwayne show up one day looking for the now-aged Cyclops, Ruby attacks them.'),
          ('Scarlet_Scarab', 'May Calamawy stars as Layla El-Faouly in the Marvel Cinematic Universe television series Moon Knight (2022), with the character becoming the Scarlet Scarab in its final episode while predating her being introduced in the comics as the third Scarlet Scarab.')]),
    ]
    if [(source, target) for score, source, target, distance in far_pairs[:3]] != [
            (spec[2], spec[3]) for spec in specs]:
        return []
    records = []
    for index, spec in enumerate(specs):
        identifier, title, source, target, interpretation, needles = spec
        score, _, _, distance = far_pairs[index]
        record = pair_record(source, target, score, distance, vectors, texts,
                             nodes, parents, ranks, evidence=False)
        record.update({'id': identifier, 'title': title,
                       'eligible_rank': index + 1, 'interpretation': interpretation,
                       'sources': [source_excerpt(texts, nodes, node, needle, context=80)
                                   for node, needle in needles]})
        records.append(record)
    return records


def analyze_week7(nodes, edges, texts, archive_path=None, nodes_path=None,
                  edges_path=None):
    if set(nodes) != set(texts) or len(nodes) < 2:
        raise ValueError('Corpus must match a complete roster of at least two nodes.')
    mask = build_title_mask(nodes)
    counts = {node: Counter(word for word in normalized_tokens(text)
                            if word not in mask)
              for node, text in sorted(texts.items())}
    vectors, idf = fit_tfidf(counts)
    scores = pair_scores(vectors)
    adjacent, distances, parents = shortest_paths(nodes, edges)
    ordered = sorted(nodes)
    pairs = sorted(((scores[source][target], source, target,
                     distances[source].get(target))
                    for index, source in enumerate(ordered)
                    for target in ordered[index + 1:]),
                   key=lambda pair: (-pair[0], pair[1], pair[2]))
    ranks = {(source, target): index + 1
             for index, (_, source, target, _) in enumerate(pairs)}
    far_pairs = [pair for pair in pairs if pair[3] is not None and pair[3] >= 4]
    nearest = []
    for source in ordered:
        target = min(scores[source], key=lambda node: (-scores[source][node], node))
        nearest.append(pair_record(source, target, scores[source][target],
                                   distances[source].get(target), vectors,
                                   texts, nodes, parents, ranks))
    baseline = Counter(bucket(distance) for _, _, _, distance in pairs)
    choices = Counter(bucket(row['distance']) for row in nearest)
    pair_count = len(pairs)
    comparison = [{'key': key, 'label': label,
                   'nearest_count': choices[key],
                   'nearest_fraction': choices[key] / len(nodes),
                   'baseline_count': 2 * baseline[key],
                   'baseline_fraction': baseline[key] / pair_count}
                  for key, label in BUCKETS]
    connected = [pair for pair in pairs if pair[3] is not None]
    cases = curated_cases(far_pairs, vectors, texts, nodes, parents, ranks)
    disconnected = next((pair for pair in pairs if pair[3] is None), None)
    disconnected_case = None
    if disconnected:
        score, source, target, distance = disconnected
        disconnected_case = pair_record(source, target, score, distance,
                                         vectors, texts, nodes, parents, ranks)
        if (source, target) == ('Happy_Sam_Sawyer', 'Junior_Juniper'):
            disconnected_case['id'] = 'disconnected'
            disconnected_case['title'] = 'No route does not mean no relationship.'
            disconnected_case['interpretation'] = (
                'The highest-cosine disconnected pair discusses the Howling '
                'Commandos: Sawyer is their commanding officer and Juniper '
                'a founding member. The frozen graph has no path between '
                'them. Disconnected means unreachable in this supplied '
                'roster and edge list, not unrelated in the stories.')
            disconnected_case['sources'] = [
                source_excerpt(texts, nodes, source,
                               'Sawyer, also known as "Happy Sam," served as the commanding officer of the Howling Commandos.', context=80),
                source_excerpt(texts, nodes, target,
                               'Jonathan "Junior" Juniper was a founding member of the original Howling Commandos and fought alongside the team during World War II.', context=80)]
    result = {'documents': len(nodes), 'possible_pairs': pair_count,
              'eligible_ordered_choices': 2 * pair_count,
              'connected_pairs': len(connected),
              'disconnected_pairs': pair_count - len(connected),
              'far_pairs': len(far_pairs),
              'distance_counts': [{'distance': distance,
                                   'count': sum(pair[3] == distance for pair in pairs)}
                                  for distance in sorted({pair[3] for pair in connected})],
              'maximum_connected_distance': max((pair[3] for pair in connected), default=None),
              'isolated_nodes': sum(not neighbors for neighbors in adjacent.values()),
              'nearest_linked': choices['1'], 'nearest_far': choices['4+'],
              'nearest_four_plus': choices['4+'],
              'baseline_four_plus': 2 * baseline['4+'],
              'nearest_four_plus_fraction': choices['4+'] / len(nodes),
              'baseline_four_plus_fraction': baseline['4+'] / pair_count,
              'nearest_disconnected': choices['disconnected'],
              'nearest_linked_fraction': choices['1'] / len(nodes),
              'baseline_linked_fraction': baseline['1'] / pair_count,
              'zero_vectors': sum(not vector for vector in vectors.values()),
              'retained_tokens': sum(sum(bag.values()) for bag in counts.values()),
              'retained_types': len(idf), 'masked_types': len(mask)}
    inputs = []
    for path, label, url in [
            (archive_path, 'Article archive', 'https://sunelehmann.com/socialgraphs2026-web/data/marvel_pages.zip'),
            (nodes_path, 'Full node roster', 'https://sunelehmann.com/socialgraphs2026-web/data/week1_nodes.tsv'),
            (edges_path, 'Directed hyperlink list', 'https://sunelehmann.com/socialgraphs2026-web/data/week1_edges.tsv')]:
        if path:
            path = Path(path)
            inputs.append({'label': label, 'path': path.relative_to(ROOT).as_posix()
                           if path.is_relative_to(ROOT) else path.name,
                           'url': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'schema_version': 1, 'title': 'Close words. Long way round.',
            'question': 'Do pages that sound alike sit close in the hyperlink network?',
            'corpus': {'documents': len(nodes), 'snapshot_date': '2026-08-26',
                       'inputs': inputs, 'directed_edges': len(edges),
                       'undirected_edges': sum(map(len, adjacent.values())) // 2},
            'method': {
                'representation': 'Lexical similarity, not dense embeddings: reuse Week 6 globally title-masked TF-IDF, raw term frequency times ln(N/df), L2 normalization and cosine. No stopword list, stemming or smoothing.',
                'tokenization': "Week 5 Unicode letter tokens, case-folded with normalized apostrophes; remove terminal possessive 's, split at hyphens, exclude numerals.",
                'mask': 'Reuse the Week 6 global title mask from canonical Wikipedia IDs: URL-decode, replace underscores, remove parenthetical qualifiers, tokenize, retain words of at least two letters except and/of/the/for/in, then remove every occurrence from every document. Names, aliases and team labels absent from these title tokens can remain.',
                'distance': 'Unweighted shortest path after ignoring hyperlink direction, using only the frozen 303-node roster. A missing path stays null/disconnected and is never treated as distance 4+ or infinity. Sorted-neighbor breadth-first search chooses a reproducible shortest route when several exist.',
                'comparison': 'Each article chooses its highest-cosine alternative among all other roster pages, including unreachable pages. Count these directed choices once per source; reciprocal choices count twice. Baseline is all ordered source-target choices: every source has the same N-1 alternatives and the same weight. This is a complete finite census and descriptive comparison, not a randomized experiment or semantic accuracy test.',
                'ranking': 'Compute and rank every unordered pair by full-precision cosine descending, then canonical source/target ID ascending for ties. The displayed three cases are exactly ranks 1-3 after filtering to finite distance >=4; that threshold is an exploratory display choice, not a fitted boundary. Disconnected pairs are ranked and inspected separately.',
                'case_selection': 'Read the three highest-cosine unordered pairs with a finite shortest path of at least four links, plus the highest-cosine disconnected pair. These are deliberately selected exceptions, not a random sample or an estimate of semantic accuracy.',
                'terms': 'For each shared retained term, contribution is the product of its two L2-normalized TF-IDF weights; shares divide this contribution by total cosine. The ten largest contributions are exported.',
                'evidence': 'Explorer passages are exact frozen-text windows around the FIRST occurrence of the largest contributing term, not a relevance score. Curated cases use literal inspected excerpts. All offsets are half-open Python character offsets into decoded UTF-8-sig archive text, not byte offsets. before/after preserve additional context.',
                'rounding': 'Rank and choose before rounding. Export similarities, contributions and shares to nine decimal places. All-source nearest choices include zero cosines if required; zero vectors have cosine zero.'},
            'result': result, 'comparison': comparison,
            'characters': [{'node': node, 'name': display_name(node, nodes),
                            'url': nodes[node]['url']} for node in ordered],
            'nearest': nearest, 'cases': cases,
            'top_far_pairs': [dict(pair_record(source, target, score, distance,
                                               vectors, texts, nodes, parents,
                                               ranks, evidence=False),
                                   eligible_rank=index+1)
                              for index, (score, source, target, distance)
                              in enumerate(far_pairs[:20])],
            'disconnected_case': disconnected_case,
            'figure': {'path': 'assets/figures/week7-distance.svg',
                       'mobile_path': 'assets/figures/week7-distance-mobile.svg',
                       'description': 'Paired percentage bars compare graph distance for one highest-cosine lexical neighbor per article with every eligible source-target alternative. Both include disconnected pairs as a separate category. The baseline weights each source equally; reciprocal nearest-neighbor choices count twice. Percentages compare differently sized denominators, with counts printed beside each bar.'},
            'limitations': [
                'TF-IDF measures shared vocabulary, not contextual meaning. The Layla collision survives title masking; team names, creators, pronouns and publication metadata can also dominate. The mask additionally removes meaningful words in titles.',
                'Paths depend on the frozen hyperlink collection, the restricted superhero roster and ignored directions. Missing roster nodes or edges can lengthen or disconnect paths. These distances are not story distance, social friendship or proof of an absent relationship.',
                'The distance >=4 cases were selected after examining the ranked census and are illustrative, not a random validation set. Three inspected cases do not estimate semantic accuracy or generalize beyond this snapshot.',
                'The nearest-neighbor versus all-alternatives contrast is descriptive. Text and links can share franchise causes, article length and editing conventions; no causal effect or independent significance test is claimed.'],
            'attribution': 'Frozen course archive of Wikipedia articles, snapshot 26 August 2026. Every evidence record links its contributing article and retains exact frozen-text offsets. Wikipedia prose is available under Creative Commons Attribution-ShareAlike; consult article histories for contributors.'}


def render_figure(data):
    """One comparison, with explicit denominators and disconnected category."""
    width, height = 1040, 680
    x0, chart_width, top = 240, 650, 180
    scale = chart_width / .70
    nearest_color, baseline_color = '#c84527', '#2849c7'
    result = data['result']
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           '<title id="title">Most lexical neighbors are one hyperlink away, with exceptions</title>',
           f'<desc id="desc">{escape(data["figure"]["description"])} {result["nearest_linked"]} of {result["documents"]} lexical-neighbor choices are one link apart, compared with {100*result["baseline_linked_fraction"]:.2f}% of all eligible choices.</desc>',
           '<rect width="1040" height="680" fill="#faf7f0"/>',
           '<g font-family="Arial, sans-serif" fill="#18243a">',
           '<text x="52" y="49" font-size="29" font-weight="700">Close words usually mean a short route.</text>',
           '<text x="52" y="80" font-size="16">Frozen Marvel pages: title-masked TF-IDF cosine and undirected hyperlink distance.</text>',
           f'<rect x="52" y="107" width="13" height="13" fill="{nearest_color}"/><text x="75" y="119" font-size="14">Highest-cosine neighbor: {result["documents"]:,} source choices</text>',
           f'<rect x="475" y="107" width="13" height="13" fill="{baseline_color}"/><text x="498" y="119" font-size="14">All alternatives: {result["eligible_ordered_choices"]:,} ordered choices</text>']
    for tick in range(0, 71, 10):
        x = x0 + scale * tick / 100
        svg += [f'<path d="M {x:.2f} 157 V 583" stroke="#daddda"/>',
                f'<text x="{x:.2f}" y="605" text-anchor="middle" font-size="12">{tick}%</text>']
    for index, row in enumerate(data['comparison']):
        y = top + index * 82
        svg.append(f'<text x="222" y="{y+17}" text-anchor="end" font-size="16" font-weight="700">{escape(row["label"])}</text>')
        for offset, prefix, color in [(0, 'nearest', nearest_color), (28, 'baseline', baseline_color)]:
            fraction, count = row[f'{prefix}_fraction'], row[f'{prefix}_count']
            length = scale * fraction
            denominator = result['documents'] if prefix == 'nearest' else result['eligible_ordered_choices']
            title = f'{row["label"]}: {count:,} / {denominator:,} ({100*fraction:.2f}%)'
            svg += [f'<rect x="{x0}" y="{y+offset}" width="{length:.3f}" height="20" rx="2" fill="{color}"><title>{escape(title)}</title></rect>',
                    f'<text x="{x0+length+9:.2f}" y="{y+offset+15}" font-size="12">{100*fraction:.1f}% ({count:,})</text>']
    svg += ['<text x="52" y="642" font-size="13">Reciprocal choices count twice. No-path pairs stay disconnected; they are excluded from 4+ links.</text>',
            '<text x="52" y="664" font-size="12">Lexical similarity is not semantic accuracy. Frozen course corpus and roster, 26 Aug 2026; full method and text evidence in the post.</text>',
            '</g></svg>']
    return '\n'.join(svg) + '\n'


def render_mobile_figure(data):
    """Reflow the same ten measured bars so phone labels stay readable."""
    result = data['result']
    scale, x0 = 220 / .70, 18
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="360" height="790" viewBox="0 0 360 790" role="img" aria-labelledby="title desc">',
           '<title id="title">Most lexical neighbors are one hyperlink away, with exceptions</title>',
           f'<desc id="desc">{escape(data["figure"]["description"])}</desc>',
           '<rect width="360" height="790" fill="#faf7f0"/>',
           '<g font-family="Arial, sans-serif" fill="#18243a">',
           '<text x="18" y="33" font-size="23" font-weight="700">Close words usually mean</text>',
           '<text x="18" y="60" font-size="23" font-weight="700">a short route.</text>',
           '<text x="18" y="86" font-size="13">Title-masked TF-IDF cosine;</text>',
           '<text x="18" y="105" font-size="13">undirected routes in the frozen Marvel roster.</text>',
           f'<rect x="18" y="126" width="12" height="12" fill="#c84527"/><text x="39" y="137" font-size="14">Closest text: {result["documents"]:,} choices</text>',
           f'<rect x="18" y="151" width="12" height="12" fill="#2849c7"/><text x="39" y="162" font-size="14">All alternatives: {result["eligible_ordered_choices"]:,} choices</text>']
    for index, row in enumerate(data['comparison']):
        y = 195 + index * 99
        svg.append(f'<text x="18" y="{y}" font-size="16" font-weight="700">{escape(row["label"])}</text>')
        for offset, prefix, color in [(13, 'nearest', '#c84527'), (40, 'baseline', '#2849c7')]:
            fraction, count = row[f'{prefix}_fraction'], row[f'{prefix}_count']
            length = scale * fraction
            denominator = result['documents'] if prefix == 'nearest' else result['eligible_ordered_choices']
            label = f'{row["label"]}: {count:,} / {denominator:,} ({100*fraction:.2f}%)'
            svg += [f'<rect x="{x0}" y="{y+offset}" width="{length:.3f}" height="18" fill="{color}"><title>{escape(label)}</title></rect>',
                    f'<text x="{x0+length+8:.2f}" y="{y+offset+14}" font-size="13">{100*fraction:.1f}% ({count:,})</text>']
    svg.append('<path d="M18 666H238" stroke="#64645b"/>')
    for tick in (0, 20, 40, 60):
        x = x0 + scale * tick / 100
        svg.append(f'<text x="{x:.2f}" y="689" font-size="13">{tick}%</text>')
    svg += ['<text x="18" y="714" font-size="13">Share of choices · same scale for both bars</text>',
            '<text x="18" y="741" font-size="12">Reciprocal nearest choices count twice.</text>',
            '<text x="18" y="759" font-size="12">No-path pairs are excluded from 4+ links.</text>',
            '<text x="18" y="777" font-size="12">Lexical resemblance is not semantic accuracy.</text>',
            '</g></svg>']
    return '\n'.join(svg) + '\n'


def main():
    nodes_path, edges_path = ROOT/'data/raw/week1_nodes.tsv', ROOT/'data/raw/week1_edges.tsv'
    archive = ROOT/'data/raw/marvel_pages.zip'
    nodes, edges = load_graph(nodes_path, edges_path)
    data = analyze_week7(nodes, edges, load_corpus(archive, nodes), archive,
                         nodes_path, edges_path)
    target = ROOT/'assets/data'
    target.mkdir(parents=True, exist_ok=True)
    (target/'week7.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (target/'week7.js').write_text('window.WEEK7_DATA = '+json.dumps(data, ensure_ascii=False, separators=(',', ':'))+';\n', encoding='utf-8')
    figure = ROOT/data['figure']['path']
    figure.parent.mkdir(parents=True, exist_ok=True)
    figure.write_text(render_figure(data), encoding='utf-8')
    (ROOT/data['figure']['mobile_path']).write_text(render_mobile_figure(data), encoding='utf-8')
    print(json.dumps(data['result'], indent=2))


if __name__ == '__main__':
    main()
