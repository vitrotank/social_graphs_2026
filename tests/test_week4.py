import json, math, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from analyze_week4 import (louvain, modularity, weighted_graph, _aggregate,
                          normalized_mutual_information, align_partitions,
                          disparity_edges, backbone_metrics, backbone_breakpoints)

class Week4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/"assets/data/week4.json").read_text(encoding="utf-8"))

    def test_seeded_partition_is_repeatable_and_modular(self):
        g=weighted_graph([{"node_id":x} for x in "ABCDEF"],[
            {"source":"A","target":"B","weight":"2"},{"source":"B","target":"C","weight":"2"},
            {"source":"D","target":"E","weight":"2"},{"source":"E","target":"F","weight":"2"},{"source":"C","target":"D","weight":"0.1"}])
        a=louvain(g,7); b=louvain(g,7)
        self.assertEqual(a,b); self.assertGreater(a[1],0)
        self.assertAlmostEqual(a[1],modularity(g,a[0]))
    def test_published_data_has_null_and_partition(self):
        data=self.data
        self.assertEqual(data["nodes"],1374)
        self.assertEqual(data["undirected_edges"],9139)
        self.assertEqual(len(data["partition"]),data["nodes"])
        self.assertEqual(data["null"]["trials"],6)
        self.assertGreater(data["modularity"],data["null"]["mean"])
        self.assertEqual(data["seed"],2026)
        self.assertEqual(len(data["runs"]),10)
        self.assertGreater(data["stability"]["mean"],0.8)
        self.assertEqual(data["null"]["type"],"degree-preserving double-edge swaps")

    def test_aggregation_preserves_modularity_and_total_degree(self):
        # Aggregating an internal weight-2 edge makes a loop of weight 2,
        # not 4. Loops contribute twice their weight to a node's degree.
        graph=weighted_graph([{"node_id":x} for x in "ABC"],[
            {"source":"A","target":"B","weight":2},
            {"source":"B","target":"C","weight":1}])
        partition={"A":0,"B":0,"C":1}
        aggregated,mapping=_aggregate(graph,partition)
        self.assertEqual(aggregated[mapping[0]][mapping[0]],2)
        degrees=lambda g:sum(sum(v.values())+v.get(n,0) for n,v in g.items())
        self.assertEqual(degrees(graph),degrees(aggregated))
        self.assertAlmostEqual(modularity(graph,partition),modularity(aggregated,{n:n for n in aggregated}))
        again,_=_aggregate(aggregated,{n:0 for n in aggregated})
        self.assertEqual(degrees(graph),degrees(again))
        self.assertAlmostEqual(modularity(again,{n:0 for n in again}),0)

    def test_nmi_is_label_invariant_and_distinguishes_independent_partitions(self):
        a=dict(zip("ABCD",(0,0,1,1)))
        relabeled=dict(zip("ABCD",(9,9,3,3)))
        independent=dict(zip("ABCD",(0,1,0,1)))
        self.assertAlmostEqual(normalized_mutual_information(a,relabeled),1)
        self.assertAlmostEqual(normalized_mutual_information(a,independent),0)
        self.assertAlmostEqual(normalized_mutual_information(a,independent),normalized_mutual_information(independent,a))
        self.assertEqual(normalized_mutual_information({"A":0},{"A":7}),1)
        with self.assertRaises(ValueError): normalized_mutual_information(a,{"A":0})

    def test_alignment_finds_global_maximum_not_greedy_matching(self):
        # Overlap [[6,5],[5,0]]: greedy retains 6, optimum retains 10.
        reference,other={},{}
        for prefix,count,ref,weighted in (("A",6,0,0),("B",5,1,0),("C",5,0,1)):
            for index in range(count):
                node=f"{prefix}{index}"
                reference[node],other[node]=ref,weighted
        aligned,records=align_partitions(reference,other)
        self.assertEqual(sum(reference[n]==aligned[n] for n in reference),10)
        self.assertEqual({r["weighted"]:r["aligned"] for r in records},{0:1,1:0})

    def test_disparity_uses_either_endpoint_and_strict_threshold(self):
        graph=weighted_graph([{"node_id":x} for x in "ABCD"],[
            {"source":"A","target":"B","weight":2},
            {"source":"A","target":"C","weight":7},
            {"source":"B","target":"D","weight":1}])
        edges=disparity_edges(graph)
        ab=next(e for e in edges if e["source"]=="A" and e["target"]=="B")
        # A's tail is 7/9; B's is 1/3. B keeps the edge for its sake.
        self.assertAlmostEqual(ab["alpha"],1/3)
        self.assertEqual(backbone_metrics(graph,[ab],ab["alpha"])["edges"],0)
        self.assertEqual(backbone_metrics(graph,[ab],math.nextafter(ab["alpha"],1))["edges"],1)
        lone={"A":{"B":1},"B":{"A":1}}
        lone_edges=disparity_edges(lone)
        self.assertEqual(lone_edges[0]["alpha"],1)
        self.assertEqual(backbone_metrics(lone,lone_edges,.99)["edges"],0)
        self.assertEqual(backbone_metrics(lone,lone_edges,1)["edges"],1)

    def test_degree_one_endpoint_cannot_automatically_save_its_edge(self):
        graph=weighted_graph([{"node_id":x} for x in "ABCD"],[
            {"source":"A","target":"B","weight":2},
            {"source":"B","target":"C","weight":1},
            {"source":"B","target":"D","weight":1}])
        edges=disparity_edges(graph)
        ab=next(edge for edge in edges if edge["source"]=="A" and edge["target"]=="B")
        # A's degree-one tail is 1; the hub B's is (1-2/4)^2=.25.
        self.assertEqual(ab["alpha"],.25)
        strict=backbone_metrics(graph,edges,.2)
        self.assertEqual((strict["nodes"],strict["edges"],strict["giant_nodes"],strict["components"]),(0,0,0,4))
        looser=backbone_metrics(graph,edges,.3)
        self.assertEqual((looser["nodes"],looser["edges"],looser["giant_nodes"],looser["components"]),(2,1,2,3))

    def test_explorer_reproduces_course_backbone_table(self):
        explorer=self.data["explorer"]
        expected={.05:(292,348,116),.1:(649,607,419),.2:(1540,950,816),.3:(2549,1111,1052),.5:(5641,1284,1270)}
        for row in explorer["backbone"]["presets"]:
            if row["alpha"] in expected:
                self.assertEqual((row["edges"],row["nodes"],row["giant_nodes"]),expected[row["alpha"]])
        self.assertEqual(explorer["backbone"]["global_threshold"],{"minimum_weight":3,"edges":1572,"nodes":863})
        for first,second in zip(explorer["backbone"]["curve"],explorer["backbone"]["curve"][1:]):
            self.assertLessEqual(first["edges"],second["edges"])
            self.assertLessEqual(first["nodes"],second["nodes"])
            self.assertLessEqual(first["giant_nodes"],second["giant_nodes"])
            self.assertGreaterEqual(first["components"],second["components"])

    def test_explorer_partitions_and_movers_are_consistent(self):
        explorer=self.data["explorer"]
        nodes=explorer["nodes"]
        reference={n["id"]:n["community"] for n in nodes}
        weighted={n["id"]:n["weighted_community"] for n in nodes}
        self.assertEqual(len(nodes),self.data["nodes"])
        self.assertEqual(len(explorer["edges"]),self.data["undirected_edges"])
        self.assertEqual({n["id"]:n["community"] for n in self.data["partition"]},reference)
        self.assertAlmostEqual(explorer["weighted_comparison"]["nmi"],normalized_mutual_information(reference,weighted))
        self.assertEqual({n["id"] for n in explorer["weighted_comparison"]["movers"]},{n for n in reference if reference[n]!=weighted[n]})
        self.assertEqual(sum(n["degree"] for n in nodes),2*len(explorer["edges"]))
        self.assertEqual(sum(n["strength"] for n in nodes),2*sum(e["weight"] for e in explorer["edges"]))
        self.assertEqual(explorer["aristotle"]["strength"],521)
        self.assertEqual(explorer["aristotle"]["degree"],300)
        self.assertEqual(sum(c["count"] for c in explorer["aristotle"]["neighbor_communities"]),300)
        self.assertTrue(all(0<=n["x"]<=1000 and 0<=n["y"]<=760 for n in nodes))

    def test_exact_half_giant_event_is_a_tied_edge_removal(self):
        explorer=self.data["explorer"]
        event=explorer["backbone"]["breakpoint"]["half_giant"]
        nodes={n["id"] for n in explorer["nodes"]}
        strict=backbone_metrics(nodes,explorer["edges"],event["alpha"])
        loose=backbone_metrics(nodes,explorer["edges"],math.nextafter(event["alpha"],1))
        self.assertLess(strict["giant_nodes"],len(nodes)/2)
        self.assertGreaterEqual(loose["giant_nodes"],len(nodes)/2)
        self.assertEqual(strict["giant_nodes"],event["giant_after_tightening"])
        self.assertEqual(loose["giant_nodes"],event["giant_before_tightening"])
        self.assertEqual(loose["edges"]-strict["edges"],event["removed_edge_count"])
        self.assertEqual(event["joining_edge_count"],1)
        self.assertEqual({event["critical_edges"][0]["source"],event["critical_edges"][0]["target"]},{"Confucius","Voltaire"})

    def test_browser_bundle_matches_json(self):
        script=(ROOT/"assets/data/week4.js").read_text(encoding="utf-8")
        self.assertTrue(script.startswith("window.CROSSTALK_WEEK4 = "))
        browser=json.loads(script.removeprefix("window.CROSSTALK_WEEK4 = ").strip().removesuffix(";"))
        self.assertEqual(browser,self.data)
if __name__=="__main__": unittest.main()
