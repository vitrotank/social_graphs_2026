#!/usr/bin/env python3
"""Week 5: exact shared phrases in the frozen Marvel article corpus.

Standard-library analysis. Run from the repository root:
    python scripts/analyze_week5.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
from urllib.parse import unquote
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import load_graph, adjacency

ROOT = Path(__file__).resolve().parents[1]
WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
NUMBER_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def tokenize(text):
    """Case-folded Unicode letter words, retaining internal apostrophes."""
    return [m.group().casefold().replace('’', "'") for m in WORD.finditer(text)]


def load_corpus(path, nodes):
    texts = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith('/') or Path(name).name == 'README.txt':
                continue
            if not name.endswith('.txt'):
                raise ValueError(f'Unexpected archive member: {name}')
            node = unquote(Path(name).stem)
            if node in texts:
                raise ValueError(f'Duplicate article: {node}')
            texts[node] = archive.read(name).decode('utf-8-sig')
    if set(texts) != set(nodes):
        raise ValueError(f'Corpus/roster mismatch: missing {set(nodes)-set(texts)}, extra {set(texts)-set(nodes)}')
    return texts


def paragraph_tokens(text, pattern=WORD):
    """A phrase may span sentences, but never a blank-line paragraph boundary."""
    rows = []
    for match in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)', text):
        para = match.group()
        words = list(pattern.finditer(para))
        if words:
            rows.append({'text': para, 'start': match.start(),
                         'tokens': tuple(m.group().casefold().replace('’', "'") for m in words),
                         'spans': [(m.start(), m.end()) for m in words]})
    return rows


def shared_runs(texts, minimum=8, pattern=WORD):
    """Find every pair's longest common contiguous token run, exactly.

    An inverted index of minimum-word seeds finds every eligible run. Seeds
    with a matching predecessor are skipped, then the maximal run is extended.
    No stopwords, names, stemming or article text are removed.
    """
    documents = {node: paragraph_tokens(text, pattern) for node, text in sorted(texts.items())}
    index = defaultdict(list)
    for node, paragraphs in documents.items():
        for paragraph, row in enumerate(paragraphs):
            tokens = row['tokens']
            for position in range(len(tokens) - minimum + 1):
                index[tokens[position:position + minimum]].append((node, paragraph, position))
    pairs = {}
    for gram, occurrences in index.items():
        if len({x[0] for x in occurrences}) < 2:
            continue
        for i, left in enumerate(occurrences):
            a, ap, ai = left
            at = documents[a][ap]['tokens']
            for b, bp, bi in occurrences[i + 1:]:
                if a == b:
                    continue
                bt = documents[b][bp]['tokens']
                if ai and bi and at[ai - 1] == bt[bi - 1]:
                    continue
                length = minimum
                while ai + length < len(at) and bi + length < len(bt) and at[ai + length] == bt[bi + length]:
                    length += 1
                key = (a, b)
                candidate = (length, ap, ai, bp, bi)
                previous = pairs.get(key)
                # First source position wins a tie, deterministically.
                if previous is None or length > previous[0] or (length == previous[0] and candidate[1:] < previous[1:]):
                    pairs[key] = candidate
    return documents, pairs


def passage(documents, node, paragraph, position, length):
    row = documents[node][paragraph]
    start, end = row['spans'][position][0], row['spans'][position + length - 1][1]
    return {'text': row['text'][start:end], 'paragraph': paragraph + 1,
            'start': row['start'] + start, 'end': row['start'] + end,
            'before': row['text'][max(0, start - 110):start],
            'after': row['text'][end:end + 110]}


STOPWORDS = set('a an the and or but if as at by for from in into of on out over to up with is are was were be been being has have had do does did not no it its this that these those he she they them their his her we us our who whom which what when where while than then also can could would should may might will one two all some such each other more most'.split())


def ranks(values):
    """Average ranks, including ties; used for Spearman's correlation."""
    result = {}
    ordered = sorted(values, key=lambda key: (values[key], key))
    i = 0
    while i < len(ordered):
        end = i + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[i]]:
            end += 1
        for key in ordered[i:end]:
            result[key] = (i + 1 + end) / 2
        i = end
    return result


