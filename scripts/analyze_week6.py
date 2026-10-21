#!/usr/bin/env python3
"""Week 6: audit the sensitivity of Marvel TF-IDF neighbors to title words.

Run ``python scripts/analyze_week6.py`` from the repository root. Only the
standard library and the committed frozen corpus are needed.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import statistics
import sys
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import load_graph
from analyze_week5 import load_corpus, tokenize

ROOT = Path(__file__).resolve().parents[1]
TITLE_FUNCTION_WORDS = frozenset(('and', 'of', 'the', 'for', 'in'))


def normalized_tokens(text):
    """Week 5 Unicode letter tokens, with terminal possessive 's removed."""
    return [word[:-2] if word.endswith("'s") else word for word in tokenize(text)]


def title_tokens(node):
    """Use canonical Wikipedia identifiers, excluding parenthetical qualifiers."""
    title = re.sub(r'\([^)]*\)', '', unquote(node).replace('_', ' '))
    return {word for word in normalized_tokens(title)
            if len(word) >= 2 and word not in TITLE_FUNCTION_WORDS}


def build_title_mask(nodes):
    return set().union(*(title_tokens(node) for node in nodes))


def fit_tfidf(counts):
    """Raw TF * natural log(N / df), then unit L2 length for cosine.

    Dividing TF by document length first gives identical vectors after L2
    normalization: that whole-document scalar cancels. There is no stoplist
    or smoothing. An empty/zero-weight document receives an empty vector,
    whose cosine is defined as zero. DF is refitted on input.
    """
    frequency = Counter(word for bag in counts.values() for word, n in bag.items() if n > 0)
    count = len(counts)
    idf = {word: math.log(count / frequency[word]) for word in sorted(frequency)}
    vectors = {}
    for node, bag in sorted(counts.items()):
        vector = {word: n * idf[word] for word, n in sorted(bag.items()) if n > 0 and idf[word] > 0}
        norm = math.sqrt(math.fsum(value * value for value in vector.values()))
        vectors[node] = {word: value / norm for word, value in vector.items()} if norm else {}
    return vectors, idf


def cosine(left, right):
    """Dot product of the L2-normalized vectors returned by fit_tfidf."""
    if len(left) > len(right):
        left, right = right, left
    return math.fsum(value * right.get(word, 0) for word, value in left.items())


def pair_scores(vectors):
    scores = {node: {} for node in vectors}
    ordered = sorted(vectors)
    for i, source in enumerate(ordered):
        for target in ordered[i + 1:]:
            value = cosine(vectors[source], vectors[target])
            scores[source][target] = value
            scores[target][source] = value
    return scores


def top_terms(source, target, vectors, limit=10):
    left, right = vectors[source], vectors[target]
    total = cosine(left, right)
    products = [(value * right[word], word) for word, value in left.items() if word in right]
    return [{'term': word, 'contribution': round(value, 9),
             'share': round(value / total, 9) if total else 0}
            for value, word in sorted(products, key=lambda item: (-item[0], item[1]))[:limit]]


def display_name(node, nodes):
    return re.sub(r'\s*\([^)]*\)', '', nodes[node]['name']).strip()


def nearest_record(source, scores, vectors, nodes, edges):
    target = min(scores[source], key=lambda node: (-scores[source][node], node))
    return {'neighbor': target, 'name': display_name(target, nodes),
            'url': nodes[target]['url'], 'similarity': round(scores[source][target], 9),
            'linked': (source, target) in edges or (target, source) in edges,
            'terms': top_terms(source, target, vectors)}


def source_excerpt(texts, nodes, node, needle, context=110):
    """Exact literal match plus context; offsets index decoded frozen text."""
    start = texts[node].index(needle)
    end = start + len(needle)
    return {'node': node, 'name': display_name(node, nodes), 'url': nodes[node]['url'],
            'start': start, 'end': end, 'text': texts[node][start:end],
            'before': texts[node][max(0, start-context):start],
            'after': texts[node][end:end+context]}


