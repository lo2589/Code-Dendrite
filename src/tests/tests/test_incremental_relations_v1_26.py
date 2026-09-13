"""CDD V1.26 — 增量 relations 必须与全量 relations 逐边相等。

为什么单独有这个文件：`cdd update` 声称是增量的，但 anchor 那一步是真增量、
relations 那一步是假增量（每次都全量重推 25227 条边）。要让 relations 真的增量，
唯一的验收口径就是这条——同一个变更集，两条路走出来的 relations.json 必须一模一样。
少一条边、多一条边、seq 顺序不同，都算索引漂了，而这在界面上只表现为"关系看着不对"。

每个用例：两份完全相同的工程 → 各建一次全量索引 → 施同一个改动 →
  full 侧跑全量 generate_relations
  inc  侧跑增量 generate_relations(changed_files=[改过的文件])
→ 比对两份 relations.json。
"""

import json
import shutil
from pathlib import Path

from analyzer.anchors import generate_all_anchors, update_anchors_for_files
from api.relations import generate_relations


# ── 夹具：一个跨 4 个文件、带 call / dataflow / inherit 的小工程 ──────────

FILES = {
    "__init__.py": "",
    "pkg/__init__.py": "",
    "pkg/beta.py": (
        "def fetch_rows(source):\n"
        "    return [row for row in source]\n"
        "\n"
        "\n"
        "def prune(rows):\n"
        "    return [row for row in rows if row]\n"
        "\n"
        "\n"
        "def normalize(rows):\n"
        "    clean = prune(rows)\n"
        "    return sorted(clean)\n"
        "\n"
        "\n"
        "def summarize(rows):\n"
        "    total = normalize(rows)\n"
        "    return len(total)\n"
    ),
    "pkg/alpha.py": (
        "from pkg.beta import fetch_rows, normalize\n"
        "\n"
        "\n"
        "class Loader:\n"
        "    def __init__(self, source):\n"
        "        self.source = source\n"
        "\n"
        "    def load(self):\n"
        "        rows = fetch_rows(self.source)\n"
        "        return normalize(rows)\n"
        "\n"
        "\n"
        "class CachedLoader(Loader):\n"
        "    def load(self):\n"
        "        rows = fetch_rows(self.source)\n"
        "        return normalize(rows)\n"
        "\n"
        "\n"
        "def load_all(sources):\n"
        "    out = []\n"
        "    for source in sources:\n"
        "        out.append(Loader(source).load())\n"
        "    return out\n"
    ),
    "pkg/gamma.py": (
        "from pkg.alpha import load_all\n"
        "from pkg.beta import summarize\n"
        "\n"
        "\n"
        "def report(sources):\n"
        "    loaded = load_all(sources)\n"
        "    return summarize(loaded)\n"
    ),
    "main.py": (
        "from pkg.gamma import report\n"
        "\n"
        "\n"
        "def main():\n"
        "    return report(['a', 'b'])\n"
        "\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    ),
}


def _write(root: Path, files=None):
    for rel, text in (files or FILES).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _edge_key(edge):
    """一条边的规范形式：字段全序，seq 也排序，两个方向都不许有偶然差异。"""
    item = dict(edge)
    if isinstance(item.get("seq"), list):
        item["seq"] = sorted(item["seq"])
    return json.dumps(item, sort_keys=True, ensure_ascii=False)


def _edges(root: Path):
    payload = json.loads((root / ".codedendrite" / "relations.json").read_text(encoding="utf-8"))
    return [_edge_key(e) for e in payload.get("edges", [])]


def _failed(root: Path):
    payload = json.loads((root / ".codedendrite" / "relations.json").read_text(encoding="utf-8"))
    return list(payload.get("meta", {}).get("failed", []))


def _diff(full, inc):
    """返回 (只在全量里有, 只在增量里有)，用可读形式。"""
    fs, is_ = set(full), set(inc)
    only_full = sorted(fs - is_)
    only_inc = sorted(is_ - fs)
    return only_full, only_inc


def _run_case(tmp_path, name, edit_files, changed, expect_change=True):
    """两份同样的工程，施同一个改动，全量 vs 增量。

    `expect_change` 是防"空过"的：如果这个改动根本没让边集发生变化，那增量等于
    全量就是废话，测试必须在改完之后先证明改动确实动到了边。
    """
    full_root = tmp_path / name / "full"
    inc_root = tmp_path / name / "inc"
    for root in (full_root, inc_root):
        root.mkdir(parents=True)
        _write(root)
        generate_all_anchors(str(root))
        generate_relations(str(root))

    before = set(_edges(full_root))

    _write(full_root, edit_files)
    _write(inc_root, edit_files)

    # 真实流水线的顺序：先更新 anchor，再更新 relations
    update_anchors_for_files(str(full_root), changed_files=changed)
    update_anchors_for_files(str(inc_root), changed_files=changed)

    generate_relations(str(full_root))
    generate_relations(str(inc_root), changed_files=changed)

    full, inc = _edges(full_root), _edges(inc_root)
    # 静默回退必须让测试挂：strict dataflow 一旦抛异常，两条路都会退化成
    # "调用即数据流"，两边一模一样，比对就变成了自我印证。
    for label, root in (("full", full_root), ("inc", inc_root)):
        assert not _failed(root), "{} 侧有静默回退，比对无效：{}".format(label, _failed(root))
    if expect_change:
        assert set(full) != before, (
            "这个改动没有动到任何边，用例是空过的——夹具或改动本身失效了"
        )
    only_full, only_inc = _diff(full, inc)
    assert not only_full, (
        "增量少了边（{} 条）:\n{}".format(len(only_full), "\n".join(only_full[:6]))
    )
    assert not only_inc, (
        "增量多了边（{} 条）:\n{}".format(len(only_inc), "\n".join(only_inc[:6]))
    )
    assert full, "夹具没有产出任何边，测试本身失效"
    return len(full)


# ── 用例 ────────────────────────────────────────────────────────────────

def test_body_edit_is_equivalent(tmp_path):
    """同一文件里加一次内部调用：新边出现在 normalize -> prune 之外的那条路径上。"""
    edited = dict(FILES)
    edited["pkg/beta.py"] = FILES["pkg/beta.py"].replace(
        "    clean = prune(rows)\n    return sorted(clean)\n",
        "    clean = prune(rows)\n    trimmed = prune(clean)\n    return sorted(trimmed)\n",
    )
    assert edited["pkg/beta.py"] != FILES["pkg/beta.py"]
    _run_case(tmp_path, "body", edited, ["pkg/beta.py"])


def test_new_function_and_new_caller_is_equivalent(tmp_path):
    """beta 加一个新函数、gamma 改去调它：两个文件都变。"""
    edited = dict(FILES)
    edited["pkg/beta.py"] = FILES["pkg/beta.py"] + (
        "\n\ndef tally(rows):\n"
        "    total = normalize(rows)\n"
        "    return len(total)\n"
    )
    edited["pkg/gamma.py"] = (
        "from pkg.alpha import load_all\n"
        "from pkg.beta import tally\n"
        "\n"
        "\n"
        "def report(sources):\n"
        "    loaded = load_all(sources)\n"
        "    return tally(loaded)\n"
    )
    _run_case(tmp_path, "newfn", edited, ["pkg/beta.py", "pkg/gamma.py"])


def test_rename_across_files_is_equivalent(tmp_path):
    """beta 把 summarize 改名成 tally，gamma 跟着改：分辨率变了。"""
    edited = dict(FILES)
    edited["pkg/beta.py"] = FILES["pkg/beta.py"].replace("def summarize(", "def tally(")
    edited["pkg/gamma.py"] = FILES["pkg/gamma.py"].replace("summarize", "tally")
    _run_case(tmp_path, "rename", edited, ["pkg/beta.py", "pkg/gamma.py"])


def test_deleted_callee_removes_edge(tmp_path):
    """beta 删掉一个被 gamma 调用的函数，而 gamma 一个字都没改。

    最危险的一类：脏文件之外的那一端必须被牵进来，否则旧边会留在索引里变成幽灵。
    """
    edited = dict(FILES)
    edited["pkg/beta.py"] = FILES["pkg/beta.py"].replace(
        "def summarize(rows):\n    total = normalize(rows)\n    return len(total)\n",
        "",
    )
    _run_case(tmp_path, "delete", edited, ["pkg/beta.py"])


def test_inheritance_change_is_equivalent(tmp_path):
    """alpha 里换掉基类：inherit 边的两端都在同一个文件里。"""
    edited = dict(FILES)
    edited["pkg/alpha.py"] = FILES["pkg/alpha.py"].replace(
        "class CachedLoader(Loader):", "class CachedLoader(object):"
    )
    _run_case(tmp_path, "inherit", edited, ["pkg/alpha.py"])


def test_new_file_is_equivalent(tmp_path):
    """新增一个文件：它自己的出边要建，指向它的入边也要建。"""
    edited = dict(FILES)
    edited["pkg/delta.py"] = (
        "from pkg.beta import normalize\n"
        "\n"
        "\n"
        "def clean(rows):\n"
        "    return normalize(rows)\n"
    )
    _run_case(tmp_path, "newfile", edited, ["pkg/delta.py"])


def test_unchanged_project_is_equivalent(tmp_path):
    """什么都不改时也要相等：增量不许把旧边弄丢或重复。"""
    _run_case(tmp_path, "noop", dict(FILES), [], expect_change=False)


def test_incremental_does_not_touch_untouched_files_edges(tmp_path):
    """局部更新不许碰无关文件的边：改 beta 后，alpha 段的边必须逐条保留。"""
    full_root = tmp_path / "scope" / "full"
    inc_root = tmp_path / "scope" / "inc"
    for root in (full_root, inc_root):
        root.mkdir(parents=True)
        _write(root)
        generate_all_anchors(str(root))
        generate_relations(str(root))

    edited = dict(FILES)
    edited["pkg/beta.py"] = FILES["pkg/beta.py"] + "\n\ndef extra(rows):\n    return len(rows)\n"
    _write(full_root, edited)
    _write(inc_root, edited)
    update_anchors_for_files(str(full_root), changed_files=["pkg/beta.py"])
    update_anchors_for_files(str(inc_root), changed_files=["pkg/beta.py"])
    generate_relations(str(full_root))
    generate_relations(str(inc_root), changed_files=["pkg/beta.py"])

    alpha_edges = lambda root: sorted(  # noqa: E731
        e for e in _edges(root) if '"file": "pkg/alpha.py"' in e or 'pkg/alpha.py' in e
    )
    assert alpha_edges(full_root) == alpha_edges(inc_root)
    assert alpha_edges(inc_root), "alpha 段没有边，断言本身失效"


# ── anchor 层的等价性 ───────────────────────────────────────────────────
#
# relations 的增量是建立在"anchor 表已经是对的"这个前提上的。这一条测的是那个
# 前提本身：`update_anchors_for_files` 跑出来的 anchors.json，必须和
# `generate_all_anchors` 全量跑出来的一模一样。
#
# 190k 行的真实库上它曾经**不成立**，两处原因，都已修：
#
#   1. src/analyzer/anchors/core_anchor.py:141 调 parse_paths 没传
#      `include_python=True`。默认 False 会把 Python 文件整批跳过，
#      `_merge_parsed_anchor` 于是从来不为它们跑——增量出来的 anchor 缺
#      qualified_name / signature / imports，全量重建却有。
#   2. src/analyzer/anchors/resolve.py 里 `callers` 按 anchors 字典的插入顺序
#      追加。全量按文件走一遍，增量是"老 anchor + 改动文件的新 anchor"，
#      同一个集合排出两种顺序。
#
# 修之前：9144 个 anchor 里 38 个不一致，并顺着 relations 放大成单步增量与
# 全量重建差 25 条边、多 24 条边。

def _anchor_body(root: Path, anchor_id: str):
    payload = json.loads((root / ".codedendrite" / "anchors.json").read_text(encoding="utf-8"))
    return payload.get(anchor_id)


def test_incremental_anchors_equal_full_anchors(tmp_path):
    """增量更新出来的 anchor 必须和全量重建出来的逐字段相等。"""
    full_root = tmp_path / "anchors" / "full"
    inc_root = tmp_path / "anchors" / "inc"
    for root in (full_root, inc_root):
        root.mkdir(parents=True)
        _write(root)
        generate_all_anchors(str(root))

    edited = dict(FILES)
    edited["pkg/beta.py"] = FILES["pkg/beta.py"] + (
        "\n\ndef extra(rows):\n    return len(rows)\n"
    )
    _write(full_root, edited)
    _write(inc_root, edited)
    generate_all_anchors(str(full_root))
    update_anchors_for_files(str(inc_root), changed_files=["pkg/beta.py"])

    full = json.loads((full_root / ".codedendrite" / "anchors.json").read_text(encoding="utf-8"))
    inc = json.loads((inc_root / ".codedendrite" / "anchors.json").read_text(encoding="utf-8"))
    assert set(full) == set(inc), "两侧 anchor 集合不同"
    drift = {}
    for anchor_id in full:
        if json.dumps(full[anchor_id], sort_keys=True) != json.dumps(inc[anchor_id], sort_keys=True):
            drift[anchor_id] = sorted(
                f for f in set(full[anchor_id]) | set(inc[anchor_id])
                if json.dumps(full[anchor_id].get(f), sort_keys=True)
                != json.dumps(inc[anchor_id].get(f), sort_keys=True)
            )
    assert not drift, "增量 anchor 与全量不一致：{}".format(drift)