def correlation(a, b):
    am, bm = statistics.mean(a.values()), statistics.mean(b.values())
    numerator = sum((a[k] - am) * (b[k] - bm) for k in a)
    denominator = math.sqrt(sum((x - am)**2 for x in a.values()) * sum((x - bm)**2 for x in b.values()))
    return numerator / denominator if denominator else 0.0


def candidates(texts, nodes, edges):
    _, _, neighbors = adjacency(nodes, edges)
    sizes = {n: len(tokenize(text)) for n, text in texts.items()}
    degree = {n: len(neighbors[n]) for n in nodes}
    bags = {n: Counter(t for t in tokenize(text) if t not in STOPWORDS) for n,text in texts.items()}
    norms = {n: math.sqrt(sum(x*x for x in bag.values())) for n,bag in bags.items()}
    similarities = []
    node_ids = sorted(nodes)
    for i, a in enumerate(node_ids):
        for b in node_ids[i+1:]:
            small, large = (bags[a], bags[b]) if len(bags[a]) < len(bags[b]) else (bags[b], bags[a])
            similarity = sum(value * large.get(term, 0) for term,value in small.items()) / (norms[a] * norms[b])
            similarities.append((similarity,a,b))
    return [
        {'id': 'length', 'question': 'Do more connected characters receive longer articles?',
         'method': 'Token count versus undirected distinct-neighbor degree; Spearman rank correlation with average tie ranks.',
         'spearman': correlation(ranks(sizes), ranks(degree)),
         'choice': 'Interesting association, but article length alone cannot distinguish editorial attention from fictional importance.'},
        {'id': 'cosine', 'question': 'Which pages sound most alike as bags of words?',
         'method': f'Cosine similarity of raw case-folded token frequency vectors after the explicitly listed {len(STOPWORDS)}-word function-word stoplist. No TF-IDF or stemming.',
         'stopwords': sorted(STOPWORDS),
         'stopword_count': len(STOPWORDS),
         'top_pairs': [{'similarity': round(sim,6), 'source':a,'target':b} for sim,a,b in sorted(similarities, reverse=True)[:5]],
         'choice': 'The highest-scoring pairs concern related names or identities. Cosine loses the location and order that explain whether similarity is story or formula.'},
        {'id': 'phrases', 'question': 'When Marvel pages share words, are they sharing stories?',
         'method': 'Exact consecutive normalized token runs, minimum 8 words; longest run for every distinct article pair.',
         'choice': 'Selected: the enormous short-phrase overlap and tiny long-passage set can be explained directly with traceable text evidence.'}
    ]


SECTIONS = set('Publication history|Fictional character biography|Powers and abilities|Other versions|In other media|Television|Film|Video games|Collected editions|Bibliography|Further reading|External links|Reception|Critical reception|Accolades|Literary reception|Spider-Man: Life Story|Old Man Logan|Marvel Comics|MC2|Marvel Zombies|References'.split('|'))


def section_of(documents, node, paragraph):
    """Nearest recognized printed section label; no inference from the link graph."""
    section = 'Lead'
    for row in documents[node][:paragraph+1]:
        for line in row['text'].splitlines():
            if line.strip() in SECTIONS:
                section = line.strip()
    return section


