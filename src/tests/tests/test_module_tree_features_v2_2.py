"""模块树 = 功能树：一个模块是一个功能，从入口开始，how 讲清它一步一步怎么做完。"""
from pathlib import Path

from analyzer.anchors import generate_all_anchors
from usage.structure.module_tree_v2 import generate_module_tree_v2

FILES = {
    # 一个 CLI：按参数分支到两个功能实现
    "app/cli.py": (
        '"""命令行入口"""\nimport sys\nfrom core.export import export_all\nfrom core.report import build_report\n\n\n'
        "def main(argv):\n    if argv[0] == 'export':\n        export_all(argv)\n    elif argv[0] == 'report':\n        build_report(argv)\n\n\n"
        "if __name__ == '__main__':\n    main(sys.argv[1:])\n"
    ),
    "core/export.py": (
        "from shared.io import write_out\nfrom core.store import Store\n\n\n"
        'def export_all(argv):\n    """把全部记录导出成文件"""\n    rows = collect(argv)\n    write_out(rows)\n\n\n'
        "def collect(argv):\n    return Store().rows()\n"
    ),
    "core/report.py": (
        "from shared.io import write_out\n\n\n"
        'def build_report(argv):\n    """生成统计报告"""\n    write_out(summarize(argv))\n\n\n'
        "def summarize(argv):\n    return len(argv)\n"
    ),
    # 类：方法靠 obj.method() 调，静态解析不到，要随类一起算进实现；@property 不是入口
    "core/store.py": (
        "class Store:\n    def rows(self):\n        return self._load()\n\n    def _load(self):\n        return []\n\n"
        "    @property\n    def size(self):\n        return len(self.rows())\n"
    ),
    # 三个功能都用 → 共享底座
    "shared/io.py": "def write_out(data):\n    return fmt(data)\n\n\ndef fmt(data):\n    return str(data)\n",
    "tools/backup.py": (
        "from shared.io import write_out\n\n\n"
        'def run_backup():\n    """备份"""\n    write_out(step_one())\n\n\ndef step_one():\n    return 1\n'
    ),
    # 没人调用的零散函数
    "legacy/old.py": "def unused():\n    return 1\n",
    "tests/test_export.py": "from core.export import export_all\n\n\ndef test_export():\n    export_all(['x'])\n",
}


def _tree(tmp_path: Path):
    for rel, text in FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    generate_all_anchors(root=str(tmp_path))
    tree = generate_module_tree_v2(str(tmp_path))
    return tree, {m["name"]: m for m in tree["modules"]}


def test_cli_feature_how_shows_branches_in_call_order(tmp_path):
    _, mods = _tree(tmp_path)
    cli = mods["app/cli"]
    assert cli["status"] == "core_flow"
    assert cli["what"] == "命令行入口"
    how = cli["how"].split("\n")
    assert how[0].startswith("1. main")
    export_line = next(l for l in how if "export_all" in l)
    report_line = next(l for l in how if "build_report" in l)
    assert how.index(export_line) < how.index(report_line)
    assert "〔若" in export_line and "把全部记录导出成文件" in export_line and "core/export.py" in export_line


def test_shared_code_is_its_own_module(tmp_path):
    _, mods = _tree(tmp_path)
    shared = [m for m in mods.values() if m["status"] == "support_utility"]
    assert any("shared/io.py::write_out" in m["functions"] for m in shared)
    assert "shared/io.py" not in mods["app/cli"]["files"]


def test_class_methods_belong_to_the_feature_and_property_is_not_an_entry(tmp_path):
    tree, mods = _tree(tmp_path)
    assert "core/store.py" in mods["app/cli"]["files"]
    entries = {e for m in tree["modules"] for e in m["entrypoints"]}
    assert "core/store.py::Store.size" not in entries


def test_uncalled_code_is_dormant_and_tests_are_evidence_not_features(tmp_path):
    tree, mods = _tree(tmp_path)
    dormant = [m for m in tree["modules"] if m["status"] == "dormant"]
    assert any("legacy/old.py::unused" in m["entrypoints"] for m in dormant)
    assert not any(e.startswith("tests/") for m in tree["modules"] for e in m["entrypoints"])
    assert "tests/test_export.py::test_export" in mods["app/cli"]["evidence"]["tests"]


def test_root_function_with_its_own_implementation_is_a_feature(tmp_path):
    _, mods = _tree(tmp_path)
    backup = next(m for name, m in mods.items() if name.startswith("run_backup"))
    assert backup["status"] == "independent_capability" and backup["what"] == "备份"
