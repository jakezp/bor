import types
from core.knowledgebase.Utils import Utils


class DummyNode:
    def __init__(self, id, labels, props):
        self.id = id
        self.labels = labels
        self.properties = props


class DummyEdge:
    def __init__(self, id, start_id, end_id, type_, props):
        self.id = id
        self.start_id = start_id
        self.end_id = end_id
        self.type = type_
        self.properties = props


def make_row(nodes, edges):
    # Emulate Memgraph project() return as dict
    return {"sg": {"nodes": nodes, "edges": edges}}


def test_results_to_dictlist_flattens_multiple_rows():
    rows = [
        make_row([DummyNode(1, ["A"], {"x": 1})], [DummyEdge(10, 1, 2, "REL", {"w": 1})]),
        make_row([DummyNode(2, ["B"], {"y": 2})], []),
    ]
    out = Utils.results_to_dictlist(rows, "sg")
    # Expect 3 items: 2 nodes + 1 edge
    assert isinstance(out, list)
    assert len(out) == 3
    # Identify nodes vs edges by shape
    node_ids = sorted([o.get("id") for o in out if "labels" in o])
    assert node_ids == [1, 2]
    edge_ids = sorted([o.get("id") for o in out if "start" in o and "end" in o])
    assert edge_ids == [10]