def classified_pair(a, b, value):
    """Audited labels of the longest >=20-word match, not corpus-wide topics.

    These labels describe the passage, not fictional relationships or authorship.
    The rules enumerate all non-lead matches in the current frozen snapshot.
    """
    key = frozenset((a,b))
    _, ap, _, bp, _ = value
    if ap == 0 and bp == 0:
        if key == frozenset(('Rocket_Raccoon','Star-Lord')):
            return 'Screen adaptations', 'Both leads enumerate the same cinematic appearances.'
        return 'Editorial formula', 'Similar introductory prose names publishers, creators, teams or media appearances.'
    groups = {
        'Bibliography / links': [('Spitfire_(character)','Union_Jack_(Joseph_Chapman)'), ('Union_Jack_(Joseph_Chapman)','Union_Jack_(Marvel_Comics)'), ('Spitfire_(character)','Union_Jack_(Marvel_Comics)'), ('Cyclops_(Marvel_Comics)','Storm_(Marvel_Comics)'), ('Cyclops_(Marvel_Comics)','Shang-Chi'), ('Gorgon_(Inhuman)','Karnak_(character)')],
        'Powers / equipment': [('Bucky_(Marvel_Comics)','Rikki_Barnes'), ('Bucky_(Marvel_Comics)','Jack_Monroe_(character)'), ('Battlestar_(character)','U.S._Agent')],
        'Reception': [('Genis-Vell','Phyla-Vell'), ('Cable_(character)','Rachel_Summers'), ('Black_Panther_(character)','Storm_(Marvel_Comics)')],
        'Screen adaptations': [('Abomination_(character)','Fin_Fang_Foom'), ('Fin_Fang_Foom','Radioactive_Man_(comics)')],
        'Identity summaries': [('Captain_Marvel_(Marvel_Comics)','Genis-Vell'), ('Captain_Marvel_(Marvel_Comics)','Phyla-Vell')],
        'Publication history': [('Spider-Woman','Spider-Woman_(Jessica_Drew)'), ('Cyclops_(Marvel_Comics)','Jean_Grey'), ('Blue_Diamond_(character)','Jack_Frost_(Marvel_Comics)'), ('Eddie_Brock','Venom_(character)'), ("Ch'od",'Raza_Longknife'), ('Mayday_Parker','Spider-Girl'), ('Black_Rider_(character)','Two-Gun_Kid'), ('Living_Lightning','Red_Wolf_(comics)'), ('Alex_Wilder','Chase_Stein'), ('Makkari_(character)','Thena'), ('Misty_Knight','Storm_(Marvel_Comics)')],
        'Shared story': [('Mayday_Parker','Spider-Woman'), ('Spider-Girl','Spider-Woman'), ('Ghost_Rider','Ghost_Rider_(Johnny_Blaze)'), ('Mockingbird_(Marvel_Comics)','Quicksilver_(Marvel_Comics)'), ('Rachel_Summers','Storm_(Marvel_Comics)'), ('Rachel_Summers','Wild_Child_(character)'), ('Storm_(Marvel_Comics)','Wild_Child_(character)'), ('Black_Cat_(Marvel_Comics)','Spider-Girl'), ('Spider-UK','Spider-Woman_(Gwen_Stacy)'), ('Power_Man_(Victor_Alvarez)','She-Hulk_(Lyra)'), ('Iron_Fist_(character)','Jessica_Jones'), ('Storm_(Marvel_Comics)','Wolverine_(character)'), ('White_Tiger_(Heroes_for_Hire)','White_Tiger_(comics)')]
    }
    for category, pairs in groups.items():
        if key in [frozenset(pair) for pair in pairs]:
            return category, 'Label assigned by inspecting the longest matched passage and its surrounding article section.'
    raise ValueError(f'Unreviewed long match: {a} / {b}')


def source_record(documents, nodes, node, paragraph, position, length):
    row = passage(documents,node,paragraph,position,length)
    row.update({'node':node, 'name':re.sub(r'\s*\([^)]*\)$','',nodes[node]['name']),
                'url':nodes[node]['url'], 'section':section_of(documents,node,paragraph),
                'excerpt':' '.join(row['text'].split()[:24]) + (' …' if len(row['text'].split()) > 24 else ''),
                'normalized_words':length})
    return row


def render_pair(key, value, documents, nodes, edge_set):
    a,b = key
    length,ap,ai,bp,bi = value
    category, note = classified_pair(a,b,value)
    return {'id':f'{a}::{b}', 'source':a, 'target':b, 'length':length,
            'category':category, 'category_note':note,
            'linked': (a,b) in edge_set or (b,a) in edge_set,
            'sources':[source_record(documents,nodes,a,ap,ai,length), source_record(documents,nodes,b,bp,bi,length)]}


