"""未解析的属性调用可以作为候选出现在下行链里，但不当成边、也不沿它继续展开。

`cfg.from_file(...)` 这种调用，Python AST 证不出接收者类型，所以它进不了调用图
（resolver 里有明确说明：把它当成项目里同名函数，曾经把生产代码连到测试替身上）。
但"图上没有边"和"这条线索不存在"是两件事——线索还在 anchor 的 call_sites 里。

所以候选通道的规则是：名字在整个索引里唯一才给提示，标 resolution="candidate"，
并且**不沿候选继续展开**（否则一个类名候选会把整个子树拖进链里）。默认关闭。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.anchors import generate_all_anchors            # noqa: E402
from api.inspector import get_downward_chain                 # noqa: E402

SRC = """class Config:
    def from_file(self, path):
        return self.helper(path)

    def helper(self, path):
        return path


def use(cfg):
    return cfg.from_file("x")


def main():
    return use(Config())
"""

SRC_AMBIGUOUS = """class A:
    def from_file(self, path):
        return path


class B:
    def from_file(self, path):
        return path


def use(cfg):
    return cfg.from_file("x")
"""


def _project(tmp_path: Path, source: str = SRC):
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    generate_all_anchors(str(tmp_path))
    return tmp_path


def _chain(root, symbol, **kw):
    return get_downward_chain("app.py::{}".format(symbol), str(root), max_depth=6, **kw)


def test_default_keeps_unresolved_attribute_calls_out(tmp_path):
    root = _project(tmp_path)
    names = [n["symbol"] for n in _chain(root, "use")]
    assert "Config.from_file" not in names, "默认不该把未解析的属性调用当成边"


def test_candidate_is_offered_when_the_name_is_unique(tmp_path):
    root = _project(tmp_path)
    chain = _chain(root, "use", include_candidates=True)
    cands = [n for n in chain if n.get("resolution") == "candidate"]
    assert [c["symbol"] for c in cands] == ["Config.from_file"]
    assert cands[0]["candidate_reason"] == "unresolved-attribute-call"


def test_candidate_carries_where_it_came_from(tmp_path):
    root = _project(tmp_path)
    cand = [n for n in _chain(root, "use", include_candidates=True)
            if n.get("resolution") == "candidate"][0]
    assert cand["call_line"], "候选要带上调用点在源码里的行号"


def test_candidate_is_not_expanded_further(tmp_path):
    """候选是提示，不是边：不沿它继续往下走。"""
    root = _project(tmp_path)
    chain = _chain(root, "use", include_candidates=True)
    assert "Config.from_file" in [n["symbol"] for n in chain]
    assert "Config.helper" not in [n["symbol"] for n in chain], "候选被继续展开了"


def test_ambiguous_name_gets_no_candidate(tmp_path):
    """同名多解一律不给提示——那种提示只会把人带偏。"""
    root = _project(tmp_path, SRC_AMBIGUOUS)
    chain = _chain(root, "use", include_candidates=True)
    assert not [n for n in chain if n.get("resolution") == "candidate"]


def test_real_edges_still_come_through(tmp_path):
    root = _project(tmp_path)
    chain = _chain(root, "main", include_candidates=True)
    assert any(n["symbol"] == "use" and n.get("resolution") != "candidate" for n in chain)
