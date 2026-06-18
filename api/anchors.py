"""
锚点管理接口层
========================
generate_all_anchors: 从 5 个源 merge，写入 .codedendrite/anchors.json
load_anchors / get_anchor: 唯一读取接口
"""

import json
import os
import ast
import re as _re
from dataclasses import asdict
from pathlib import Path
from typing import Optional, List, Dict

from shared.types import Anchor
from shared.codedendrite_ignore import CodeDendriteIgnore
from shared.formula_skip import should_skip as _should_skip_formula

_EMBED_STYLE_RE = _re.compile(r'<style[^>]*>(.*?)</style>', _re.DOTALL | _re.IGNORECASE)
_EMBED_SCRIPT_RE = _re.compile(r'<script[^>]*>(.*?)</script>', _re.DOTALL | _re.IGNORECASE)
_EMBED_DOM_ID_RE = _re.compile(r'\bid=["\']([A-Za-z][\w-]*)["\']')
_EMBED_CSS_SEL_RE = _re.compile(r'(?:^|[\s,>+~])([.#][A-Za-z][\w-]*)', _re.MULTILINE)
_EMBED_JS_FUNC_RE = _re.compile(r'function\s+([A-Za-z$_][\w$]*)\s*\(')
_EMBED_JS_QUERY_RE = _re.compile(r'(?:querySelectorAll?|getElementById)\s*\(\s*["\']([^"\']+)["\']')

# ── 调试日志（环境变量 CD_ANCHOR_LOG 开关；默认不打，不污染生产 run）──
import time as _time
_ANCHOR_DBG = bool(os.environ.get("CD_ANCHOR_LOG"))


