"""cdd archify 的版面：列走最长调用路径，边都从左指向右；同名文件分得清；框不圈全图；宽度在 archify 上限内。"""
from pathlib import Path

from analyzer.anchors import generate_all_anchors, load_anchors
from usage.export.archify_ir import WIDTH_BUDGET, build_architecture_ir

FILES = {
    "app/main.py": (
        "from core.store import save\nfrom core.service import handle\n\n\n"
        "def main():\n    save(0)\n    return handle(1)\n"
    ),
    # handle 又调 save：save 既被入口直接调，也被 service 调，应排到 service 右边
    "core/service.py": "from core.store import save\nfrom util.core import fmt\n\n\ndef handle(x):\n    return save(fmt(x))\n",
    "core/store.py": "def save(x):\n    return x\n",
    "util/core.py": "from lib.core import base\n\n\ndef fmt(x):\n    return base(x)\n",
    "lib/core.py": "def base(x):\n    return x\n",
}


def _ir(tmp_path: Path):
    for rel, text in FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    generate_all_anchors(root=str(tmp_path))
    ir, _ = build_architecture_ir(load_anchors(root=str(tmp_path)), "app/main.py::main", 6, "m.html")
    return ir, {c["id"]: c for c in ir["components"]}


def test_every_edge_points_right(tmp_path):
    ir, comps = _ir(tmp_path)
    for conn in ir["connections"]:
        assert comps[conn["to"]]["col"] > comps[conn["from"]]["col"], conn


def test_shared_callee_sits_right_of_its_deepest_caller(tmp_path):
    _, comps = _ir(tmp_path)
    assert comps["f_core_store_py"]["col"] > comps["f_core_service_py"]["col"]


def test_same_file_names_get_distinct_sublabels(tmp_path):
    _, comps = _ir(tmp_path)
    assert comps["f_util_core_py"]["label"] == comps["f_lib_core_py"]["label"] == "core.py"
    assert comps["f_util_core_py"]["sublabel"] != comps["f_lib_core_py"]["sublabel"]


def test_no_box_wraps_every_node_and_width_fits(tmp_path):
    ir, comps = _ir(tmp_path)
    for box in ir.get("boundaries", []):
        assert len(box["wraps"]) < len(comps)
    lay = ir["layout"]
    assert 40 + lay["cols"] * lay["cellW"] + (lay["cols"] - 1) * lay["gapX"] <= WIDTH_BUDGET
