"""
build_map 重设计
================
替换 context_builder/builder.py 里的以下方法：
  - build_map()
  - _build_dataflow_section()
  - _build_risk_section()
  - _build_error_entry_section()
  - _build_inheritance_section()
  - _strip_anchors()

直接把这个文件的内容粘贴进 builder.py，
找到对应方法替换方法体即可。
"""

import re
from pathlib import Path


# ── 常量 ──────────────────────────────────────────────────────────────────────

BUILTIN_NOISE = {
    "print","append","get","len","str","int","list","dict","set","type",
    "range","enumerate","zip","map","filter","isinstance","hasattr",
    "getattr","setattr","open","any","all","sorted","reversed","join",
    "split","format","update","extend","items","values","keys","pop",
    "insert","read","write","close","encode","decode","replace","strip",
}


# ── build_map 主方法 ──────────────────────────────────────────────────────────

def build_map(self, budget_tokens: int = 2000, mode: str = "llm") -> str:
    """
    生成高密度项目情报简报。

    mode='llm'   → 含 anchor:// 引用，LLM 可调用 expand()
    mode='human' → 纯符号名，锚点对人透明
    """
    self._ensure_loaded()

    sections = []

    s1 = self._build_dataflow_section()
    if s1: sections.append(s1)

    s2 = self._build_risk_section()
    if s2: sections.append(s2)

    s3 = self._build_error_entry_section()
    if s3: sections.append(s3)

    s4 = self._build_inheritance_section()
    if s4: sections.append(s4)

    raw = "\n\n".join(sections)

    if mode == "human":
        return self._strip_anchors(raw)
    return raw


# ── Section 1: 数据流主干 ──────────────────────────────────────────────────────

def _build_dataflow_section(self) -> str:
    try:
        from relate.api.relations import load_relations
        data = load_relations(str(self.root))
        edges = data["edges"]
    except Exception:
        return ""

    df_edges = [e for e in edges if e["edge_type"] == "dataflow"]
    if not df_edges:
        return ""

    # 找起点：from出现但不作为to的节点
    all_to  = {e["to_id"]   for e in df_edges}
    all_from = {e["from_id"] for e in df_edges}
    sources = all_from - all_to

    # 过滤掉 unknown:: 和 impact:: 节点
    sources = {s for s in sources if not s.startswith(("unknown::", "impact::", "external::", "override::"))}

    if not sources:
        # fallback：取被引用最多的起点
        from collections import Counter
        cnt = Counter(e["from_id"] for e in df_edges)
        sources = {cnt.most_common(1)[0][0]}

    lines = ["## 数据流主干"]

    for src in list(sources)[:3]:
        chain = self._trace_chain(src, df_edges, max_depth=5)
        if len(chain) < 2:
            continue
        lines.append(self._format_chain(chain))

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _trace_chain(self, start: str, edges: list, max_depth: int = 5, visited: set = None) -> list:
    if visited is None:
        visited = set()
    if start in visited or max_depth == 0:
        return [start]
    visited.add(start)
    nexts = [
        e["to_id"] for e in edges
        if e["from_id"] == start
        and not e["to_id"].startswith(("unknown::", "impact::", "external::", "override::"))
    ]
    if not nexts:
        return [start]
    return [start] + self._trace_chain(nexts[0], edges, max_depth - 1, visited)


def _format_chain(self, chain: list) -> str:
    parts = []
    for node in chain:
        sym = node.split("::")[-1]
        parts.append("[{}](anchor://{})".format(sym, node))
    return "  " + " → ".join(parts)


# ── Section 2: 高风险节点 ──────────────────────────────────────────────────────

def _build_risk_section(self) -> str:
    try:
        from relate.api.relations import load_relations
        data = load_relations(str(self.root))
        edges = data["edges"]
    except Exception:
        return ""

    impact_edges = [e for e in edges if e["edge_type"] == "impact"]
    if not impact_edges:
        return ""

    # 按依赖数量排序
    impact_edges.sort(key=lambda e: e.get("count", 0), reverse=True)

    lines = ["## 高风险节点（改了影响最大）"]
    for e in impact_edges[:5]:
        node = e["to_id"]
        if node.startswith(("unknown::", "external::")):
            continue
        sym = node.split("::")[-1]
        dependents = e.get("dependents", [])
        count = e.get("count", len(dependents))
        lines.append(
            "  [{}](anchor://{})  被{}个模块依赖：{}".format(
                sym, node, count, " / ".join(dependents[:4])
            )
        )

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


# ── Section 3: 报错入口 ────────────────────────────────────────────────────────

