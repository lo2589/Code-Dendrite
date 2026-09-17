"""连线可以点：点一条连线 = 跳到它指向的子节点。

图上的连线原来只是画出来的线（1.2px、没有 id），点不动。要「顺着连线找子节点」
就得让每条线带着两端 anchor id 落进 SVG，并且有一条足够宽的透明命中区——1.2px 的
线本身点不中。可见的那条线必须 pointer-events:none，否则它会把点击吞掉。

这个文件钉住的是：两端的 id 都在、命中区在、可见线不吃点击、点连线走的是和点节点
同一条路径（选中 + onSel）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer.anchors import generate_all_anchors            # noqa: E402
from view.browser import generate                            # noqa: E402
from view.module_tree import draw_pages                      # noqa: E402

PY_SRC = "def helper(x):\n    return x + 1\n\n\ndef main():\n    return helper(1)\n"


def _page(tmp_path: Path) -> str:
    (tmp_path / "app.py").write_text(PY_SRC, encoding="utf-8")
    generate_all_anchors(str(tmp_path))
    generate(str(tmp_path), str(tmp_path / ".codedendrite" / "anchor_browser.html"))
    page = tmp_path / ".codedendrite" / "anchor_browser_pages" / (draw_pages.page_id("app.py") + ".html")
    assert page.exists(), "no page for app.py"
    return page.read_text(encoding="utf-8")


def test_edge_path_carries_both_ends(tmp_path):
    html = _page(tmp_path)
    assert 'data-from="${escA(e.s)}"' in html, "连线没有带上源 anchor id"
    assert 'data-to="${escA(e.t)}"' in html, "连线没有带上目标 anchor id"


def test_edge_has_a_wide_transparent_hit_area(tmp_path):
    html = _page(tmp_path)
    hit = 'stroke="transparent" stroke-width="10" style="cursor:pointer"'
    assert hit in html, "连线没有命中区，1.2px 的线点不中"


def test_visible_edge_does_not_swallow_clicks(tmp_path):
    """可见线叠在命中区上面，必须让点击穿过去。"""
    html = _page(tmp_path)
    visible = html.index('marker-end="url(#${mk})"')
    assert 'pointer-events="none"' in html[visible:visible + 120], "可见连线会吃掉点击"


def test_hit_area_is_emitted_before_the_visible_line(tmp_path):
    html = _page(tmp_path)
    assert html.index('data-to="${escA(e.t)}"') < html.index('marker-end="url(#${mk})"'), \
        "命中区必须画在可见线下面，否则会被盖住"


def test_clicking_an_edge_selects_the_child(tmp_path):
    """点连线与点节点同义：选中目标节点并通知详情面板。"""
    html = _page(tmp_path)
    assert "this.eg.addEventListener('click'" in html, "连线层没有点击委托"
    handler = html[html.index("this.eg.addEventListener('click'"):]
    handler = handler[:handler.index("});") + 3]
    assert "e.target.closest('[data-to]')" in handler, "点击委托没有认 data-to"
    assert "this.sel=to" in handler, "点连线没有选中子节点"
    assert "this.onSel" in handler, "点连线没有通知详情面板"
