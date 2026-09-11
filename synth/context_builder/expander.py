"""
expander.py — 按需展开符号

AI 拿到压缩地图后，需要某个符号的具体实现时调用此模块。
精准返回锚点 code，不返回整个文件。

用法：
    expander = SymbolExpander(anchors_path="...", project_root="...")
    code = expander.expand("validate_user")
    context = expander.expand_with_context("validate_user", lines_around=10)
"""

import json
from pathlib import Path
from typing import Optional, List


class SymbolExpander:
    """
    精准展开单个符号的代码。

    这是 AI 第二步调用的接口：
      第一步：context_builder.build_map() 得到导航地图
      第二步：expander.expand(name) 得到具体实现
    """

    def __init__(self, project_root: str, anchors_path: Optional[str] = None):
        self.root = Path(project_root)
        self.anchors_path = Path(anchors_path) if anchors_path else (
            self.root / ".codedendrite" / "anchors.json"
        )
        self._anchors: dict = {}
        self._loaded = False

    def expand(self, symbol_name: str) -> str:
        """
        返回符号的完整代码。

        优先从锚点的 code 字段返回（已存储），
        若不存在则从源文件按行号切片读取。
        """
        self._ensure_loaded()
        anchor = self._find(symbol_name)
        if not anchor:
            return f"# 未找到符号: {symbol_name}\n# 请尝试 search('{symbol_name}') 查看候选"

        # 优先用已存储的 code
        if anchor.get("code"):
            return self._format_result(anchor, anchor["code"])

        # 降级：从源文件按行号读取
        return self._read_from_file(anchor)

    def expand_with_context(self, symbol_name: str, lines_around: int = 5) -> str:
        """
        展开符号代码，并附带上下文行（调用者理解用）。
        """
        self._ensure_loaded()
        anchor = self._find(symbol_name)
        if not anchor:
            return f"# 未找到符号: {symbol_name}"

        file_path = self.root / anchor.get("file", "")
        if not file_path.exists():
            return self.expand(symbol_name)

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        start = max(0, anchor.get("line_start", 1) - 1 - lines_around)
        end = min(len(all_lines), anchor.get("line_end", 1) + lines_around)

        snippet = "".join(all_lines[start:end])
        header = (
            f"# {anchor['name']}  {anchor['file']}:"
            f"L{anchor.get('line_start')}–L{anchor.get('line_end')}\n"
            f"# （含前后 {lines_around} 行上下文）\n\n"
        )
        return header + snippet

    def search(self, keyword: str, top_n: int = 5) -> List[dict]:
        """
        模糊搜索符号，返回候选列表（名字 + 位置 + 简要描述）。
        """
        self._ensure_loaded()
        keyword = keyword.lower()
        results = []
        for anchor in self._anchors.values():
            name = anchor.get("name", "").lower()
            desc = anchor.get("description", "").lower()
            if keyword in name or keyword in desc:
                results.append({
                    "name": anchor["name"],
                    "file": anchor.get("file", "?"),
                    "line": anchor.get("line_start", "?"),
                    "category": anchor.get("category", "?"),
                    "description": anchor.get("description", ""),
                })
        # 精确匹配优先
        results.sort(key=lambda r: (0 if keyword == r["name"].lower() else 1))
        return results[:top_n]

    def get_callers(self, symbol_name: str) -> List[str]:
        """
        找出所有调用了该符号的函数（反向引用）。
        """
        self._ensure_loaded()
        callers = []
        for anchor in self._anchors.values():
            calls = anchor.get("metadata", {}).get("calls", [])
            if symbol_name in calls or any(symbol_name in c for c in calls):
                callers.append(anchor.get("name", "?"))
        return callers

    def get_anchor_info(self, symbol_name: str) -> Optional[dict]:
        """
        返回符号的完整锚点信息（不含 code，避免过大）。
        """
        self._ensure_loaded()
        anchor = self._find(symbol_name)
        if not anchor:
            return None
        return {k: v for k, v in anchor.items() if k != "code"}

    # ── 私有 ─────────────────────────────────────────────────

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            from index.api.anchors import load_anchors
            raw = load_anchors(str(self.root))
            # 转换为 expander 内部期望的格式
            self._anchors = {}
            for k, a in raw.items():
                self._anchors[k] = {
                    "name": a.symbol,
                    "symbol": a.symbol,
                    "symbol_type": a.symbol_type,
                    "file": a.file,
                    "line_start": a.line_start,
                    "line_end": a.line_end,
                    "hash": a.hash,
                    "description": a.description,
                    "category": a.symbol_type,
                    "code": a.code,
                    "callers": a.callers,
                    "callees": [
                        c.get("target", c) if isinstance(c, dict) else c
                        for c in a.callees
                    ],
                    "inputs": a.inputs,
                    "outputs": a.outputs,
                    "mro": a.mro,
                    "overrides": a.overrides,
                    "metadata": {
                        "calls": [
                            c.get("target", c) if isinstance(c, dict) else c
                            for c in a.callees
                        ],
                        "parameters": [v.get("name", "") for v in a.inputs],
                    },
                }
        except FileNotFoundError:
            self._anchors = {}
        self._loaded = True

    def _find(self, name: str) -> Optional[dict]:
        # 精确 key 匹配
        if name in self._anchors:
            return self._anchors[name]
        # 名字匹配
        for k, v in self._anchors.items():
            if v.get("name") == name:
                return v
        # 后缀匹配（支持 module.Class.method 格式）
        for k, v in self._anchors.items():
            if k.endswith(f".{name}"):
                return v
        return None

    def _read_from_file(self, anchor: dict) -> str:
        file_path = self.root / anchor.get("file", "")
        if not file_path.exists():
            return f"# 源文件不存在: {anchor.get('file')}"

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        start = anchor.get("line_start", 1) - 1
        end = anchor.get("line_end", start + 1)
        code = "".join(lines[start:end])
        return self._format_result(anchor, code)

    def _format_result(self, anchor: dict, code: str) -> str:
        header = (
            "# {}  {}:L{}–L{}\n\n".format(
                anchor.get("name"),
                anchor.get("file"),
                anchor.get("line_start", "?"),
                anchor.get("line_end", "?"),
            )
        )
        return header + code

    # ── 新接口：anchor:// 引用展开 ────────────────────────────

    def expand_from_ref(self, anchor_ref: str) -> dict:
        """
        解析 anchor:// 引用，返回锚点摘要信息（不含完整 code）。

        anchor_ref 格式：
          anchor://file::symbol
          anchor://symbol
          symbol（直接符号名）
        """
        self._ensure_loaded()
        anchor = None
        if anchor_ref.startswith("anchor://"):
            ref = anchor_ref[len("anchor://"):]
            if "::" in ref:
                file_part, sym_part = ref.split("::", 1)
                anchor = self._find_by_file_symbol(file_part, sym_part)
            else:
                anchor = self._find_by_symbol(ref)
        else:
            anchor = self._find_by_symbol(anchor_ref)

        if not anchor:
            return {"error": "找不到 {}".format(anchor_ref)}

        return {
            "symbol": anchor.get("symbol", anchor.get("name", "")),
            "file": anchor.get("file", ""),
            "line_start": anchor.get("line_start"),
            "symbol_type": anchor.get("symbol_type", anchor.get("category", "")),
            "inputs": anchor.get("inputs", []),
            "outputs": anchor.get("outputs", []),
            "callers": anchor.get("callers", []),
            "callees": anchor.get("callees", []),
            "mro": anchor.get("mro", []),
            "overrides": anchor.get("overrides"),
            "drift": anchor.get("drift", "ok"),
        }

    def _find_by_file_symbol(self, file_part: str, sym_part: str) -> Optional[dict]:
        """按 file::symbol 精确查找（兼容正反斜杠）。"""
        key = "{}::{}".format(file_part, sym_part)
        if key in self._anchors:
            return self._anchors[key]
        # 路径分隔符兼容
        alt = key.replace("\\", "/") if "\\" in key else key.replace("/", "\\")
        return self._anchors.get(alt)

    def _find_by_symbol(self, sym: str) -> Optional[dict]:
        """按符号名精确或后缀查找。"""
        for a in self._anchors.values():
            if a.get("symbol") == sym or a.get("name") == sym:
                return a
        for a in self._anchors.values():
            s = a.get("symbol", "")
            if s.endswith("." + sym) or s.endswith("::" + sym):
                return a
        return None

    def expand_with_relations(self, anchor_ref: str, radius: int = 1) -> dict:
        """
        在 expand_from_ref 的基础上，附加 radius 层关系子图。

        radius=1 → 直接上下游（debug 用）
        radius=2 → 再展开一层（追溯根源）
        """
        base = self.expand_from_ref(anchor_ref)
        if "error" in base:
            return base
        try:
            from relate.api.relations import expand_node
            node_id = "{}::{}".format(base["file"], base["symbol"])
            base["relations"] = expand_node(node_id, str(self.root), radius)
        except Exception as e:
            base["relations"] = {"error": str(e)}
        return base

    def get_code(self, anchor_ref: str) -> str:
        """
        返回符号的完整源码。优先取 anchor.code，
        若空则按 line_start/line_end 从源文件切片。
        """
        self._ensure_loaded()
        anchor = None
        if anchor_ref.startswith("anchor://"):
            ref = anchor_ref[len("anchor://"):]
            if "::" in ref:
                f, s = ref.split("::", 1)
                anchor = self._find_by_file_symbol(f, s)
            else:
                anchor = self._find_by_symbol(ref)
        else:
            anchor = self._find_by_symbol(anchor_ref)

        if not anchor:
            return "# 找不到 {}".format(anchor_ref)

        if anchor.get("code"):
            return anchor["code"]

        try:
            src = (self.root / anchor["file"]).read_text(encoding="utf-8", errors="replace")
            lines = src.splitlines()
            start = anchor.get("line_start", 1) - 1
            end = anchor.get("line_end", start + 20)
            return "\n".join(lines[start:end])
        except Exception as e:
            return "# 读取失败: {}".format(e)