def _build_error_entry_section(self) -> str:
    try:
        from relate.api.relations import load_relations, get_node_edges
        data = load_relations(str(self.root))
    except Exception:
        return ""

    # 找 smart_analyze 的下游
    ENTRY_CANDIDATES = [
        "api/smart.py::smart_analyze",
        "api\\smart.py::smart_analyze",
    ]

    entry_id = None
    all_ids = {e["from_id"] for e in data["edges"]} | {e["to_id"] for e in data["edges"]}
    for c in ENTRY_CANDIDATES:
        if c in all_ids:
            entry_id = c
            break

    lines = ["## 报错入口"]
    lines.append("  TypeError / KeyError / AttributeError")

    if entry_id:
        sym = entry_id.split("::")[-1]
        lines.append("    → [{}](anchor://{})".format(sym, entry_id))
        try:
            out_edges = get_node_edges(entry_id, str(self.root), direction="out", edge_type="call")
            for e in out_edges[:3]:
                to = e["to_id"]
                if to.startswith(("unknown::", "external::")):
                    continue
                to_sym = to.split("::")[-1]
                lines.append("    → [{}](anchor://{})".format(to_sym, to))
        except Exception:
            pass
    else:
        lines.append("    → smart_analyze（未在 relations 中找到，检查 api/smart.py）")

    return "\n".join(lines)


# ── Section 4: 继承主链 ────────────────────────────────────────────────────────

def _build_inheritance_section(self) -> str:
    try:
        from relate.api.relations import load_relations
        data = load_relations(str(self.root))
        edges = [e for e in data["edges"] if e["edge_type"] == "inherit"]
    except Exception:
        return ""

    if not edges:
        return ""

    # 建父子关系
    children_of = {}  # parent → [children]
    for e in edges:
        parent = e["to_id"]
        child  = e["from_id"]
        if parent.startswith(("external::", "override::", "unknown::")):
            continue
        if parent not in children_of:
            children_of[parent] = []
        children_of[parent].append(child)

    if not children_of:
        return ""

    # 找根节点（不作为child出现的parent）
    all_children = {e["from_id"] for e in edges}
    roots = [p for p in children_of if p not in all_children]

    lines = ["## 继承主链"]
    for root in roots[:4]:
        children = children_of.get(root, [])
        if not children:
            continue
        root_sym = root.split("::")[-1]
        lines.append(
            "  [{}](anchor://{})  ← {} 个子类".format(root_sym, root, len(children))
        )
        for c in children[:3]:
            c_sym = c.split("::")[-1]
            lines.append("    └ [{}](anchor://{})".format(c_sym, c))

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


# ── _strip_anchors: human 模式 ─────────────────────────────────────────────────

def _strip_anchors(self, text: str) -> str:
    """把 [符号名](anchor://...) 替换成 符号名"""
    return re.sub(r'\[([^\]]+)\]\(anchor://[^)]+\)', r'\1', text)


# ══════════════════════════════════════════════════════════════════════════════
# 验证脚本（直接跑这个文件可以验证效果）
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    import sys

    ROOT = os.environ.get("CDD_ROOT") or str(Path(__file__).resolve().parents[1])
    sys.path.insert(0, ROOT)

    from synth.context_builder.builder import ContextBuilder

    cb = ContextBuilder(ROOT)

    # 临时把新方法绑定进去
    import types
    cb.build_map                    = types.MethodType(build_map, cb)
    cb._build_dataflow_section      = types.MethodType(_build_dataflow_section, cb)
    cb._build_risk_section          = types.MethodType(_build_risk_section, cb)
    cb._build_error_entry_section   = types.MethodType(_build_error_entry_section, cb)
    cb._build_inheritance_section   = types.MethodType(_build_inheritance_section, cb)
    cb._trace_chain                 = types.MethodType(_trace_chain, cb)
    cb._format_chain                = types.MethodType(_format_chain, cb)
    cb._strip_anchors               = types.MethodType(_strip_anchors, cb)

    print("=" * 60)
    print("LLM 模式（含 anchor:// 引用）")
    print("=" * 60)
    result_llm = cb.build_map(mode="llm")
    print(result_llm)

    print()
    print("=" * 60)
    print("Human 模式（纯符号名）")
    print("=" * 60)
    result_human = cb.build_map(mode="human")
    print(result_human)

    print()
    print("=" * 60)
    print("验证结果")
    print("=" * 60)
    assert "##" in result_llm,            "❌ 没有section标题"
    assert "anchor://" in result_llm,     "❌ LLM模式缺少anchor引用"
    assert "anchor://" not in result_human, "❌ Human模式不应含anchor引用"
    assert "print" not in result_llm,    "❌ 出现了builtin噪音"
    print("✅ 验证通过")
