"""cdd archify：调用链 → archify Architecture IR。

边只能来自索引里真实的调用，节点的 sources 行号要落在函数上，层框不能圈进别层的节点
（archify 按被框节点的外接矩形画框）。
"""
import re
from pathlib import Path

from analyzer.anchors import generate_all_anchors, load_anchors
from usage.export.archify_ir import build_architecture_ir, collect_chain

FILES = {
    "app/main.py": "from core.service import handle\n\n\ndef main():\n    return handle(1)\n",
    "core/service.py": (
        "from core.store import save\nfrom util.text import clean\n\n\n"
        "def handle(x):\n    return save(clean(x))\n"
    ),
    "core/store.py": "def save(x):\n    return x\n",
    "util/text.py": "def clean(x):\n    return x\n\n\ndef unused():\n    return 0\n",
}


def _anchors(tmp_path: Path):
    for rel, text in FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    generate_all_anchors(root=str(tmp_path))
    return load_anchors(root=str(tmp_path))


def test_chain_follows_only_real_calls(tmp_path):
    anchors = _anchors(tmp_path)
    seen, _ = collect_chain(anchors, "app/main.py::main", 6)
    assert set(seen) == {"app/main.py::main", "core/service.py::handle",
                         "core/store.py::save", "util/text.py::clean"}


def test_ir_nodes_are_files_and_edges_are_calls(tmp_path):
    anchors = _anchors(tmp_path)
    ir, stats = build_architecture_ir(anchors, "app/main.py::main", 6, "main.html")
    assert stats == {"functions": 4, "files": 4, "links": 3}
    labels = {(c["from"], c["to"]): c["label"] for c in ir["connections"]}
    assert labels[("f_app_main_py", "f_core_service_py")] == "handle"
    assert labels[("f_core_service_py", "f_util_text_py")] == "clean"
    for comp in ir["components"]:
        assert re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", comp["id"])
        assert 1 <= len(comp["sources"]) <= 3
        for src in comp["sources"]:
            assert 1 <= src["line"] <= src["end_line"]
    entry = next(c for c in ir["components"] if c["id"] == "f_app_main_py")
    assert entry["type"] == "frontend" and entry["col"] == 0


def test_region_box_never_wraps_another_layer(tmp_path):
    anchors = _anchors(tmp_path)
    ir, _ = build_architecture_ir(anchors, "app/main.py::main", 6, "main.html")
    by_id = {c["id"]: c for c in ir["components"]}
    for box in ir.get("boundaries", []):
        inside = [by_id[i] for i in box["wraps"]]
        rows = [c["row"] for c in inside]; cols = [c["col"] for c in inside]
        for c in ir["components"]:
            if c["id"] in box["wraps"]:
                continue
            assert not (min(rows) <= c["row"] <= max(rows) and min(cols) <= c["col"] <= max(cols))


def _git(cwd, *args):
    import subprocess
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_repository_pinned_only_when_project_is_the_git_root(tmp_path):
    from usage.export.archify_repo import repository_identity
    _git(tmp_path, "init", "-q")
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x")
    # 子目录：HEAD 属于外层仓库，sources 路径对不上，不能钉
    assert repository_identity(tmp_path / "proj") == (None, set())
    repo, dirty = repository_identity(tmp_path)
    assert re.fullmatch(r"[0-9a-f]{40}", repo["revision"]) and repo["link_mode"] == "local-only"
    assert dirty == set()