def analyze_week5(nodes, edges, texts, archive_path=None):
    documents, all_pairs = shared_runs(texts)
    without_leads = {node:'\n\n'.join(row['text'] for row in paragraphs[1:]) for node, paragraphs in documents.items()}
    _, trimmed_pairs = shared_runs(without_leads)
    _, numeric_pairs = shared_runs(texts,pattern=NUMBER_WORD)
    possible_pairs = len(nodes)*(len(nodes)-1)//2
    thresholds = []
    for length in range(8,61):
        selected = {pair:value for pair,value in all_pairs.items() if value[0] >= length}
        thresholds.append({'length':length, 'pairs':len(selected),
                           'articles':len({node for pair in selected for node in pair}),
                           'percent':100*len(selected)/possible_pairs,
                           'without_lead_pairs':sum(value[0]>=length for value in trimmed_pairs.values()),
                           'with_numerals_pairs':sum(value[0]>=length for value in numeric_pairs.values())})
    common = Counter()
    for paragraphs in documents.values():
        phrases = set()
        for para in paragraphs:
            tokens = para['tokens']
            phrases.update(tokens[i:i+8] for i in range(len(tokens)-7))
        common.update(phrases)
    edge_set = set(edges)
    pairs = [render_pair(key,value,documents,nodes,edge_set) for key,value in sorted(all_pairs.items(),key=lambda row:(-row[1][0],row[0])) if value[0]>=20]
    token_counts = {node:len(tokenize(text)) for node,text in texts.items()}
    vocab = set(term for text in texts.values() for term in tokenize(text))
    phrase = tuple('in american comic books published by marvel comics'.split())
    phrase_docs = common[phrase]
    def contains_standard_phrase(paragraphs):
        return any(para['tokens'][offset:offset+len(phrase)] == phrase
                   for para in paragraphs
                   for offset in range(len(para['tokens'])-len(phrase)+1))
    phrase_lead_docs = sum(contains_standard_phrase(paragraphs[:1]) for paragraphs in documents.values())
    phrase_body_docs = sum(contains_standard_phrase(paragraphs[1:]) for paragraphs in documents.values())
    # Example deliberately picked from an unrelated editorial pair. Its whole
    # longest match is short, so it complements the selected long-match sample.
    short_pair = ('Abomination_(character)','Adam_Warlock')
    value = all_pairs[short_pair]
    n,ap,ai,bp,bi = value
    short_example = {'id':'editorial-voice','length':n,'category':'Editorial formula',
                     'sources':[source_record(documents,nodes,short_pair[0],ap,ai,n), source_record(documents,nodes,short_pair[1],bp,bi,n)]}
    long_example = next(row for row in pairs if row['source']=='Mayday_Parker' and row['target']=='Spider-Woman')
    ref_example = next(row for row in pairs if row['source']=='Spitfire_(character)' and row['target']=='Union_Jack_(Joseph_Chapman)')
    formula_example = next(row for row in pairs if row['source']=='Radian_(Morituri)' and row['target']=='Scaredycat')
    return {
        'schema_version':1,'question':'When Marvel pages share words, are they sharing stories?',
        'title':'An editorial accent. A shared universe.',
        'corpus':{'documents':len(texts),'tokens':sum(token_counts.values()),'types':len(vocab),
                  'snapshot_date':'2026-08-26','download_date':'2026-10-03',
                  'source_url':'https://sunelehmann.com/socialgraphs2026-web/data/marvel_pages.zip',
                  'archive':'data/raw/marvel_pages.zip',
                  'sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest() if archive_path else None,
                  'smallest':{'node':min(token_counts,key=token_counts.get),'tokens':min(token_counts.values())},
                  'largest':{'node':max(token_counts,key=token_counts.get),'tokens':max(token_counts.values())}},
        'result':{'possible_pairs':possible_pairs,'pairs_at_8':thresholds[0]['pairs'],
                  'pairs_at_20':next(row['pairs'] for row in thresholds if row['length']==20),
                  'pairs_at_40':next(row['pairs'] for row in thresholds if row['length']==40),
                  'standard_phrase_documents':phrase_docs,'standard_phrase_pairs':phrase_docs*(phrase_docs-1)//2,
                  'standard_phrase_lead_documents':phrase_lead_docs,'standard_phrase_body_documents':phrase_body_docs,
                  'standard_phrase_fraction_of_8_pairs':phrase_docs*(phrase_docs-1)//2/thresholds[0]['pairs'],
                  'longest_words':long_example['length'],
                  'both_leads_at_20':sum(row['sources'][0]['paragraph']==1 and row['sources'][1]['paragraph']==1 for row in pairs),
                  'linked_at_20':sum(row['linked'] for row in pairs),
                  'takeaway':'Short shared phrases mostly capture Wikipedia\u2019s editorial voice. Longer runs reveal a small mixture of shared stories, publication history and reference material; length alone does not identify their meaning.'},
        'thresholds':thresholds,'pairs':pairs,
        'common_phrases':[{'text':' '.join(gram),'length':8,'documents':count,'pairs':count*(count-1)//2} for gram,count in sorted(common.items(),key=lambda item:(-item[1],item[0]))[:8]],
        'examples':{'editorial':short_example,'story':long_example,'references':ref_example,'counterexample':formula_example},
        'candidates':candidates(texts,nodes,edges),
        'definitions':{
            'unit':'Distinct unordered article pairs. A pair is counted once when its longest common consecutive token run reaches the chosen threshold. All 303 articles remain in the denominator (45,753 pairs).',
            'tokens':'Unicode letter sequences, with internal apostrophes retained; curly apostrophes normalized and text case-folded. Hyphens separate words. Numbers and punctuation are excluded. Stopwords, character names and headings remain; no stemming or TF-IDF.',
            'boundary':'Runs may span sentences and single line breaks, including headings, but may not cross a blank-line paragraph boundary. Exact means identical normalized word sequences, not identical bytes.',
            'ties':'For equal longest runs, choose the earliest paragraph/word position in the alphabetically first article, then the earliest in the second. Pair IDs and output order are deterministic.',
            'exclusions':'README and archive directory entries are excluded. No character articles are dropped. Zip filenames are URL-decoded and must match the frozen Week 1 roster exactly.',
            'lead_check':'Remove only the first blank-line-delimited paragraph of each article, then recompute all runs. This is a sensitivity check, not a perfect semantic extraction of introductions.',
            'numerals_check':'Recompute with letter-or-number tokens, retaining numerals. The threshold pattern persists: 40,581 pairs at 8 tokens, 82 at 20 and 14 at 40.',
            'categories':'A human-readable label was assigned to every longest >=20-word passage after inspecting its text and section. It is a descriptive aid, not an automated topic model. A pair can share several kinds of text; only its longest run is represented.',
            'links':'Linked means at least one directed hyperlink between the two pages in the same frozen Week 1 roster. This is metadata, not an explanation of text reuse.',
            'figure':'The curve is a complete census of this frozen corpus, not an estimate. The vertical count scale is logarithmic and the baseline is 1 pair. Thresholds 8 through 60 are recomputed exactly; connecting lines guide the eye.'},
        'checks':[
            'Validated archive contains exactly the same 303 decoded identifiers as the Week 1 roster.',
            f'The standard eight-word publisher phrase occurs in the first paragraph of {phrase_lead_docs} articles and in later paragraphs of {phrase_body_docs} articles.',
            'Inspected all 71 longest passages of at least 20 words and their surrounding sections before labeling them.',
            'Checked longest result against both frozen source texts using stored character offsets.',
            'Inspected counterexamples: a 34-word Morituri introductory formula survives a long threshold; a 103-word shared bibliography is not fictional narration.',
            'Recomputed every pair after removing the first paragraph and after retaining numerals. Both preserve the steep decline.'
        ],
        'limitation':'A match is a shared normalized word sequence, not proof of plagiarism, copying direction or a fictional relationship. Editorial formulas, quotations and bibliographies can persist at long thresholds. Paraphrases are invisible, short articles have fewer possible runs, and larger articles have more opportunities to overlap.',
        'attribution':'Frozen course corpus of Wikipedia articles; source links identify the contributing pages. Wikipedia prose is available under its linked Creative Commons Attribution-ShareAlike license; consult article history for authors and revisions.'
    }


def main():
    nodes, edges = load_graph(ROOT/'data/raw/week1_nodes.tsv', ROOT/'data/raw/week1_edges.tsv')
    texts = load_corpus(ROOT/'data/raw/marvel_pages.zip', nodes)
    result = analyze_week5(nodes,edges,texts,ROOT/'data/raw/marvel_pages.zip')
    target = ROOT/'assets/data'
    target.mkdir(parents=True,exist_ok=True)
    payload = json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    (target/'week5.json').write_text(payload,encoding='utf-8')
    (target/'week5.js').write_text('window.WEEK5_DATA = '+json.dumps(result,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(json.dumps(result['result'],indent=2))
    print(f"Wrote assets/data/week5.json and .js ({len(result['pairs'])} reviewed pairs).")


if __name__ == '__main__':
    main()
