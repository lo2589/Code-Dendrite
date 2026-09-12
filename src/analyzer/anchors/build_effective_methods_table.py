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

from analyzer.shared.types import Anchor
from analyzer.shared.codedendrite_ignore import CodeDendriteIgnore
from analyzer.shared.formula_skip import should_skip as _should_skip_formula

_EMBED_STYLE_RE = _re.compile(r'<style[^>]*>(.*?)</style>', _re.DOTALL | _re.IGNORECASE)
_EMBED_SCRIPT_RE = _re.compile(r'<script[^>]*>(.*?)</script>', _re.DOTALL | _re.IGNORECASE)
_EMBED_DOM_ID_RE = _re.compile(r'\bid=["\']([A-Za-z][\w-]*)["\']')
_EMBED_CSS_SEL_RE = _re.compile(r'(?:^|[\s,>+~])([.#][A-Za-z][\w-]*)', _re.MULTILINE)
_EMBED_JS_FUNC_RE = _re.compile(r'function\s+([A-Za-z$_][\w$]*)\s*\(')
_EMBED_JS_QUERY_RE = _re.compile(r'(?:querySelectorAll?|getElementById)\s*\(\s*["\']([^"\']+)["\']')

# ── 调试日志（环境变量 CD_ANCHOR_LOG 开关；默认不打，不污染生产 run）──
import time as _time
_ANCHOR_DBG = bool(os.environ.get("CD_ANCHOR_LOG"))

from analyzer.anchors.subscript_string import ANCHOR_DEFAULTS
from analyzer.anchors.call_site_collector import _CallSiteCollector

def _anchor_to_storage(anchor: Anchor) -> dict:
    data = asdict(anchor)
    return {
        key: value
        for key, value in data.items()
        if key not in ANCHOR_DEFAULTS or value != ANCHOR_DEFAULTS[key]
    }

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

def _build_leaf_symbol_ids(anchors: dict) -> tuple[dict, dict]:
    """Return unique leaf targets and every candidate for ambiguity reporting."""
    candidates: dict[str, list[str]] = {}
    for anchor in anchors.values():
        if anchor.symbol_type == "class" or anchor.is_virtual:
            continue
        leaf = str(anchor.symbol or "").replace("::", ".").rsplit(".", 1)[-1]
        if leaf:
            candidates.setdefault(leaf, []).append(anchor.id)
    unique = {leaf: ids[0] for leaf, ids in candidates.items() if len(ids) == 1}
    return unique, candidates

def _call_target(raw_callee):
    if isinstance(raw_callee, dict):
        return raw_callee.get("target", "")
    return raw_callee

def _code_anchor_symbol(ca) -> tuple[str, str] | None:
    """Return the public symbol/type while accepting legacy codeGenome IDs."""
    if ca.category in ("classes", "structs"):
        return ca.name, "class"
    if ca.category == "methods":
        if "::" in ca.id:
            symbol = ca.id.split("::", 1)[1]
            return symbol, "method"
        parts = ca.parent_id.split(".") if ca.parent_id else []
        class_name = ""
        if "classes" in parts:
            idx = parts.index("classes")
            if idx + 1 < len(parts):
                class_name = parts[idx + 1]
        symbol = "{}.{}".format(class_name, ca.name) if class_name else ca.name
        return symbol, "method"
    if ca.category == "functions":
        return ca.name, "function"
    if ca.category == "__main__":
        # A Python main guard is executable structure with its own call edges,
        # not anonymous module noise. Its extractor id carries an asset suffix;
        # the public graph uses the stable symbol users actually see in code.
        return "__main__", "entrypoint"
    return None


def _is_main_guard(node: ast.AST) -> bool:
    """Whether *node* is ``if __name__ == '__main__'`` (either operand order)."""
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq) or len(test.comparators) != 1:
        return False

    def is_name(value: ast.AST) -> bool:
        return isinstance(value, ast.Name) and value.id == "__name__"

    def is_main(value: ast.AST) -> bool:
        return isinstance(value, ast.Constant) and value.value == "__main__"

    return ((is_name(test.left) and is_main(test.comparators[0]))
            or (is_main(test.left) and is_name(test.comparators[0])))

def _collect_import_aliases(tree: ast.AST, function_node: ast.AST) -> dict:
    aliases = {}

    def record(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                module = alias.name if alias.asname else bound
                aliases[bound] = {
                    "module": module,
                    "imported": "",
                    "level": 0,
                }
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                aliases[bound] = {
                    "module": node.module or "",
                    "imported": alias.name,
                    "level": int(node.level or 0),
                }

    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            record(node)
    for node in ast.walk(function_node):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            record(node)
    return aliases

def _find_function_node(tree: ast.AST, symbol: str):
    if symbol == "__main__":
        for node in getattr(tree, "body", []):
            if _is_main_guard(node):
                return node
        return None
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

def _extract_call_sites_from_tree(tree: ast.AST, symbol: str) -> list[dict]:
    node = _find_function_node(tree, symbol)
    if not node:
        return []
    collector = _CallSiteCollector(_collect_import_aliases(tree, node))
    for stmt in node.body:
        collector.visit(stmt)
    return collector.call_sites

def _extract_call_sites(file_path: Path, symbol: str) -> list[dict]:
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception:
        return []
    return _extract_call_sites_from_tree(tree, symbol)

def _extract_function_io_from_tree(tree: ast.AST, symbol: str) -> tuple:
    node = _find_function_node(tree, symbol)
    if not node or not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
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

def _extract_module_call_sites(tree: ast.AST) -> list[dict]:
    """Collect import-time/top-level calls without entering definitions."""
    aliases = {}

    def collect_imports(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                aliases[bound] = {
                    "module": alias.name if alias.asname else bound,
                    "imported": "",
                    "level": 0,
                }
            return
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = {
                        "module": node.module or "",
                        "imported": alias.name,
                        "level": int(node.level or 0),
                    }
            return
        for child in ast.iter_child_nodes(node):
            collect_imports(child)

    for statement in getattr(tree, "body", []):
        collect_imports(statement)

    collector = _CallSiteCollector(aliases)
    for statement in getattr(tree, "body", []):
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                  ast.Import, ast.ImportFrom)) or _is_main_guard(statement):
            continue
        collector.visit(statement)
    return collector.call_sites

def _extract_registered_as(decorators: list) -> Optional[str]:
    for dec in decorators:
        if isinstance(dec, dict) and dec.get("key"):
            return dec["key"]
    return None

def _registration_entries(anchor) -> list[dict]:
    entries = []
    scalar = str(getattr(anchor, "registered_as", "") or "")
    if scalar:
        entries.append({"key": scalar, "name": ""})
    for item in getattr(anchor, "block_metadata", {}).get("decorators", []) or []:
        if not isinstance(item, dict) or not item.get("key"):
            continue
        entry = {"key": str(item["key"]), "name": str(item.get("name") or "")}
        if entry not in entries:
            entries.append(entry)
    return entries

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