def case_record(identifier, title, source, target, interpretation, needles,
                before_scores, after_scores, before_vectors, after_vectors,
                texts, nodes, edges):
    def rank(scores):
        return sorted(scores[source], key=lambda node: (-scores[source][node], node)).index(target) + 1
    return {'id': identifier, 'title': title, 'source': source, 'target': target,
            'source_name': display_name(source, nodes), 'target_name': display_name(target, nodes),
            'before': round(before_scores[source][target], 9),
            'after': round(after_scores[source][target], 9),
            'rank_before': rank(before_scores), 'rank_after': rank(after_scores),
            'nearest_before': nearest_record(source, before_scores, before_vectors, nodes, edges),
            'nearest_after': nearest_record(source, after_scores, after_vectors, nodes, edges),
            'terms_before': top_terms(source, target, before_vectors),
            'terms_after': top_terms(source, target, after_vectors),
            'linked': (source, target) in edges or (target, source) in edges,
            'interpretation': interpretation,
            'sources': [source_excerpt(texts, nodes, node, needle) for node, needle in needles]}


def audited_cases(before_scores, after_scores, before_vectors, after_vectors, texts, nodes, edges):
    """Five deliberately inspected cases; no claim of representative sampling.

    Literal excerpts fail loudly if the frozen evidence changes. The whole
    corpus result is independent of case selection. Small synthetic fixtures
    intentionally have no manually interpreted cases.
    """
    specs = [
        ('storm', 'One word supplied 87% of the match.',
         'Storm_(Marvel_Comics)', 'Human_Torch',
         'The shared token storm is 86.9% of this pair\'s original cosine: Ororo Munroe\'s superhero name collides with Johnny Storm\'s surname. After removal, Storm chooses Jean Grey. Their pages both identify X-Men membership; retained x/men supply 46.2% of that new cosine. That is a defensible franchise connection, not proof of identical powers.',
         [('Storm_(Marvel_Comics)', 'Born Ororo Munroe to a tribal princess of Kenya'),
          ('Human_Torch', 'The Human Torch (Jonathan Lowell Spencer "Johnny" Storm)'),
          ('Storm_(Marvel_Comics)', 'Storm is a member of the X-Men, a group of mutant heroes'),
          ('Jean_Grey', 'usually those featuring the X-Men, a group of superheroes of which she is a founding member')]),
        ('frost', 'A surname made two different powers look alike.',
         'Emma_Frost', 'Jack_Frost_(Marvel_Comics)',
         'Frost supplied 96.0% of the original cosine. The passages describe Emma\'s telepathy and diamond form versus Jack\'s ice and cold. Emma\'s replacement neighbor is Jean Grey, whose page explicitly describes telepathy; retained telepathy/telepathic/psychic contribute to their new match alongside X-Men language. The old match was not evidence that their abilities were alike.',
         [('Emma_Frost', 'Her mutation grants her high-level telepathic abilities and the power to turn into organic diamond.'),
          ('Jack_Frost_(Marvel_Comics)', 'Jack Frost resembles a young man made of ice, and can create and withstand extremely cold temperatures and generate large amounts of ice.'),
          ('Jean_Grey', 'Initially capable of using only telekinesis, she later develops the power of telepathy.')]),
        ('symbiote', 'A story connection survives the mask.',
         'Venom_(character)', 'Eddie_Brock',
         'Venom and Eddie Brock remain mutual nearest neighbors after venom, eddie, brock and spider are removed. Symbiote now supplies 61.8% of their cosine. The source describes a host-bonding alien and explicitly says the bond makes Eddie become Venom: this is a direct narrative connection. Writer names and other aliases also survive, so the score is not a pure measure of plot.',
         [('Venom_(character)', 'The character is a sentient alien symbiote with an amorphous, liquid-like form, who survives by bonding with a host'),
          ('Eddie_Brock', 'The symbiote bonds with him and they become Venom')]),
        ('alias', 'A stronger surviving match still contains a name.',
         'Black_Panther_(character)', 'Shuri_(character)',
         'Black Panther and Shuri remain mutual nearest neighbors, with a larger cosine after removal. Yet t\'challa supplies 59.9% of that new cosine: a civilian identity absent from the canonical article titles escaped our mask. Their pages confirm the sibling and Wakandan connection, but this is also a concrete failure of title words as complete name detection. A higher post-removal score does not prove the result is name-free.',
         [('Black_Panther_(character)', "Born T'Challa, son of the previous Black Panther T'Chaka, he is the king and protector of the fictional African nation of Wakanda"),
          ('Shuri_(character)', "She is the daughter of T'Chaka and younger sister of T'Challa")]),
        ('bibliography', 'The replacement can be another trap.',
         'Solomon_Kane_(comics)', 'Luke_Cage',
         'Solomon Kane initially chooses Garrison Kane; kane supplies 98.9% of that match. After title removal it chooses Luke Cage at only 0.094 cosine. ISBN alone supplies 34.5% of this replacement score, followed by Duffy and issue. Inspection places these words in collected editions, bibliography and publication history. Shared creator and publishing metadata is real, but these passages do not establish a fictional relationship. Removing a surname did not guarantee a story-based replacement.',
         [('Solomon_Kane_(comics)', 'was published in July 2009 (ISBN 1595822828).'),
          ('Solomon_Kane_(comics)', 'by Thomas, Glut, Doug Moench, Jo Duffy and John Arcudi'),
          ('Luke_Cage', 'Marvel Comics in the 1970s: The World inside Your Head. Cornell University Press. ISBN 978-1-5017-6783-8.'),
          ('Luke_Cage', 'Jo Duffy, a fan of both characters, was appointed as its writer at her request beginning with issue #56.')]),
    ]
    required = {node for spec in specs for node, _ in spec[-1]} | {spec[2] for spec in specs} | {spec[3] for spec in specs}
    if not required <= nodes.keys():
        return []
    return [case_record(*spec, before_scores, after_scores, before_vectors, after_vectors,
                        texts, nodes, edges) for spec in specs]