def _alog(msg: str):
    if _ANCHOR_DBG:
        print(f"[anchors {_time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _slow_warn(phase: str, rel: str, dt: float, thresh: float = 1.0):
    """逐文件计时；超过阈值的单独标 SLOW，方便一眼揪出卡的文件。"""
    if _ANCHOR_DBG:
        tag = "  <<< SLOW" if dt >= thresh else ""
        print(f"[anchors {_time.strftime('%H:%M:%S')}] {phase} {rel}  {dt*1000:.0f}ms{tag}", flush=True)


BUILTIN_NOISE = {
    "print", "append", "get", "len", "str", "int", "list", "dict",
    "set", "type", "range", "enumerate", "zip", "map", "filter",
    "isinstance", "hasattr", "getattr", "setattr", "open", "any",
    "all", "sorted", "reversed", "join", "split", "format", "update",
    "extend", "items", "values", "keys", "pop", "insert", "read",
    "write", "close", "encode", "decode", "replace", "strip",
    # super() 及常见 dunder：callee 解析结果不可用，过滤掉
    "super", "__init__", "__new__", "__str__", "__repr__",
    "__len__", "__iter__", "__next__", "__enter__", "__exit__",
    "__getitem__", "__setitem__", "__delitem__", "__contains__",
    "__call__", "__del__",
}


def _build_unique_symbol_ids(anchors: dict) -> dict:
    by_symbol = {}
    duplicate_symbols = set()
    for anchor in anchors.values():
        symbol = anchor.symbol
        if not symbol:
            continue
        if symbol in by_symbol:
            duplicate_symbols.add(symbol)
        else:
            by_symbol[symbol] = anchor.id
    return {
        symbol: anchor_id
        for symbol, anchor_id in by_symbol.items()
        if symbol not in duplicate_symbols
    }


def _call_target(raw_callee):
    if isinstance(raw_callee, dict):
        return raw_callee.get("target", "")
    return raw_callee


def _resolve_super_call(method_name: str, caller_anchor, anchors: dict) -> Optional[str]:
    """super().method() → 取 mro[1] 的 effective_methods[method_name]，O(1)。
    mro[1] 是第一个父类；其 effective_methods 已经做了 carry-down，
    所以无论父类是否自己定义该方法，都能给出正确的 ancestor nid。
    """
    symbol = getattr(caller_anchor, "symbol", "")
    if "." not in symbol:
        return None
    class_name = symbol.split(".", 1)[0]
    class_nid = "{}::{}".format(caller_anchor.file, class_name)
    class_anchor = anchors.get(class_nid)
    if class_anchor is None:
        return None
    mro = getattr(class_anchor, "mro", [])
    if len(mro) < 2:
        return None
    parent_nid = mro[1]
    if parent_nid.startswith("external::"):
        return None
    parent_anchor = anchors.get(parent_nid)
    if parent_anchor is None:
        return None
    return parent_anchor.effective_methods.get(method_name)


def _resolve_call_id(raw_callee, anchors: dict, unique_symbol_ids: dict,
                     caller_file: str | None = None,
                     caller_anchor=None) -> str | None:
    target = _call_target(raw_callee)
    if not target:
        return None
    target = str(target).replace("\\", "/")
    # super::method_name → MRO-aware 解析
    if target.startswith("super::") and caller_anchor is not None:
        return _resolve_super_call(target[len("super::"):], caller_anchor, anchors)
    if target in BUILTIN_NOISE:
        return None
    if "::" in target:
        return target if target in anchors else None
    if caller_file:
        candidate = "{}::{}".format(caller_file.replace("\\", "/"), target)
        if candidate in anchors:
            return candidate
    return unique_symbol_ids.get(target)


ANCHOR_DEFAULTS = {
    "code": "",
    "callers": [],
    "callees": [],
    "call_sites": [],
    "inputs": [],
    "outputs": [],
    "parent_classes": [],
    "overrides": None,
    "overridden_by": [],
    "mro": [],
    "own_methods": [],
    "effective_methods": {},
    "observations": [],
    "language": "python",
    "description": "",
    "drift": "ok",
    "is_virtual": False,
    "virtual_kind": None,
    "parent_anchor": None,
    "scope_label": None,
    "block_metadata": {},
    "registered_as": None,
}


def _anchor_to_storage(anchor: Anchor) -> dict:
    data = asdict(anchor)
    return {
        key: value
        for key, value in data.items()
        if key not in ANCHOR_DEFAULTS or value != ANCHOR_DEFAULTS[key]
    }


def _normalize_file_ref(root: Path, file_path) -> str:
    path = Path(str(file_path).replace("\\", "/"))
    if path.is_absolute():
        try:
            return str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")
    normalized = str(path).replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def _write_anchors(root: Path, anchors: dict) -> None:
    output_path = root / ".codedendrite" / "anchors.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: _anchor_to_storage(v) for k, v in anchors.items()}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _extract_registered_as(decorators: list) -> Optional[str]:
    for dec in decorators:
        if isinstance(dec, dict) and dec.get("key"):
            return dec["key"]
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _find_function_node(tree: ast.AST, symbol: str):
    parts = symbol.split(".")
    if len(parts) == 1:
        for node in getattr(tree, "body", []):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
                return node
        return None
    class_name, method_name = parts[0], parts[1]
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return item
    return None


class _CallSiteCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.call_sites: list[dict] = []
        self.conds: list[dict] = []
        self.seq = 0

    def _expr(self, node: ast.AST | None) -> str:
        if node is None:
            return "else"
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def _cond_item(self, cond_id: str, expr: str) -> dict:
        return {cond_id: expr or "else"}

    def _append_call(self, node: ast.Call) -> None:
        target = _call_name(node.func)
        if not target:
            return
        self.call_sites.append({
            "target": target,
            "seq": self.seq,
            "line": int(getattr(node, "lineno", 0) or 0),
            "conds": list(self.conds) if self.conds else ["nocond"],
        })
        self.seq += 1

    @staticmethod
    def _is_super_call(node: ast.AST) -> bool:
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "super")

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        # super().method() or super(Cls, self).method() — emit super::method,
        # suppress the inner super() so it doesn't appear as a bare noise call
        if isinstance(func, ast.Attribute) and self._is_super_call(func.value):
            self.call_sites.append({
                "target": "super::{}".format(func.attr),
                "seq": self.seq,
                "line": int(getattr(node, "lineno", 0) or 0),
                "conds": list(self.conds) if self.conds else ["nocond"],
            })
            self.seq += 1
            # Visit args of the outer call but skip the super() sub-call itself
            for child in node.args:
                self.visit(child)
            for kw in node.keywords:
                self.visit(kw.value)
            return
        self._append_call(node)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        cond_id = "if:{}".format(int(getattr(node, "lineno", 0) or 0))
        current = node
        while True:
            self.conds.append(self._cond_item(cond_id, self._expr(current.test)))
            for stmt in current.body:
                self.visit(stmt)
            self.conds.pop()
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                current = current.orelse[0]
                continue
            if current.orelse:
                self.conds.append(self._cond_item(cond_id, "else"))
                for stmt in current.orelse:
                    self.visit(stmt)
                self.conds.pop()
            break

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_loop(node)

    def visit_While(self, node: ast.While) -> None:
        cond_id = "while:{}".format(int(getattr(node, "lineno", 0) or 0))
        self.conds.append(self._cond_item(cond_id, self._expr(node.test)))
        for stmt in node.body:
            self.visit(stmt)
        self.conds.pop()
        if node.orelse:
            self.conds.append(self._cond_item(cond_id, "else"))
            for stmt in node.orelse:
                self.visit(stmt)
            self.conds.pop()

    def _visit_loop(self, node: ast.AST) -> None:
        cond_id = "for:{}".format(int(getattr(node, "lineno", 0) or 0))
        expr = "{} in {}".format(self._expr(getattr(node, "target", None)), self._expr(getattr(node, "iter", None)))
        self.conds.append(self._cond_item(cond_id, expr))
        for stmt in getattr(node, "body", []):
            self.visit(stmt)
        self.conds.pop()
        if getattr(node, "orelse", None):
            self.conds.append(self._cond_item(cond_id, "else"))
            for stmt in node.orelse:
                self.visit(stmt)
            self.conds.pop()

    def visit_Try(self, node: ast.Try) -> None:
        try_id = "try:{}".format(int(getattr(node, "lineno", 0) or 0))
        self.conds.append(self._cond_item(try_id, "try"))
        for stmt in node.body:
            self.visit(stmt)
        self.conds.pop()
        for handler in node.handlers:
            expr = self._expr(handler.type) if handler.type else "except"
            self.conds.append(self._cond_item(try_id, expr))
            for stmt in handler.body:
                self.visit(stmt)
            self.conds.pop()
        if node.orelse:
            self.conds.append(self._cond_item(try_id, "else"))
            for stmt in node.orelse:
                self.visit(stmt)
            self.conds.pop()
        if node.finalbody:
            self.conds.append(self._cond_item(try_id, "finally"))
            for stmt in node.finalbody:
                self.visit(stmt)
            self.conds.pop()

    def generic_visit(self, node) -> None:
        # 跳公式：不下钻进大的纯数据/公式子树（sqrt/S 那种不是调用关系，是数据）
        for child in ast.iter_child_nodes(node):
            if _should_skip_formula(child):
                continue
            self.visit(child)


def _extract_call_sites_from_tree(tree: ast.AST, symbol: str) -> list[dict]:
    node = _find_function_node(tree, symbol)
    if not node:
        return []
    collector = _CallSiteCollector()
    for stmt in node.body:
        collector.visit(stmt)
    return collector.call_sites


def _extract_function_io_from_tree(tree: ast.AST, symbol: str) -> tuple:
    node = _find_function_node(tree, symbol)
    if not node:
        return [], []
    all_args = (
        getattr(node.args, "posonlyargs", []) +
        node.args.args +
        getattr(node.args, "kwonlyargs", [])
    )
    inputs = []
    for arg in all_args:
        if arg.arg in ("self", "cls"):
            continue
        ann = ""
        if arg.annotation:
            try:
                ann = ast.unparse(arg.annotation)
            except Exception:
                pass
        inputs.append({"name": arg.arg, "type": ann})
    outputs = []
    if node.returns:
        try:
            outputs = [{"name": "return", "type": ast.unparse(node.returns)}]
        except Exception:
            pass
    return inputs, outputs


