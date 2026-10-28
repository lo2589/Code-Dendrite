"""pip install 留下的 build/lib/ 不能进索引。

build/lib/ 是整份源码的拷贝。扫进来以后同一个模块有两份，``from pkg.core import run``
解析不出唯一目标，跨文件的边全断——本仓库实测 ``cdd chain mcp/server.py::call_tool``
从 55 行掉到 15 行。建索引只认项目自己的 .codedendrite_ignore，而用户几乎不会在里面写
build/lib，所以构建产物要在 should_scan 里先挡掉。
"""
from pathlib import Path

from analyzer.anchors import generate_all_anchors, load_anchors

CORE = "def run():\n    return 1\n"
MAIN = "from pkg.core import run\n\n\ndef main():\n    return run()\n"


def _project(tmp_path: Path) -> Path:
    for base in (tmp_path, tmp_path / "build" / "lib"):
        (base / "pkg").mkdir(parents=True, exist_ok=True)
        (base / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (base / "pkg" / "core.py").write_text(CORE, encoding="utf-8")
        (base / "pkg" / "main.py").write_text(MAIN, encoding="utf-8")
    # 自己的构建脚本放在 build/ 下，不是产物，必须照样扫
    (tmp_path / "build" / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "build" / "scripts" / "make.py").write_text("def make():\n    return 0\n", encoding="utf-8")
    return tmp_path


def test_build_lib_copy_is_not_indexed(tmp_path):
    root = _project(tmp_path)
    generate_all_anchors(root=str(root))
    anchors = load_anchors(root=str(root))
    assert not [a for a in anchors if a.startswith("build/lib/")]


def test_cross_file_call_resolves_to_the_real_source(tmp_path):
    root = _project(tmp_path)
    generate_all_anchors(root=str(root))
    anchors = load_anchors(root=str(root))
    assert "pkg/core.py::run" in anchors["pkg/main.py::main"].callees


def test_own_build_scripts_are_still_indexed(tmp_path):
    root = _project(tmp_path)
    generate_all_anchors(root=str(root))
    anchors = load_anchors(root=str(root))
    assert "build/scripts/make.py::make" in anchors