def analyze_week6(nodes, edges, texts, archive_path=None):
    if set(nodes) != set(texts):
        raise ValueError('Corpus must match the complete frozen roster.')
    mask = build_title_mask(nodes)
    counts = {node: Counter(normalized_tokens(text)) for node, text in sorted(texts.items())}
    stripped = {node: Counter({word: n for word, n in bag.items() if word not in mask})
                for node, bag in counts.items()}
    before_vectors, before_idf = fit_tfidf(counts)
    after_vectors, after_idf = fit_tfidf(stripped)
    assert all(before_idf[word] == value for word, value in after_idf.items())
    before_scores, after_scores = pair_scores(before_vectors), pair_scores(after_vectors)
    edge_set = set(edges)
    rows = []
    for source in sorted(nodes):
        before = nearest_record(source, before_scores, before_vectors, nodes, edge_set)
        after = nearest_record(source, after_scores, after_vectors, nodes, edge_set)
        count = sum(counts[source].values())
        removed = count - sum(stripped[source].values())
        rows.append({'node': source, 'name': display_name(source, nodes), 'url': nodes[source]['url'],
                     'before': before, 'after': after, 'changed': before['neighbor'] != after['neighbor'],
                     'original_pair_after_similarity': round(after_scores[source][before['neighbor']], 9),
                     'removed_tokens': removed, 'token_count': count,
                     'removed_token_fraction': round(removed/count, 9)})
    changed = sum(row['changed'] for row in rows)
    result = {'changed': changed, 'unchanged': len(rows)-changed,
              'changed_fraction': changed / len(rows),
              'removed_tokens': sum(row['removed_tokens'] for row in rows),
              'removed_token_fraction': sum(row['removed_tokens'] for row in rows) / sum(row['token_count'] for row in rows),
              'median_original_pair_before': statistics.median(row['before']['similarity'] for row in rows),
              'median_original_pair_after': statistics.median(row['original_pair_after_similarity'] for row in rows),
              'linked_before': sum(row['before']['linked'] for row in rows),
              'linked_after': sum(row['after']['linked'] for row in rows),
              'possible_pairs': len(nodes)*(len(nodes)-1)//2,
              'zero_vectors_before': sum(not vector for vector in before_vectors.values()),
              'zero_vectors_after': sum(not vector for vector in after_vectors.values())}
    cases = audited_cases(before_scores, after_scores, before_vectors, after_vectors,
                          texts, nodes, edge_set)
    return {'schema_version': 1,
            'question': 'Names or meaning? How much do character-title words change Marvel textual lookalikes?',
            'title': 'The name trap, measured.',
            'corpus': {'documents': len(nodes), 'tokens': sum(row['token_count'] for row in rows),
                       'types': len(before_idf), 'snapshot_date': '2026-08-26',
                       'source_url': 'https://sunelehmann.com/socialgraphs2026-web/data/marvel_pages.zip',
                       'archive': 'data/raw/marvel_pages.zip',
                       'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest() if archive_path else None},
            'method': {'representation': 'Raw term frequency times natural log(N/df), followed by L2 normalization and cosine similarity. No stopword list, stemming, smoothing or topic model.',
                       'tokenization': "Reuse the Week 5 Unicode letter tokenizer, case-fold, normalize apostrophes, and remove a final possessive 's in BOTH conditions. Hyphens split words; numerals are excluded.",
                       'ablation': 'Build one global mask from canonical Wikipedia node IDs: decode URL escapes, replace underscores with spaces, remove all parenthetical qualifiers, tokenize, and retain tokens with at least two letters except the five title function words and/of/the/for/in. Remove every occurrence of every masked word from every article; recompute TF-IDF and cosine.',
                       'title_function_words': sorted(TITLE_FUNCTION_WORDS),
                       'ties': 'Highest full-precision cosine wins; equal scores choose the lexicographically first canonical node ID. Each article chooses one other article; this is 303 directed choices, not 303 distinct pairs.',
                       'df_refit': 'Document frequencies are recomputed after ablation. Since whole word types are globally removed and all articles remain, retained terms have exactly the same DF and IDF in both conditions; only vocabulary and vector normalization change.',
                       'links': 'Linked means at least one directed Wikipedia hyperlink between the two roster nodes in the frozen Week 1 network. Link status is auxiliary metadata, not a semantic ground-truth label.',
                       'zero_idf_terms': sorted(word for word, value in before_idf.items() if value == 0),
                       'masked_types': len(mask), 'masked_types_in_corpus': len(mask & before_idf.keys()),
                       'retained_types': len(after_idf)},
            'result': result, 'rows': rows, 'cases': cases, 'title_mask': sorted(mask),
            'figure': {'path': 'assets/figures/week6-name-audit.svg',
                       'description': 'One point per article: cosine with its ORIGINAL nearest neighbor before and after global title-word removal. The pair is held fixed on both axes. Color records whether this original neighbor remains the nearest among all 302 alternatives. Points below the diagonal became less similar; the chart measures sensitivity, not accuracy.'},
            'limitation': 'This is an intentionally coarse title-word sensitivity check, not a named-entity recognizer. Titles contain meaningful words such as storm, iron and black; removing them can erase real subject matter. Conversely, civilian aliases absent from titles survive. Nearest-neighbor changes do not prove improved meaning, and retained matches can still reflect publication lists, quoted names or editorial formulas.',
            'attribution': 'Frozen course archive of Wikipedia articles. Source records link each contributing article and preserve exact character offsets into decoded frozen text. Wikipedia prose is available under Creative Commons Attribution-ShareAlike; consult linked article histories for contributors.'}


def render_figure(data):
    width, height = 1000, 680
    left, top, size = 95, 150, 445
    changed, retained = '#c84527', '#2849c7'
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           '<title id="title">Does removing title words change Marvel textual lookalikes?</title>',
           f'<desc id="desc">{escape(data["figure"]["description"])} {data["result"]["changed"]} of {len(data["rows"])} articles choose a different nearest neighbor after removal.</desc>',
           '<rect width="1000" height="680" fill="#faf7f0"/>',
           '<g font-family="Arial, sans-serif" fill="#18243a">',
           '<text x="55" y="48" font-size="27" font-weight="700">The name trap, measured.</text>',
           '<text x="55" y="79" font-size="16">Hold each article’s original nearest-neighbor pair fixed; remove title words globally.</text>',
           '<text x="55" y="104" font-size="14">TF-IDF cosine · 303 frozen articles · no stopword list · title-word sensitivity, not semantic accuracy</text>']
    def point(x, y):
        return left + size*x, top + size*(1-y)
    for value in (0, .2, .4, .6, .8, 1):
        x, y = point(value, value)
        svg += [f'<path d="M {x} {top} V {top+size} M {left} {y} H {left+size}" stroke="#dcdedb" stroke-width="1"/>',
                f'<text x="{x}" y="{top+size+25}" text-anchor="middle" font-size="13">{value:.1f}</text>',
                f'<text x="{left-15}" y="{y+5}" text-anchor="end" font-size="13">{value:.1f}</text>']
    svg += [f'<path d="M {left} {top+size} L {left+size} {top}" stroke="#738092" stroke-dasharray="6 5"/>']
    for row in sorted(data['rows'], key=lambda row: row['changed']):
        x, y = point(row['before']['similarity'], row['original_pair_after_similarity'])
        label = f'{row["name"]} / {row["before"]["name"]}: {row["before"]["similarity"]:.3f} → {row["original_pair_after_similarity"]:.3f}; nearest neighbor {"changed" if row["changed"] else "retained"}'
        svg.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="{changed if row["changed"] else retained}" fill-opacity=".58"><title>{escape(label)}</title></circle>')
    svg += [f'<text x="{left+size/2}" y="{top+size+60}" text-anchor="middle" font-size="15">Original pair cosine, before removal</text>',
            f'<text transform="translate(30 {top+size/2}) rotate(-90)" text-anchor="middle" font-size="15">Same pair cosine, after removal</text>',
            f'<text x="610" y="185" font-size="63" font-weight="700" fill="{changed}">{data["result"]["changed"]} / {len(data["rows"])}</text>',
            '<text x="612" y="217" font-size="21">articles change their</text>',
            '<text x="612" y="244" font-size="21">nearest neighbor.</text>',
            f'<circle cx="620" cy="286" r="6" fill="{changed}"/><text x="638" y="291" font-size="15">Original neighbor replaced</text>',
            f'<circle cx="620" cy="317" r="6" fill="{retained}"/><text x="638" y="322" font-size="15">Original neighbor retained</text>',
            '<text x="612" y="371" font-size="15">Below the dashed line:</text>',
            '<text x="612" y="394" font-size="15">the original pair loses similarity.</text>',
            f'<text x="612" y="439" font-size="15">Removed {data["method"]["masked_types_in_corpus"]} observed word types</text>',
            f'<text x="612" y="462" font-size="15">({100*data["result"]["removed_token_fraction"]:.1f}% of all token occurrences).</text>',
            '<text x="612" y="509" font-size="14">Words such as storm and iron</text>',
            '<text x="612" y="531" font-size="14">carry names AND story meaning.</text>',
            '<text x="612" y="553" font-size="14">Change alone is not improvement.</text>',
            '<text x="55" y="672" font-size="11">Course Marvel corpus · snapshot 26 Aug 2026 · source archive and exact method linked in the post</text>',
            '</g></svg>']
    return '\n'.join(svg) + '\n'


def main():
    nodes, edges = load_graph(ROOT/'data/raw/week1_nodes.tsv', ROOT/'data/raw/week1_edges.tsv')
    archive = ROOT/'data/raw/marvel_pages.zip'
    data = analyze_week6(nodes, edges, load_corpus(archive, nodes), archive)
    target = ROOT/'assets/data'
    target.mkdir(parents=True, exist_ok=True)
    (target/'week6.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (target/'week6.js').write_text('window.WEEK6_DATA = '+json.dumps(data, ensure_ascii=False, separators=(',', ':'))+';\n', encoding='utf-8')
    figure = ROOT/data['figure']['path']
    figure.parent.mkdir(parents=True, exist_ok=True)
    figure.write_text(render_figure(data), encoding='utf-8')
    print(json.dumps(data['result'], indent=2))


if __name__ == '__main__':
    main()