def _extract_call_sites(file_path: Path, symbol: str) -> list[dict]:
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception:
        return []
    return _extract_call_sites_from_tree(tree, symbol)


def _merge_code_anchor(anchors: dict, ca, root: Path) -> None:
    try:
        rel = str(Path(ca.file).relative_to(root)).replace("\\", "/")
    except ValueError:
        rel = _normalize_file_ref(root, ca.file)

    lang_map = {"py": "python", "cpp": "cpp"}
    lang = lang_map.get(ca.language, ca.language)

    if ca.category in ("classes", "structs"):
        sym_type = "class"
        symbol = ca.name
    elif ca.category == "methods":
        sym_type = "method"
        parts = ca.parent_id.split(".") if ca.parent_id else []
        class_name = ""
        if "classes" in parts:
            idx = parts.index("classes")
            if idx + 1 < len(parts):
                class_name = parts[idx + 1]
        symbol = "{}.{}".format(class_name, ca.name) if class_name else ca.name
    elif ca.category == "functions":
        sym_type = "function"
        symbol = ca.name
    else:
        return

    key = "{}::{}".format(rel, symbol)
    decorators = ca.metadata.get("decorators", [])
    dec_meta = [d for d in decorators if isinstance(d, dict) and (d.get("name") or d.get("key"))]
    anchors[key] = Anchor(
        id=key,
        symbol=symbol,
        file=rel,
        line_start=ca.line_start,
        line_end=ca.line_end,
        hash=ca.hash,
        callers=ca.metadata.get("callers", []),
        language=lang,
        symbol_type=sym_type,
        registered_as=_extract_registered_as(decorators),
        block_metadata={"decorators": dec_meta} if dec_meta else {},
    )


def _build_unique_class_ids(anchors: dict) -> dict:
    by_symbol = {}
    duplicate_symbols = set()
    for anchor in anchors.values():
        if anchor.symbol_type != "class" or anchor.is_virtual:
            continue
        symbol = anchor.symbol
        if symbol in by_symbol:
            duplicate_symbols.add(symbol)
        else:
            by_symbol[symbol] = anchor.id
    return {
        symbol: anchor_id
        for symbol, anchor_id in by_symbol.items()
        if symbol not in duplicate_symbols
    }


def _resolve_class_ref(class_name: str, class_ids: dict) -> str:
    if not class_name:
        return ""
    class_name = str(class_name).replace("\\", "/")
    if "::" in class_name or class_name.startswith("external::"):
        return class_name
    return class_ids.get(class_name) or "external::{}".format(class_name)


def _build_effective_methods_table(anchors: dict) -> None:
    """每个 class anchor 上写入 own_methods 和 effective_methods。"""
    class_own: Dict[str, Dict[str, str]] = {}
    for nid, anchor in anchors.items():
        if anchor.symbol_type != "method" or "." not in anchor.symbol:
            continue
        class_sym = anchor.symbol.split(".", 1)[0]
        class_nid = "{}::{}".format(anchor.file, class_sym)
        if class_nid not in class_own:
            class_own[class_nid] = {}
        method_name = anchor.symbol.split(".", 1)[1]
        class_own[class_nid][method_name] = nid

    for nid, anchor in anchors.items():
        if anchor.symbol_type != "class":
            continue
        own = class_own.get(nid, {})
        anchor.own_methods = list(own.values())
        mro = getattr(anchor, "mro", [])
        if not mro:
            anchor.effective_methods = dict(own)
            continue
        effective: Dict[str, str] = {}
        for ancestor_nid in reversed(mro):
            if ancestor_nid.startswith("external::"):
                effective.setdefault("__external_base__", ancestor_nid)
                continue
            ancestor_own = class_own.get(ancestor_nid, {})
            effective.update(ancestor_own)
        anchor.effective_methods = effective


def _apply_inheritance_refs(anchors: dict, index, compute_mro, find_subclasses) -> None:
    class_ids = _build_unique_class_ids(anchors)
    for anchor in anchors.values():
        if anchor.symbol_type != "class" or anchor.language != "python":
            continue
        try:
            raw_mro = compute_mro(anchor.symbol, index) or []
            mro_ids = [
                _resolve_class_ref(name, class_ids)
                for name in raw_mro
                if name
            ]
            anchor.mro = mro_ids if len(mro_ids) > 1 else []
            anchor.parent_classes = mro_ids[1:2] if len(mro_ids) > 1 else []
            subs = find_subclasses(index, anchor.symbol)
            anchor.overridden_by = [s.name for s in subs]
        except Exception:
            pass


def _finalize_anchor_graph(anchors: dict) -> None:
    unique_symbol_ids = _build_unique_symbol_ids(anchors)
    for anchor in anchors.values():
        normalized_callees = []
        normalized_sites = []
        sites = list(getattr(anchor, "call_sites", []) or [])
        for idx, raw_callee in enumerate(anchor.callees):
            target_id = _resolve_call_id(raw_callee, anchors, unique_symbol_ids,
                                         caller_file=anchor.file, caller_anchor=anchor)
            if not target_id:
                continue
            if idx < len(sites) and isinstance(sites[idx], dict):
                site = dict(sites[idx])
            elif isinstance(raw_callee, dict):
                site = dict(raw_callee)
            else:
                site = {}
            site["target"] = target_id
            site.setdefault("seq", idx)
            site.setdefault("line", 0)
            site.setdefault("conds", ["nocond"])
            normalized_callees.append(target_id)
            normalized_sites.append(site)
        anchor.callees = normalized_callees
        anchor.call_sites = normalized_sites

    for anchor in anchors.values():
        anchor.callers = []
    for anchor in anchors.values():
        if anchor.is_virtual:
            continue
        for raw_callee in anchor.callees:
            target_id = _call_target(raw_callee)
            target = anchors.get(target_id)
            if not target:
                continue
            if anchor.id not in target.callers:
                target.callers.append(anchor.id)


# ── 懒加载兼容包装（codeTree 使用了 Python 3.9+ 语法）──────────

