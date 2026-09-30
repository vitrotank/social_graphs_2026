import json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from analyze_week4 import louvain, modularity, weighted_graph

class Week4Tests(unittest.TestCase):
    def test_seeded_partition_is_repeatable_and_modular(self):
        g=weighted_graph([{"node_id":x} for x in "ABCDEF"],[
            {"source":"A","target":"B","weight":"2"},{"source":"B","target":"C","weight":"2"},
            {"source":"D","target":"E","weight":"2"},{"source":"E","target":"F","weight":"2"},{"source":"C","target":"D","weight":"0.1"}])
        a=louvain(g,7); b=louvain(g,7)
        self.assertEqual(a,b); self.assertGreater(a[1],0)
        self.assertAlmostEqual(a[1],modularity(g,a[0]))
    def test_published_data_has_null_and_partition(self):
        data=json.loads((ROOT/"assets/data/week4.json").read_text(encoding="utf-8"))
        self.assertEqual(data["nodes"],1374)
        self.assertEqual(data["undirected_edges"],9139)
        self.assertEqual(len(data["partition"]),data["nodes"])
        self.assertEqual(data["null"]["trials"],6)
        self.assertGreater(data["modularity"],data["null"]["mean"])
        self.assertEqual(data["seed"],2026)
        self.assertEqual(len(data["runs"]),10)
        self.assertGreater(data["stability"]["mean"],0.8)
        self.assertEqual(data["null"]["type"],"degree-preserving double-edge swaps")
if __name__=="__main__": unittest.main()
