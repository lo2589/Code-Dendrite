"""archify 合法 ≠ 读得懂：audit 查并线、标签挂错、端点没接上；polish 一次只试一个改法。"""
from usage.export.archify_repair import audit, polish


def _node(nid, x, y, w=100, h=60):
    return {"id": nid, "x": x, "y": y, "width": w, "height": h}


def _layout(conns, labels):
    comps = [_node("a", 0, 0), _node("b", 400, 0), _node("c", 400, 200)]
    return {"components": comps, "connections": conns, "labels": labels}


def _conn(frm, to, label, pts, at):
    return {"from": frm, "to": to, "label": label, "points": pts, "labelAt": at}


def test_clean_layout_has_no_problems():
    c = _conn("a", "b", "call", [[100, 30], [400, 30]], [250, 20])
    lab = {"text": "call", "x": 230, "y": 10, "width": 40, "height": 14, "labelAt": [250, 20]}
    assert audit(_layout([c], [lab])) == []


def test_two_edges_in_one_corridor_are_reported():
    c1 = _conn("a", "b", "x", [[100, 30], [200, 30], [200, -40], [450, -40], [450, 0]], [300, -50])
    c2 = _conn("a", "c", "y", [[100, 40], [180, 40], [180, -40], [430, -40], [430, 200]], [300, -50])
    kinds = {p[0] for p in audit(_layout([c1, c2], []))}
    assert "shared" in kinds


def test_label_closer_to_another_line_is_reported():
    c1 = _conn("a", "b", "mine", [[100, 30], [400, 30]], [250, 60])
    c2 = _conn("a", "c", "other", [[100, 50], [250, 50], [250, 230], [400, 230]], [320, 220])
    lab = {"text": "mine", "x": 230, "y": 52, "width": 40, "height": 14, "labelAt": [250, 60]}
    problems = audit(_layout([c1, c2], [lab]))
    assert ("label", 0) in {(p[0], p[1]) for p in problems}


def test_detached_endpoint_is_reported():
    c = _conn("a", "b", "call", [[100, 30], [380, 30]], [250, 20])
    assert ("endpoint", 0) in {(p[0], p[1]) for p in audit(_layout([c], []))}


def test_polish_keeps_only_changes_that_reduce_problems():
    """validate 是假的：只有第 1 条边改成从底部出线，并线才消失；手写 via 一律不合法。"""
    shared = [_conn("a", "b", "x", [[100, 30], [200, 30], [200, -40], [450, -40], [450, 0]], [300, -50]),
              _conn("a", "c", "y", [[100, 40], [180, 40], [180, -40], [430, -40], [430, 200]], [300, -50])]
    clean = [_conn("a", "b", "x", [[100, 30], [400, 30]], [250, 20]),
             _conn("a", "c", "y", [[50, 60], [50, 230], [400, 230]], [60, 150])]

    def validate(ir):
        if any("via" in c for c in ir["connections"]):
            return None          # 不合法的改法要被撤回
        ok = ir["connections"][1].get("fromSide") == "bottom"
        return _layout(clean if ok else shared, [])

    ir = {"connections": [{"from": "a", "to": "b", "label": "x"}, {"from": "a", "to": "c", "label": "y"}]}
    fixed, remaining = polish(ir, validate)
    assert remaining == []
    assert fixed["connections"][1] == {"from": "a", "to": "c", "label": "y", "fromSide": "bottom"}
    assert fixed["connections"][0] == {"from": "a", "to": "b", "label": "x"}
    assert "fromSide" not in ir["connections"][1]   # 原 IR 不被就地改坏
