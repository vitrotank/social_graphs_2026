"""Checks for the exact text matching algorithm and published evidence.

These tests cover the failure modes that would change the reported finding:
paragraph seams, longer extensions, normalization, missing source pages and
text offsets that no longer refer to the quoted passage.
"""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import analyze_week5 as analysis
from analyze import load_graph


class SharedPhraseTests(unittest.TestCase):
    def test_longest_run_extends_seed_and_respects_paragraph_boundary(self):
        texts = {
            'a':'prefix red blue green yellow orange violet black white ending\n\none two three',
            'b':'other red blue green yellow orange violet black white ending\n\nfour five six',
            'c':'red blue green yellow\n\norange violet black white ending'
        }
        _,pairs = analysis.shared_runs(texts,minimum=4)
        self.assertEqual(pairs['a','b'][0],9)
        self.assertEqual(pairs['a','c'][0],5)
        self.assertEqual(pairs['b','c'][0],5)

    def test_normalization_and_source_offsets(self):
        a = 'Header\n\nA character’s red-blue costume, created in 1995, is fictional.'
        b = "A CHARACTER'S RED blue costume created in 2005 is fictional!"
        docs,pairs = analysis.shared_runs({'a':a,'b':b},minimum=4)
        length,ap,ai,bp,bi = pairs['a','b']
        left = analysis.passage(docs,'a',ap,ai,length)
        right = analysis.passage(docs,'b',bp,bi,length)
        self.assertEqual(length,9)
        self.assertEqual(a[left['start']:left['end']],left['text'])
        self.assertEqual(b[right['start']:right['end']],right['text'])
        self.assertEqual(analysis.tokenize(left['text']),analysis.tokenize(right['text']))
        # The numerals sensitivity check must detect the different dates.
        _,numeric = analysis.shared_runs({'a':a,'b':b},minimum=4,pattern=analysis.NUMBER_WORD)
        self.assertLess(numeric['a','b'][0],length)

    def test_tie_chooses_earliest_source_occurrence(self):
        docs,pairs = analysis.shared_runs({'a':'red blue green\n\nred blue green','b':'red blue green'},minimum=3)
        self.assertEqual(pairs['a','b'],(3,0,0,0,0))

    def test_archive_requires_complete_roster_and_decodes_titles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'test.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('marvel_pages/README.txt','metadata')
                archive.writestr('marvel_pages/Name%3A_title.txt','A real source.')
            self.assertEqual(analysis.load_corpus(path,{'Name:_title':{}}),{'Name:_title':'A real source.'})
            with self.assertRaises(ValueError):
                analysis.load_corpus(path,{'missing':{}})


class PublishedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT/'assets/data/week5.json').read_text(encoding='utf-8'))
        cls.nodes,_ = load_graph(ROOT/'data/raw/week1_nodes.tsv',ROOT/'data/raw/week1_edges.tsv')
        cls.texts = analysis.load_corpus(ROOT/'data/raw/marvel_pages.zip',cls.nodes)

    def test_every_displayed_passage_exists_and_matches(self):
        rows = self.data['pairs'] + [self.data['examples']['editorial']]
        for pair in rows:
            normalized = []
            for source in pair['sources']:
                text = self.texts[source['node']]
                self.assertEqual(text[source['start']:source['end']],source['text'])
                self.assertEqual(source['url'],self.nodes[source['node']]['url'])
                words = analysis.tokenize(source['text'])
                self.assertEqual(len(words),pair['length'])
                normalized.append(words)
            self.assertEqual(*normalized)

    def test_reported_counts_are_ordered_and_share_one_denominator(self):
        thresholds = self.data['thresholds']
        self.assertEqual(len(self.texts),303)
        self.assertEqual(self.data['result']['possible_pairs'],303*302//2)
        for left,right in zip(thresholds,thresholds[1:]):
            self.assertLessEqual(right['pairs'],left['pairs'])
            self.assertLessEqual(right['articles'],left['articles'])
        for row in thresholds:
            self.assertLessEqual(row['without_lead_pairs'],row['pairs'])
            self.assertAlmostEqual(row['percent'],100*row['pairs']/45753)
            if row['length']>=20:
                self.assertEqual(row['pairs'],sum(p['length']>=row['length'] for p in self.data['pairs']))
        self.assertEqual(len(self.data['pairs']),71)
        self.assertEqual(max(p['length'] for p in self.data['pairs']),166)


if __name__=='__main__':
    unittest.main()