def list_all_symbols(root, extensions=(".py",), exclude_dirs=None):
    from codeTree.deep_drift import _list_all_symbols
    return _list_all_symbols(root, extensions, exclude_dirs)


def list_anchors(root="."):
    from codeTree.anchor_engine_v2 import list_anchors as _list_anchors
    return _list_anchors(root)


def create_anchor(anchor_id, file, symbol=None, line_start=None, line_end=None,
                  description="", hash_mode="struct", language="python", root="."):
    from codeTree.anchor_engine_v2 import create_anchor as _create_anchor
    return _create_anchor(anchor_id, file, symbol, line_start, line_end,
                          description, hash_mode, language, root)


def check_all_anchors(root):
    from anchorRepair import check_all_anchors as _check_all_anchors
    return _check_all_anchors(root)


# ── 核心：generate_all_anchors ──────────────────────────────────

def generate_all_anchors(root=".", exclude_dirs=None, include_virtual_blocks=False) -> dict:
    root = Path(root)
    output_path = root / ".codedendrite" / "anchors.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    exclude = set(exclude_dirs or [])
    ignore = CodeDendriteIgnore(str(root))

    anchors: dict = {}
    failed = []

    parse_failures = []
    auto_fixed = []

    _alog(f"BEGIN generate_all_anchors root={root}")
    _phase0 = _time.perf_counter()

    # ── 源 1: codeGenome ──────────────────────────────────────
    try:
        from codeGenome import scan_project as genome_scan
        _alog("源1 codeGenome.scan_project START (whole project)")
        _g0 = _time.perf_counter()
        query = genome_scan(str(root))
        _alog(f"源1 codeGenome.scan_project DONE {_time.perf_counter()-_g0:.1f}s")
        parse_failures.extend(getattr(query, 'parse_failures', []))
        auto_fixed.extend(getattr(query, 'auto_fixed', []))

        for ca in query.find_functions() + query.find_classes() + query.find_methods():
            if not ignore.should_scan(Path(ca.file)):
                continue
            if any(p in exclude for p in Path(ca.file).parts):
                continue
            try:
                rel = str(Path(ca.file).relative_to(root)).replace("\\", "/")
            except ValueError:
                rel = ca.file.replace("\\", "/")

            lang_map = {"py": "python", "cpp": "cpp"}
            lang = lang_map.get(ca.language, ca.language)

            if ca.category in ("classes", "structs"):
                sym_type = "class"
                symbol = ca.name
            elif ca.category == "methods":
                sym_type = "method"
                # 用 parent_id 提取类名，格式: py.module.classes.ClassName.methods.method_name
                parts = ca.parent_id.split(".") if ca.parent_id else []
                class_name = ""
                if "classes" in parts:
                    idx = parts.index("classes")
                    if idx + 1 < len(parts):
                        class_name = parts[idx + 1]
                symbol = "{}.{}".format(class_name, ca.name) if class_name else ca.name
            else:
                sym_type = "function"
                symbol = ca.name

            key = "{}::{}".format(rel, symbol)

            anchors[key] = Anchor(
                id=key,
                symbol=symbol,
                file=rel,
                line_start=ca.line_start,
                line_end=ca.line_end,
                hash=ca.hash,
                callers=ca.metadata.get("callers", []),
                language=lang,
                symbol_type=sym_type,
            )
    except Exception as e:
        failed.append("codeGenome: {}".format(e))
    # ── 源2 codeAnalysis(Python 补漏)已删除 ──
    # 实测 源1 codeGenome 与 源2 符号集完全相同(源2 独有=0,漏=0)：
    # inheritance(93)/codeGenome(141)/api(315)/dataFlow(27)。纯冗余,且多一次整库 parse+walk。
    # 见 _refactor/diff_sources.py。

    # ── 源 2b: codeAnalysis TypeScript/JavaScript ──
    _TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
    try:
        ts_analyzer = get_analyzer(str(root), language="typescript")
        for dirpath, dirnames, filenames in os.walk(root):
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.ts")]
            for fname in filenames:
                if Path(fname).suffix.lower() not in _TS_EXTS:
                    continue
                ts_file = dp / fname
                if not ignore.should_scan(ts_file):
                    continue
                if any(p in exclude for p in ts_file.parts):
                    continue
                try:
                    rel = str(ts_file.relative_to(root)).replace("\\", "/")
                except ValueError:
                    rel = str(ts_file).replace("\\", "/")
                lang = "typescript" if Path(fname).suffix.lower() in {".ts", ".tsx"} else "javascript"
                try:
                    _t0 = _time.perf_counter()
                    module = ts_analyzer.analyze_file(str(ts_file))
                    _slow_warn("ts.analyze", rel, _time.perf_counter() - _t0)
                    for cls in module.classes:
                        cls_name = cls.name if hasattr(cls, "name") else str(cls)
                        key_cls = "{}::{}".format(rel, cls_name)
                        if key_cls not in anchors:
                            anchors[key_cls] = Anchor(
                                id=key_cls, symbol=cls_name, file=rel,
                                line_start=getattr(cls, "line_number", 1),
                                line_end=getattr(cls, "line_number", 1),
                                hash="", language=lang, symbol_type="class",
                            )
                    for func in module.functions:
                        if not func.name:
                            continue
                        if getattr(func, "is_method", False) and getattr(func, "class_name", None):
                            qualified = "{}.{}".format(func.class_name, func.name)
                            fkey = "{}::{}".format(rel, qualified)
                            sym_type = "method"
                        else:
                            qualified = func.name
                            fkey = "{}::{}".format(rel, qualified)
                            sym_type = "function"
                        if fkey not in anchors:
                            anchors[fkey] = Anchor(
                                id=fkey, symbol=qualified, file=rel,
                                line_start=getattr(func, "line_number", 1),
                                line_end=getattr(func, "line_number", 1),
                                hash="", language=lang, symbol_type=sym_type,
                            )
                except Exception:
                    pass
    except Exception as e:
        failed.append("codeAnalysis_ts: {}".format(e))

    # ── 源 2b: codeAnalysis TypeScript/JavaScript ─────────────
    try:
        for _e_dirpath, _e_dirs, _e_files in os.walk(root):
            _e_dp = Path(_e_dirpath)
            _e_dirs[:] = [d for d in _e_dirs if ignore.should_scan(_e_dp / d / "_x.py")]
            for _e_fname in _e_files:
                if not _e_fname.endswith(".py"):
                    continue
                _e_file = _e_dp / _e_fname
                if not ignore.should_scan(_e_file):
                    continue
                if any(p in exclude for p in _e_file.parts):
                    continue
                try:
                    _e_rel = str(_e_file.relative_to(root)).replace("\\", "/")
                except ValueError:
                    _e_rel = str(_e_file).replace("\\", "/")
                try:
                    _e_src = _e_file.read_text(encoding="utf-8", errors="replace")
                    if "<" not in _e_src:
                        continue
                    _e_tree = ast.parse(_e_src)
                except Exception:
                    continue
                _e_pmap = {}
                for _e_pn in ast.walk(_e_tree):
                    for _e_ch in ast.iter_child_nodes(_e_pn):
                        _e_pmap[id(_e_ch)] = _e_pn
                for _e_node in ast.walk(_e_tree):
                    if not isinstance(_e_node, ast.Constant) or not isinstance(_e_node.value, str):
                        continue
                    _e_text = _e_node.value
                    if "<" not in _e_text:
                        continue
                    _e_line = getattr(_e_node, "lineno", 1)
                    _e_new_keys = []
                    for _esm in _EMBED_STYLE_RE.finditer(_e_text):
                        for _ecm in _EMBED_CSS_SEL_RE.finditer(_esm.group(1)):
                            _esel = _ecm.group(1)
                            _ekey = "{}::css:{}".format(_e_rel, _esel)
                            if _ekey not in anchors:
                                anchors[_ekey] = Anchor(
                                    id=_ekey, symbol="css:{}".format(_esel),
                                    file=_e_rel, line_start=_e_line, line_end=_e_line,
                                    hash="", language="css", symbol_type="css_rule",
                                )
                            _e_new_keys.append(_ekey)
                    for _eim in _EMBED_DOM_ID_RE.finditer(_e_text):
                        _eid = _eim.group(1)
                        _ekey = "{}::dom:{}".format(_e_rel, _eid)
                        if _ekey not in anchors:
                            anchors[_ekey] = Anchor(
                                id=_ekey, symbol="dom:{}".format(_eid),
                                file=_e_rel, line_start=_e_line, line_end=_e_line,
                                hash="", language="html", symbol_type="dom_id",
                            )
                        _e_new_keys.append(_ekey)
                    for _escm in _EMBED_SCRIPT_RE.finditer(_e_text):
                        _e_js = _escm.group(1)
                        _e_js_callees = []
                        for _eqm in _EMBED_JS_QUERY_RE.finditer(_e_js):
                            _eqsel = _eqm.group(1).strip()
                            if _eqsel.startswith("."):
                                _e_js_callees.append("css:{}".format(_eqsel))
                            elif _eqsel.startswith("#"):
                                _e_js_callees.append("dom:{}".format(_eqsel[1:]))
                            elif _eqsel and _eqsel.replace("-", "").isalnum():
                                _e_js_callees.append("dom:{}".format(_eqsel))
                        for _efm in _EMBED_JS_FUNC_RE.finditer(_e_js):
                            _efname = _efm.group(1)
                            _efkey = "{}::js:{}".format(_e_rel, _efname)
                            if _efkey not in anchors:
                                anchors[_efkey] = Anchor(
                                    id=_efkey, symbol="js:{}".format(_efname),
                                    file=_e_rel, line_start=_e_line, line_end=_e_line,
                                    hash="", language="javascript", symbol_type="function",
                                    callees=list(_e_js_callees),
                                )
                            _e_new_keys.append(_efkey)
                    # Link enclosing Python method → these embedded anchors
                    if _e_new_keys:
                        _e_cur = _e_pmap.get(id(_e_node))
                        while _e_cur is not None:
                            if isinstance(_e_cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                _e_parent = _e_pmap.get(id(_e_cur))
                                if isinstance(_e_parent, ast.ClassDef):
                                    _e_py_sym = "{}.{}".format(_e_parent.name, _e_cur.name)
                                else:
                                    _e_py_sym = _e_cur.name
                                _e_py_anchor = anchors.get("{}::{}".format(_e_rel, _e_py_sym))
                                if _e_py_anchor is not None:
                                    for _ek in _e_new_keys:
                                        if _ek not in _e_py_anchor.callees:
                                            _e_py_anchor.callees.append(_ek)
                                break
                            _e_cur = _e_pmap.get(id(_e_cur))
    except Exception as e:
        failed.append("embedded_dom: {}".format(e))

    # ── 源 2c: embedded DOM/CSS/JS in Python string literals ────
    from collections import defaultdict as _defaultdict
    _by_file: dict = _defaultdict(list)
    for _key, _anchor in anchors.items():
        if _anchor.language == "python" and _anchor.symbol_type != "class":
            _by_file[_anchor.file].append(_anchor)
    _alog(f"源2c embedded/call-site per-file START ({len(_by_file)} files, phase elapsed {_time.perf_counter()-_phase0:.1f}s)")
    for _rel_file, _file_anchors in _by_file.items():
        _t2c = _time.perf_counter()
        try:
            _source = (root / _rel_file).read_text(encoding="utf-8", errors="replace")
            _tree = ast.parse(_source)
        except Exception:
            continue
        for _anchor in _file_anchors:
            try:
                _call_sites = _extract_call_sites_from_tree(_tree, _anchor.symbol)
                if _call_sites:
                    _anchor.call_sites = _call_sites
                    _anchor.callees = [s["target"] for s in _call_sites]
                _inputs, _outputs = _extract_function_io_from_tree(_tree, _anchor.symbol)
                if _inputs:
                    _anchor.inputs = _inputs
                if _outputs:
                    _anchor.outputs = _outputs
            except Exception:
                pass
        _slow_warn("2c.callsites", _rel_file, _time.perf_counter() - _t2c)

    # ── 源 3: dataFlow（callees / inputs / outputs）────────────
    _alog(f"源3 inheritance START (phase elapsed {_time.perf_counter()-_phase0:.1f}s)")
    try:
        from inheritance import build_class_index, compute_mro, find_subclasses
        from inheritance import resolve_inheritance
        from inheritance.override_analyzer import build_override_chain

        _t3 = _time.perf_counter()
        index = build_class_index(str(root))
        _alog(f"源3 build_class_index DONE {_time.perf_counter()-_t3:.1f}s")

        _t3b = _time.perf_counter()
        _apply_inheritance_refs(anchors, index, compute_mro, find_subclasses)
        _alog(f"源3 _apply_inheritance_refs DONE {_time.perf_counter()-_t3b:.1f}s")

        _t3c = _time.perf_counter()
        for key, anchor in anchors.items():
            if anchor.symbol_type != "method" or anchor.language != "python":
                continue
            try:
                class_name = anchor.symbol.split(".")[0] if "." in anchor.symbol else None
                if not class_name:
                    continue
                chain_objs = resolve_inheritance(class_name, index)
                chain_dicts = [e.to_dict() for e in chain_objs]
                method_name = anchor.symbol.split(".")[-1]
                override_chain = build_override_chain(chain_dicts, method_name)
                if (len(override_chain) > 1
                        and override_chain[0]["class"] == class_name):
                    anchor.overrides = override_chain[1]["class"]
            except Exception:
                pass

        _alog(f"源3 per-method override loop DONE {_time.perf_counter()-_t3c:.1f}s")
        _t3d = _time.perf_counter()
        _build_effective_methods_table(anchors)
        _alog(f"源3 _build_effective_methods_table DONE {_time.perf_counter()-_t3d:.1f}s")
    except Exception as e:
        failed.append("inheritance: {}".format(e))
    _alog(f"源3 inheritance phase DONE (total elapsed {_time.perf_counter()-_phase0:.1f}s)")

    # ── 源 4: inheritance（mro / parent_classes / overridden_by / overrides）
    if include_virtual_blocks:
        try:
            from api.control_flow_blocks import extract_control_flow_blocks

            for key, block_anchor in extract_control_flow_blocks(str(root)).items():
                if not ignore.should_scan(root / block_anchor.file):
                    continue
                if key not in anchors:
                    anchors[key] = block_anchor
        except Exception as e:
            failed.append("control_flow_blocks: {}".format(e))

    # ── 反向构建 callers ──────────────────────────────────────
    _finalize_anchor_graph(anchors)

    # ── 写入 anchors.json ──────────────────────────────────────
    data = {k: _anchor_to_storage(v) for k, v in anchors.items()}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 写入 failure_files.json ────────────────────────────────
    if parse_failures or auto_fixed:
        def _rel(entry):
            try:
                entry["file"] = str(Path(entry["file"]).relative_to(root)).replace("\\", "/")
            except ValueError:
                entry["file"] = entry["file"].replace("\\", "/")
            return entry

        failure_data = {
            "stats": {
                "total": len(parse_failures) + len(auto_fixed),
                "auto_fixed": len(auto_fixed),
                "unfixable": len(parse_failures),
            },
            "auto_fixed": [_rel(dict(e)) for e in auto_fixed],
            "unfixable": [_rel(dict(e)) for e in parse_failures],
        }
        fail_path = output_path.parent / "failure_files.json"
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(failure_data, f, ensure_ascii=False, indent=2)

    return {
        "created": len(anchors),
        "skipped": 0,
        "failed": len(failed),
        "errors": failed,
        "total_symbols": len(anchors),
        "total_anchors": len(anchors),
    }


# ── 读取接口 ─────────────────────────────────────────────────────

def _generate_anchors_for_paths(
    root: Path,
    file_paths: list[Path],
    include_virtual_blocks: bool = False,
) -> tuple[dict, list]:
    anchors: dict = {}
    failed = []

    try:
        from codeGenome.python_extractor import extract_python_file
        from codeGenome.cpp_extractor import extract_cpp_file
        for file_path in file_paths:
            try:
                if file_path.suffix == ".py":
                    index = extract_python_file(str(file_path))
                elif file_path.suffix.lower() in {".cpp", ".h", ".hpp", ".cc", ".cxx", ".hxx"}:
                    index = extract_cpp_file(str(file_path))
                else:
                    continue
                for ca in index.anchors.values():
                    _merge_code_anchor(anchors, ca, root)
            except Exception as e:
                failed.append("{}: {}".format(file_path, e))
    except Exception as e:
        failed.append("codeGenome: {}".format(e))

    py_files = [p for p in file_paths if p.suffix == ".py"]
    try:
        from codeAnalysis.analyzer import get_analyzer
        analyzer = get_analyzer(str(root), language="python")
        for py_file in py_files:
            rel = _normalize_file_ref(root, py_file)
            try:
                module = analyzer.analyze_file(str(py_file))
                for cls in module.classes:
                    cls_name = cls.name if hasattr(cls, "name") else str(cls)
                    cls_line = getattr(cls, "line_number", 1)
                    key_cls = "{}::{}".format(rel, cls_name)
                    if key_cls not in anchors:
                        anchors[key_cls] = Anchor(
                            id=key_cls, symbol=cls_name, file=rel,
                            line_start=cls_line, line_end=cls_line,
                            hash="", language="python", symbol_type="class",
                        )
                    for method in getattr(cls, "methods", []):
                        if not hasattr(method, "name"):
                            continue
                        qualified = "{}.{}".format(cls_name, method.name)
                        mkey = "{}::{}".format(rel, qualified)
                        if mkey not in anchors:
                            anchors[mkey] = Anchor(
                                id=mkey, symbol=qualified, file=rel,
                                line_start=method.line_number, line_end=method.line_number,
                                hash="", language="python", symbol_type="method",
                            )
                for func in module.functions:
                    if getattr(func, "is_method", False) and getattr(func, "class_name", None):
                        qualified = "{}.{}".format(func.class_name, func.name)
                        fkey = "{}::{}".format(rel, qualified)
                        if fkey not in anchors:
                            anchors[fkey] = Anchor(
                                id=fkey, symbol=qualified, file=rel,
                                line_start=func.line_number, line_end=func.line_number,
                                hash="", language="python", symbol_type="method",
                            )
                    else:
                        key_f = "{}::{}".format(rel, func.name)
                        if key_f not in anchors:
                            anchors[key_f] = Anchor(
                                id=key_f, symbol=func.name, file=rel,
                                line_start=func.line_number, line_end=func.line_number,
                                hash="", language="python", symbol_type="function",
                            )
            except Exception as e:
                failed.append("{}: {}".format(py_file, e))
    except Exception as e:
        failed.append("codeAnalysis: {}".format(e))

    try:
        for py_file in py_files:
            rel = _normalize_file_ref(root, py_file)
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                if "<" not in source:
                    continue
                tree = ast.parse(source)
            except Exception:
                continue

            parent_map = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parent_map[id(child)] = parent

            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                text = node.value
                if "<" not in text:
                    continue

                line = getattr(node, "lineno", 1)
                embedded_keys = []
                for style_match in _EMBED_STYLE_RE.finditer(text):
                    for selector_match in _EMBED_CSS_SEL_RE.finditer(style_match.group(1)):
                        selector = selector_match.group(1)
                        key = "{}::css:{}".format(rel, selector)
                        if key not in anchors:
                            anchors[key] = Anchor(
                                id=key, symbol="css:{}".format(selector),
                                file=rel, line_start=line, line_end=line,
                                hash="", language="css", symbol_type="css_rule",
                            )
                        embedded_keys.append(key)

                for id_match in _EMBED_DOM_ID_RE.finditer(text):
                    dom_id = id_match.group(1)
                    key = "{}::dom:{}".format(rel, dom_id)
                    if key not in anchors:
                        anchors[key] = Anchor(
                            id=key, symbol="dom:{}".format(dom_id),
                            file=rel, line_start=line, line_end=line,
                            hash="", language="html", symbol_type="dom_id",
                        )
                    embedded_keys.append(key)

                for script_match in _EMBED_SCRIPT_RE.finditer(text):
                    js_text = script_match.group(1)
                    js_callees = []
                    for query_match in _EMBED_JS_QUERY_RE.finditer(js_text):
                        selector = query_match.group(1).strip()
                        if selector.startswith("."):
                            js_callees.append("css:{}".format(selector))
                        elif selector.startswith("#"):
                            js_callees.append("dom:{}".format(selector[1:]))
                        elif selector and selector.replace("-", "").isalnum():
                            js_callees.append("dom:{}".format(selector))
                    for func_match in _EMBED_JS_FUNC_RE.finditer(js_text):
                        func_name = func_match.group(1)
                        key = "{}::js:{}".format(rel, func_name)
                        if key not in anchors:
                            anchors[key] = Anchor(
                                id=key, symbol="js:{}".format(func_name),
                                file=rel, line_start=line, line_end=line,
                                hash="", language="javascript", symbol_type="function",
                                callees=list(js_callees),
                            )
                        embedded_keys.append(key)

                if not embedded_keys:
                    continue

                current = parent_map.get(id(node))
                while current is not None:
                    if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        parent = parent_map.get(id(current))
                        if isinstance(parent, ast.ClassDef):
                            py_symbol = "{}.{}".format(parent.name, current.name)
                        else:
                            py_symbol = current.name
                        py_anchor = anchors.get("{}::{}".format(rel, py_symbol))
                        if py_anchor is not None:
                            for embedded_key in embedded_keys:
                                if embedded_key not in py_anchor.callees:
                                    py_anchor.callees.append(embedded_key)
                        break
                    current = parent_map.get(id(current))
    except Exception as e:
        failed.append("embedded_dom: {}".format(e))

    from collections import defaultdict as _defaultdict
    _by_file2: dict = _defaultdict(list)
    for _anchor2 in anchors.values():
        if _anchor2.language == "python" and _anchor2.symbol_type != "class":
            _by_file2[_anchor2.file].append(_anchor2)
    for _rel_file2, _file_anchors2 in _by_file2.items():
        try:
            _source2 = (root / _rel_file2).read_text(encoding="utf-8", errors="replace")
            _tree2 = ast.parse(_source2)
        except Exception:
            continue
        for _anchor2 in _file_anchors2:
            try:
                _call_sites2 = _extract_call_sites_from_tree(_tree2, _anchor2.symbol)
                if _call_sites2:
                    _anchor2.call_sites = _call_sites2
                    _anchor2.callees = [s["target"] for s in _call_sites2]
                _inputs2, _outputs2 = _extract_function_io_from_tree(_tree2, _anchor2.symbol)
                if _inputs2:
                    _anchor2.inputs = _inputs2
                if _outputs2:
                    _anchor2.outputs = _outputs2
            except Exception:
                pass

    try:
        from inheritance import build_class_index, compute_mro, find_subclasses
        from inheritance import resolve_inheritance
        from inheritance.override_analyzer import build_override_chain
        index = build_class_index(str(root))
        _apply_inheritance_refs(anchors, index, compute_mro, find_subclasses)
        for anchor in anchors.values():
            if anchor.symbol_type != "method" or anchor.language != "python":
                continue
            try:
                class_name = anchor.symbol.split(".")[0] if "." in anchor.symbol else None
                if not class_name:
                    continue
                chain_objs = resolve_inheritance(class_name, index)
                chain_dicts = [e.to_dict() for e in chain_objs]
                method_name = anchor.symbol.split(".")[-1]
                override_chain = build_override_chain(chain_dicts, method_name)
                if (len(override_chain) > 1
                        and override_chain[0]["class"] == class_name):
                    anchor.overrides = override_chain[1]["class"]
            except Exception:
                pass
        _build_effective_methods_table(anchors)
    except Exception as e:
        failed.append("inheritance: {}".format(e))

    if include_virtual_blocks:
        try:
            from api.control_flow_blocks import _ControlFlowBlockExtractor
            for py_file in py_files:
                try:
                    rel = _normalize_file_ref(root, py_file)
                    source = py_file.read_text(encoding="utf-8", errors="replace")
                    anchors.update(_ControlFlowBlockExtractor(root, rel, source).extract())
                except Exception:
                    continue
        except Exception as e:
            failed.append("control_flow_blocks: {}".format(e))

    return anchors, failed


def update_anchors_for_files(root=".", changed_files=None, include_virtual_blocks=False) -> dict:
    root = Path(root)
    changed_files = changed_files or []
    ignore = CodeDendriteIgnore(str(root))
    normalized_changed = {
        _normalize_file_ref(root, f)
        for f in changed_files
    }

    try:
        anchors = load_anchors(str(root))
    except FileNotFoundError:
        anchors = {}

    before = len(anchors)
    anchors = {
        key: anchor
        for key, anchor in anchors.items()
        if _normalize_file_ref(root, anchor.file) not in normalized_changed
    }
    removed = before - len(anchors)

    file_paths = []
    for rel in sorted(normalized_changed):
        path = root / rel
        if path.exists() and path.is_file() and ignore.should_scan(path):
            file_paths.append(path)

    new_anchors, failed = _generate_anchors_for_paths(
        root,
        file_paths,
        include_virtual_blocks=include_virtual_blocks,
    )
    anchors.update(new_anchors)
    try:
        from inheritance import build_class_index, compute_mro, find_subclasses
        index = build_class_index(str(root))
        _apply_inheritance_refs(anchors, index, compute_mro, find_subclasses)
        _build_effective_methods_table(anchors)
    except Exception as e:
        failed.append("inheritance: {}".format(e))
    _finalize_anchor_graph(anchors)
    _write_anchors(root, anchors)

    return {
        "before": before,
        "removed": removed,
        "created": len(new_anchors),
        "total_anchors": len(anchors),
        "failed": len(failed),
        "errors": failed,
    }


def load_anchors(root=".") -> dict:
    """加载 anchors.json，返回 {key: Anchor} 字典"""
    path = Path(root) / ".codedendrite" / "anchors.json"
    if not path.exists():
        raise FileNotFoundError(
            "先执行 generate_all_anchors(root='{}')".format(root)
        )
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    def _coerce_callers(lst):
        result = []
        for item in (lst or []):
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                result.append(item.get("target") or item.get("symbol") or item.get("id") or "")
            else:
                result.append(str(item))
        return result

    def _coerce_callees(lst):
        result = []
        for item in (lst or []):
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                result.append(item)
            else:
                result.append(str(item))
        return result

    result = {}
    for k, v in data.items():
        for field_name, default_value in ANCHOR_DEFAULTS.items():
            if field_name not in v:
                if isinstance(default_value, (list, dict)):
                    v[field_name] = default_value.copy()
                else:
                    v[field_name] = default_value
        v["callers"] = _coerce_callers(v.get("callers"))
        v["callees"] = _coerce_callees(v.get("callees"))
        result[k] = Anchor(**v)
    return result


def get_anchor(symbol: str, root=".") -> Optional[Anchor]:
    """按符号名查找锚点（精确 > 后缀匹配）"""
    anchors = load_anchors(root)
    for a in anchors.values():
        if a.symbol == symbol:
            return a
    for a in anchors.values():
        if a.symbol.endswith("." + symbol) or a.id.endswith("::" + symbol):
            return a
    return None


def search_anchors(keyword: str, root=".", file_prefix: str = None,
                   symbol_type: str = None, top_n: int = None) -> List[Anchor]:
    """
    模糊搜索锚点，返回匹配列表。

    参数：
        keyword     — 在 symbol 名中做子串匹配（空字符串 = 不过滤）
        root        — 目标项目路径
        file_prefix — 只返回该文件路径前缀下的锚点，如 "api" / "src/trainer"
        symbol_type — 只返回指定类型："function" / "method" / "class"
        top_n       — 最多返回 N 条
    """
    anchors = load_anchors(root)
    results = []
    for a in anchors.values():
        if keyword and keyword not in a.symbol:
            continue
        if file_prefix and not a.file.startswith(file_prefix):
            continue
        if symbol_type and a.symbol_type != symbol_type:
            continue
        results.append(a)
        if top_n and len(results) >= top_n:
            break
    return results


def filter_anchors_by_file(keyword: str, root: str = ".") -> dict:
    """过滤文件路径包含关键词的锚点。"""
    anchors = load_anchors(root)
    kw = keyword.lower()
    result = {}
    for aid, a in anchors.items():
        f = a.file if hasattr(a, 'file') else a.get('file', '')
        if kw in f.lower():
            result[aid] = a
    return result


def list_anchors_in_file(
    file_path: str,
    root: str = ".",
    include_virtual: bool = False,
    symbol_types: Optional[List[str]] = None,
) -> dict:
    """列出单个文件内的 anchors，默认不含 virtual_block。"""
    anchors = load_anchors(root)
    normalized = file_path.replace("\\", "/").lower()
    result = {}
    allowed = set(symbol_types or ["function", "method", "class"])
    for aid, anchor in anchors.items():
        anchor_file = (anchor.file if hasattr(anchor, "file") else anchor.get("file", "")).replace("\\", "/")
        if anchor_file.lower() != normalized:
            continue
        anchor_type = anchor.symbol_type if hasattr(anchor, "symbol_type") else anchor.get("symbol_type", "")
        is_virtual = anchor.is_virtual if hasattr(anchor, "is_virtual") else anchor.get("is_virtual", False)
        if is_virtual and not include_virtual:
            continue
        if allowed and anchor_type not in allowed and not (include_virtual and anchor_type == "virtual_block"):
            continue
        result[aid] = anchor
    return result


__all__ = [
    "list_all_symbols",
    "list_anchors",
    "create_anchor",
    "check_all_anchors",
    "generate_all_anchors",
    "update_anchors_for_files",
    "load_anchors",
    "get_anchor",
    "search_anchors",
    "filter_anchors_by_file",
    "list_anchors_in_file",
]
