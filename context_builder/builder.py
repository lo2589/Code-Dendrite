"""
builder.py — 核心压缩器

把项目的锚点数据库、继承链、调用图压缩成
AI 能在单次上下文内理解的导航地图。

压缩策略（按重要性排序）：
  1. 入口点图      — 从 main/entry 出发的顶层调用链
  2. 模块职责      — 每个模块一行，对外接口列表
  3. 继承摘要      — 只显示有 override/多继承/深链的类
  4. 热点符号      — 被引用次数最多的前 N 个
  5. 精简符号索引  — 名字 + 签名 + 文件位置，不含 code
"""

import json
import os
from pathlib import Path
from typing import Optional
from collections import defaultdict


class ContextBuilder:
    """
    将项目锚点数据压缩为 AI 可用的上下文地图。

    参数：
        project_root: 项目根目录
        anchors_path: anchors.json 路径（默认 project_root/.codedendrite/anchors.json）
        max_tokens:   输出 token 预算（粗略按字符数 /4 估算）
    """

    def __init__(
        self,
        project_root: str,
        anchors_path: Optional[str] = None,
        max_tokens: int = 2000,
    ):
        self.root = Path(project_root)
        self.anchors_path = Path(anchors_path) if anchors_path else (
            self.root / ".codedendrite" / "anchors.json"
        )
        self.max_tokens = max_tokens
        self._anchors: dict = {}
        self._loaded = False

    # ── 公开接口 ──────────────────────────────────────────────

    def build_map(self, budget_tokens: Optional[int] = None,
                  mode: str = "llm") -> str:
        """
        生成压缩地图文本，直接喂给 AI system prompt 或 user message。

        mode='llm'   — 带 anchor:// 引用（LLM 可调用 expand()）
        mode='human' — 去掉 anchor:// 超链接，纯文本，人类可读

        优先使用 relations.json 数据（4 节）：
          数据流链路 / 高风险节点 / 入口点 / 继承摘要
        若 relations.json 不存在，降级到旧有 5 节：
          Entry Points / Module Responsibilities / Key Inheritance /
          Hot Symbols / Symbol Index
        """
        budget = budget_tokens or self.max_tokens
        self._ensure_loaded()

        sections = []
        remaining = budget * 4  # 粗略字符预算

        # 标题
        header = "# ProjectMap: {}\n\n".format(self.root.name)
        sections.append(header)
        remaining -= len(header)

        module_tree_section = self._build_module_tree_section(
            char_budget=max(remaining // 3, 300)
        )
        if module_tree_section:
            sections.append(module_tree_section)
            remaining -= len(module_tree_section)

        # 尝试基于 relations.json 的新 4 节
        has_relations = (self.root / ".codedendrite" / "relations.json").exists()
        if has_relations:
            for builder_fn in (
                self._build_dataflow_section,
                self._build_risk_section,
                self._build_relations_entry_section,
                self._build_relations_inheritance_section,
            ):
                s = builder_fn()
                if s:
                    sections.append(s)
                    remaining -= len(s)
        else:
            # 降级：旧有 5 节
            entry_section = self._build_entry_section()
            if len(entry_section) < remaining * 0.25:
                sections.append(entry_section)
                remaining -= len(entry_section)

            module_section = self._build_module_section()
            if len(module_section) < remaining * 0.35:
                sections.append(module_section)
                remaining -= len(module_section)

            inherit_section = self._build_inheritance_section()
            if len(inherit_section) < remaining * 0.25:
                sections.append(inherit_section)
                remaining -= len(inherit_section)

            hot_section = self._build_hotspot_section(top_n=10)
            if len(hot_section) < remaining * 0.3:
                sections.append(hot_section)
                remaining -= len(hot_section)

            index_section = self._build_symbol_index(char_budget=remaining)
            sections.append(index_section)

        raw = "\n".join(sections)
        if mode == "human":
            return self._strip_anchors(raw)
        return raw

    def build_debug_map(self, entry_function: str) -> str:
        """
        针对 Debug 场景的专用地图：以某个入口函数为中心，
        只展示该调用链相关的符号和依赖。
        """
        self._ensure_loaded()
        lines = [f"# Debug Map: {entry_function}\n"]

        # 找到入口锚点
        entry = self._find_anchor(entry_function)
        if not entry:
            lines.append(f"⚠ 未找到符号: {entry_function}\n")
            return "\n".join(lines)

        module = self._find_module_for_debug(entry_function)
        if module:
            lines.append(self._render_debug_module_section(module))

        lines.append(f"## 入口\n{entry['file']}:{entry.get('line_start', '?')}\n")

        # 找调用链（从 dataFlow 结果中读，若没有则降级到引用计数）
        callees = self._get_callees(entry_function)
        if callees:
            lines.append("## 调用链")
            for c in callees:
                lines.append(f"  → {c}")
            lines.append("")

        # 相关锚点
        related = self._get_related_anchors(entry_function, module=module)
        if related:
            lines.append("## 相关符号")
            for r in related:
                sig = r.get("metadata", {}).get("signature", r["name"])
                lines.append(f"  {sig}   {r['file']}:{r.get('line_start', '?')}")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        """返回项目统计，用于快速了解规模。"""
        self._ensure_loaded()
        by_lang = defaultdict(int)
        by_cat = defaultdict(int)
        for a in self._anchors.values():
            by_lang[a.get("language", "unknown")] += 1
            by_cat[a.get("category", "unknown")] += 1
        return {
            "total_anchors": len(self._anchors),
            "by_language": dict(by_lang),
            "by_category": dict(by_cat),
        }

    # ── 私有：数据加载 ────────────────────────────────────────

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            from api.anchors import load_anchors
            raw = load_anchors(str(self.root))
            # 转换为 builder 内部期望的格式（兼容旧字段名）
            sym_type_to_cat = {
                "function": "functions",
                "class": "classes",
                "method": "methods",
            }
            self._anchors = {}
            for k, a in raw.items():
                self._anchors[k] = {
                    "name": a.symbol,
                    "symbol": a.symbol,        # 与 name 同值，供新方法使用
                    "symbol_type": a.symbol_type,
                    "file": a.file,
                    "line_start": a.line_start,
                    "line_end": a.line_end,
                    "hash": a.hash,
                    "description": a.description,
                    "category": sym_type_to_cat.get(a.symbol_type, a.symbol_type),
                    "language": a.language,
                    "code": a.code,
                    "callers": a.callers,      # 谁调用了我（反向引用）
                    "metadata": {
                        "calls": [
                            c.get("target", c) if isinstance(c, dict) else c
                            for c in a.callees
                        ],
                        "parameters": [v.get("name", "") for v in a.inputs],
                        "return_type": [v.get("name", "") for v in a.outputs],
                        "bases": a.parent_classes,
                        "inheritance_depth": len(a.mro),
                    },
                }
        except FileNotFoundError:
            self._anchors = {}   # anchors.json 不存在时返回空，不报错
        self._loaded = True

    def _find_anchor(self, name: str) -> Optional[dict]:
        """按符号名模糊查找锚点。"""
        # 精确匹配
        for k, v in self._anchors.items():
            if v.get("name") == name:
                return v
        # 后缀匹配
        for k, v in self._anchors.items():
            if k.endswith(f".{name}"):
                return v
        return None

    def _get_callees(self, func_name: str) -> list:
        """从锚点 metadata 中提取调用列表。"""
        anchor = self._find_anchor(func_name)
        if not anchor:
            return []
        return anchor.get("metadata", {}).get("calls", [])

    def _get_related_anchors(self, func_name: str, max_n: int = 8, module: Optional[dict] = None) -> list:
        """找和某个函数相关的锚点，优先限制在所属模块。"""
        anchor = self._find_anchor(func_name)
        if not anchor:
            return []
        if module:
            member_ids = set(module.get("member_symbols", []))
            related = []
            for symbol_id in member_ids:
                candidate = self._anchors.get(symbol_id)
                if not candidate:
                    continue
                if candidate.get("name") == anchor.get("name"):
                    continue
                related.append(candidate)
            if related:
                related.sort(key=lambda item: (item.get("file", ""), item.get("line_start", 0)))
                return related[:max_n]
        file = anchor.get("file", "")
        related = [
            v for v in self._anchors.values()
            if v.get("file") == file and v.get("name") != func_name
        ]
        return related[:max_n]

    def _find_module_for_debug(self, entry_function: str) -> Optional[dict]:
        try:
            from api.module_tree import find_module_for_symbol
            return find_module_for_symbol(entry_function, str(self.root))
        except Exception:
            return None

    def _render_debug_module_section(self, module: dict) -> str:
        title = module.get("name", module.get("id", "module"))
        responsibility = (
            module.get("responsibility")
            or module.get("responsibility_hint")
            or "module summary pending"
        )
        entry_names = [
            item.get("symbol_id", "").split("::")[-1]
            for item in module.get("entry_functions", [])
            if item.get("symbol_id")
        ]
        lines = [
            "## Module\n",
            f"{title}: {responsibility}\n",
        ]
        if entry_names:
            lines.append("entries: " + " / ".join(entry_names[:3]) + "\n")
        edges = module.get("cross_module_edges", [])
        if edges:
            preview = []
            for edge in edges[:2]:
                preview.append(
                    "{} [{} x{}]".format(
                        edge.get("to_module", "?"),
                        edge.get("edge_type", "?"),
                        edge.get("count", 0),
                    )
                )
            lines.append("depends on: " + "; ".join(preview) + "\n")
        lines.append("")
        return "".join(lines)

    # ── 私有：各节构建 ────────────────────────────────────────

    # ── 入口点常量 ──────────────────────────────────────────────
    _ENTRY_PRIORITY_PATHS = ("api/", "api\\", "workflow")
    _ENTRY_EXCLUDE_PREFIXES = ("_", "test_", "demo", "debug", "banner", "section")

    def _get_entry_points(self) -> list:
        """优先返回 api/ 层的公开函数作为入口点，降级到根层非私有函数。"""
        primary = []
        fallback = []
        for anchor in self._anchors.values():
            sym = anchor.get("symbol", "")
            f   = anchor.get("file", "")
            typ = anchor.get("symbol_type", "")
            if not sym or sym.startswith(self._ENTRY_EXCLUDE_PREFIXES):
                continue
            if typ == "class":
                continue
            if any(p in f for p in self._ENTRY_PRIORITY_PATHS):
                primary.append(anchor)
            elif typ == "function" and "/" not in f.replace("\\", "/").strip("/"):
                fallback.append(anchor)
        entries = primary if primary else fallback
        return entries[:6]

    def _build_entry_section(self) -> str:
        """识别入口点，优先展示 api/ 层公开函数。"""
        lines = ["## Entry Points\n"]
        entries = self._get_entry_points()
        if not entries:
            lines.append("  （未检测到明确入口点，请手动指定）\n")
        else:
            for a in entries:
                sym = a.get("symbol", "")
                callees = a.get("metadata", {}).get("calls", [])
                # 过滤掉 callees 里的内置噪音
                clean = [c for c in callees if c not in self._BUILTIN_NAMES][:3]
                chain = " → ".join([sym] + clean) if clean else sym
                lines.append(f"  {chain}\n")
        return "".join(lines) + "\n"

    # ── 模块职责常量 ────────────────────────────────────────────
    _MODULE_EXCLUDE = {"(root)", "debug", "tests", "examples", "__pycache__", "docs"}
    _MODULE_SYMBOL_LIMIT = 5
    _MODULE_SYMBOL_NOISE = frozenset({
        "test_", "demo", "banner", "section", "main",
    })

    def _get_module_responsibilities(self) -> dict:
        """按第一级目录归类，每个模块展示代表性公开函数/类。"""
        from pathlib import PurePosixPath
        modules = {}
        for anchor in self._anchors.values():
            sym = anchor.get("symbol", "")
            f   = anchor.get("file", "").replace("\\", "/")
            typ = anchor.get("symbol_type", "")
            if not sym or sym.startswith("_"):
                continue
            if any(sym.startswith(n) for n in self._MODULE_SYMBOL_NOISE):
                continue
            # 只收函数和类（method 名带 ClassName. 前缀，太冗余）
            if typ == "method":
                continue
            parts = PurePosixPath(f).parts
            module = parts[0] if len(parts) > 1 else "(root)"
            if module in self._MODULE_EXCLUDE:
                continue
            if module not in modules:
                modules[module] = []
            if len(modules[module]) < self._MODULE_SYMBOL_LIMIT:
                modules[module].append(sym)
        return {k: v for k, v in sorted(modules.items()) if v}

    def _build_module_section(self) -> str:
        """按第一级目录分组，每个模块一行摘要。"""
        lines = ["## Module Responsibilities\n"]
        modules = self._get_module_responsibilities()
        if not modules:
            lines.append("  （暂无模块数据）\n")
        else:
            for module, symbols in modules.items():
                lines.append(f"  {module:<24} {', '.join(symbols)}\n")
        return "".join(lines) + "\n"

    def _build_inheritance_section(self) -> str:
        """从锚点 metadata 中提取继承信息，只展示有意义的链。"""
        lines = ["## Key Inheritance\n"]
        seen = set()
        for anchor in self._anchors.values():
            meta = anchor.get("metadata", {})
            bases = meta.get("bases", [])
            if not bases:
                continue
            name = anchor.get("name", "")
            if name in seen:
                continue
            seen.add(name)
            depth = meta.get("inheritance_depth", len(bases))
            # 只展示深度 >= 2 或多重继承
            if depth >= 2 or len(bases) > 1:
                base_str = ", ".join(bases[:3])
                lines.append(f"  {name}({base_str})  depth={depth}\n")

        if len(lines) == 1:
            lines.append("  （未检测到深层继承，或继承数据尚未写入锚点）\n")

        return "".join(lines) + "\n"

    # ── 热点常量 ────────────────────────────────────────────────
    _BUILTIN_NAMES = frozenset({
        "print", "append", "get", "len", "str", "int", "float", "bool",
        "list", "dict", "set", "tuple", "type", "range", "enumerate",
        "zip", "map", "filter", "isinstance", "issubclass", "hasattr",
        "getattr", "setattr", "open", "any", "all", "sorted", "reversed",
        "iter", "next", "super", "object", "staticmethod", "classmethod", "property",
        "join", "split", "format", "strip", "replace", "update", "extend",
        "items", "values", "keys", "add", "remove", "pop", "insert",
        "read", "write", "close", "encode", "decode",
        "add_argument", "parse_args", "Path", "exists", "mkdir", "run",
        "json", "os", "sys", "re", "logging", "copy", "deepcopy",
        "lower", "upper", "hash", "id", "vars", "dir", "abs", "round", "sum",
        "max", "min", "repr",
    })
    _HOT_MIN_CALLERS = 2    # 至少被几处调用才算热点
    _HOT_SYMBOL_NOISE = frozenset({"test_", "demo", "debug", "banner", "section"})

    def _get_hot_symbols(self, top_n: int = 10) -> list:
        """
        返回被频繁调用的项目内部符号。
        使用 callers 字段（谁调用了我），比统计 callees 更准确。
        """
        hot = []
        for anchor in self._anchors.values():
            sym = anchor.get("symbol", "")
            if not sym or sym in self._BUILTIN_NAMES:
                continue
            if sym.startswith("_"):
                continue
            if any(sym.startswith(n) for n in self._HOT_SYMBOL_NOISE):
                continue
            caller_count = len(anchor.get("callers", []))
            if caller_count < self._HOT_MIN_CALLERS:
                continue
            hot.append((
                caller_count,
                sym,
                anchor.get("file", ""),
                anchor.get("line_start", 0),
            ))
        hot.sort(reverse=True)
        return hot[:top_n]

    def _build_hotspot_section(self, top_n: int = 10) -> str:
        """展示被频繁调用的项目内部符号。"""
        lines = ["## Hot Symbols\n"]
        hot = self._get_hot_symbols(top_n)
        if not hot:
            # 降级：用 callees 反向统计（callers 字段为空时兜底）
            ref_count = defaultdict(int)  # type: ignore[var-annotated]
            known = {a.get("symbol") for a in self._anchors.values()}
            for anchor in self._anchors.values():
                for c in anchor.get("metadata", {}).get("calls", []):
                    if c not in self._BUILTIN_NAMES and c in known:
                        ref_count[c] += 1
            top_fb = sorted(ref_count.items(), key=lambda x: x[1], reverse=True)[:top_n]
            if top_fb:
                for name, count in top_fb:
                    a = self._find_anchor(name)
                    loc = f"{a['file']}:L{a.get('line_start','?')}" if a else "?"
                    lines.append(f"  {name:<40} 被{count}处引用  {loc}\n")
            else:
                lines.append("  （暂无项目内部调用关系数据）\n")
        else:
            for count, sym, f, line in hot:
                loc = f"{f}:L{line}" if f else "?"
                lines.append(f"  {sym:<40} 被{count}处引用  {loc}\n")
        return "".join(lines) + "\n"

    def _build_module_tree_section(self, char_budget: int = 800) -> str:
        """Section 0: consume module_tree.json when available."""
        try:
            from api.module_tree import load_module_tree
            data = load_module_tree(str(self.root))
        except Exception:
            return ""

        modules = data.get("semantic_modules", [])
        if not modules:
            return ""

        lines = ["## Project Modules\n"]
        used = len("".join(lines))
        for module in modules:
            title = module.get("name", module.get("id", "module"))
            responsibility = (
                module.get("responsibility")
                or module.get("responsibility_hint")
                or "module summary pending"
            )
            entry_ids = [
                entry.get("symbol_id", "")
                for entry in module.get("entry_functions", [])
                if entry.get("symbol_id")
            ][:3]
            entries = ", ".join(item.split("::")[-1] for item in entry_ids) or "-"
            edge_lines = []
            for edge in module.get("cross_module_edges", [])[:2]:
                pair_preview = ""
                pairs = edge.get("top_pairs", [])
                if pairs:
                    left = pairs[0][0].split("::")[-1]
                    right = pairs[0][1].split("::")[-1]
                    pair_preview = f" via {left}->{right}"
                edge_lines.append(
                    "{} [{} x{}{}]".format(
                        edge.get("to_module", "?"),
                        edge.get("edge_type", "?"),
                        edge.get("count", 0),
                        pair_preview,
                    )
                )
            depends = "; ".join(edge_lines) if edge_lines else "-"
            block = (
                f"{title}: {responsibility}\n"
                f"  entries: {entries}\n"
                f"  depends on: {depends}\n"
            )
            if used + len(block) > char_budget:
                break
            lines.append(block)
            used += len(block)

        return "".join(lines) + "\n"

    # ── 基于 relations.json 的新四节 ──────────────────────────

    def _build_dataflow_section(self) -> str:
        """数据流主干：过滤噪音节点，从真正源头沿 dataflow 边展 5 跳。"""
        try:
            from api.relations import load_relations
            data = load_relations(str(self.root))
            edges = data["edges"]
        except Exception:
            return ""

        df_edges = [e for e in edges if e["edge_type"] == "dataflow"]
        if not df_edges:
            return ""

        all_to   = {e["to_id"]   for e in df_edges}
        all_from = {e["from_id"] for e in df_edges}
        sources  = all_from - all_to
        sources  = {s for s in sources if not s.startswith(
            ("unknown::", "impact::", "external::", "override::"))}

        if not sources:
            from collections import Counter
            cnt = Counter(e["from_id"] for e in df_edges)
            sources = {cnt.most_common(1)[0][0]}

        lines = ["## 数据流主干\n"]
        for src in list(sources)[:3]:
            chain = self._trace_chain(src, df_edges, max_depth=5)
            if len(chain) < 2:
                continue
            lines.append(self._format_chain(chain) + "\n")

        if len(lines) == 1:
            return ""
        return "".join(lines) + "\n"

    def _trace_chain(self, start, edges, max_depth=5, visited=None):
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

    def _format_chain(self, chain):
        parts = []
        for node in chain:
            sym = node.split("::")[-1]
            parts.append("[{}](anchor://{})".format(sym, node))
        return "  " + " → ".join(parts)

    def _build_risk_section(self) -> str:
        """高风险节点：impact 边，显示具体依赖数量和模块名。"""
        try:
            from api.relations import load_relations
            data = load_relations(str(self.root))
            impact_edges = [e for e in data["edges"] if e["edge_type"] == "impact"]
        except Exception:
            return ""

        if not impact_edges:
            return ""

        impact_edges.sort(key=lambda e: e.get("count", 0), reverse=True)

        lines = ["## 高风险节点（改了影响最大）\n"]
        for e in impact_edges[:5]:
            node = e["to_id"]
            if node.startswith(("unknown::", "external::")):
                continue
            sym        = node.split("::")[-1]
            dependents = e.get("dependents", [])
            count      = e.get("count", len(dependents))
            lines.append("  [{}](anchor://{})  被{}个模块依赖：{}\n".format(
                sym, node, count, " / ".join(dependents[:4])))

        if len(lines) == 1:
            return ""
        return "".join(lines) + "\n"

    def _build_relations_entry_section(self) -> str:
        """报错入口：展示 smart_analyze 及其直接下游调用链。"""
        try:
            from api.relations import load_relations, get_node_edges
            data = load_relations(str(self.root))
        except Exception:
            return ""

        ENTRY_CANDIDATES = [
            "api/smart.py::smart_analyze",
            "api\\smart.py::smart_analyze",
        ]
        all_ids = {e["from_id"] for e in data["edges"]} | {e["to_id"] for e in data["edges"]}
        entry_id = next((c for c in ENTRY_CANDIDATES if c in all_ids), None)

        lines = ["## 报错入口\n", "  TypeError / KeyError / AttributeError\n"]
        if entry_id:
            sym = entry_id.split("::")[-1]
            lines.append("    → [{}](anchor://{})\n".format(sym, entry_id))
            try:
                out_edges = get_node_edges(entry_id, str(self.root), direction="out", edge_type="call")
                for e in out_edges[:3]:
                    to = e["to_id"]
                    if to.startswith(("unknown::", "external::")):
                        continue
                    to_sym = to.split("::")[-1]
                    lines.append("    → [{}](anchor://{})\n".format(to_sym, to))
            except Exception:
                pass
        else:
            lines.append("    → smart_analyze\n")

        return "".join(lines) + "\n"

    def _build_relations_inheritance_section(self) -> str:
        """继承主链：从 relations.json 读 inherit 边，展示根节点及子类。"""
        try:
            from api.relations import load_relations
            data = load_relations(str(self.root))
            edges = [e for e in data["edges"] if e["edge_type"] == "inherit"]
        except Exception:
            return ""

        if not edges:
            return ""

        children_of = {}
        for e in edges:
            parent = e["to_id"]
            child  = e["from_id"]
            if parent.startswith(("external::", "override::", "unknown::")):
                continue
            children_of.setdefault(parent, []).append(child)

        if not children_of:
            return ""

        all_children = {e["from_id"] for e in edges}
        roots = [p for p in children_of if p not in all_children]

        lines = ["## 继承主链\n"]
        shown = 0
        for root_node in roots[:4]:
            children = children_of.get(root_node, [])
            if not children:
                continue
            root_sym = root_node.split("::")[-1]
            lines.append("  [{}](anchor://{})  ← {} 个子类\n".format(
                root_sym, root_node, len(children)))
            for c in children[:3]:
                sym = c.split("::")[-1]
                lines.append("    └ [{}](anchor://{})\n".format(sym, c))
            shown += 1

        if shown == 0:
            return ""
        return "".join(lines) + "\n"

    # ── _strip_anchors（human 模式去掉超链接）──────────────────

    def _strip_anchors(self, text: str) -> str:
        """把 [符号名](anchor://...) 替换为 符号名（human 模式用）。"""
        import re
        return re.sub(r'\[([^\]]+)\]\(anchor://[^)]+\)', r'\1', text)

    # ── Symbol Index ──────────────────────────────────────────

    def _build_symbol_index(self, char_budget: int = 4000) -> str:
        """精简符号索引：名字 + 签名 + 位置，不含 code。"""
        lines = ["## Symbol Index\n"]
        used = len(lines[0])

        # 优先级：函数 > 类 > 方法 > 其他
        priority = {"functions": 0, "classes": 1, "methods": 2}
        sorted_anchors = sorted(
            self._anchors.values(),
            key=lambda a: priority.get(a.get("category", ""), 9)
        )

        for anchor in sorted_anchors:
            name = anchor.get("name", "")
            if name.startswith("_") and not name.startswith("__"):
                continue  # 跳过私有方法
            meta = anchor.get("metadata", {})
            params = ", ".join(meta.get("parameters", []))
            sig = f"{name}({params})"
            file = anchor.get("file", "?")
            line = anchor.get("line_start", "?")
            entry = f"  {sig:<50} {file}:L{line}\n"

            if used + len(entry) > char_budget:
                lines.append(f"  ... （还有更多符号，用 expand(name) 查询）\n")
                break
            lines.append(entry)
            used += len(entry)

        return "".join(lines)
