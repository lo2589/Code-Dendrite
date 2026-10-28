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

from analyzer.anchors.build_effective_methods_table import _anchor_to_storage, _apply_inheritance_refs, _build_effective_methods_table, _code_anchor_symbol, _extract_call_sites_from_tree, _extract_function_io_from_tree, _extract_registered_as
from analyzer.anchors.resolve import _finalize_anchor_graph, _module_anchor_for_file, _normalize_file_ref, _normalize_registration_decorators

def _merge_code_anchor(anchors: dict, ca, root: Path) -> None:
    try:
        rel = str(Path(ca.file).relative_to(root)).replace("\\", "/")
    except ValueError:
        rel = _normalize_file_ref(root, ca.file)

    symbol_info = _code_anchor_symbol(ca)
    if symbol_info is None:
        return
    symbol, sym_type = symbol_info

    lang_map = {"py": "python", "cpp": "cpp"}
    lang = lang_map.get(ca.language, ca.language)

    key = "{}::{}".format(rel, symbol)
    decorators = ca.metadata.get("decorators", [])
    dec_meta = _normalize_registration_decorators(decorators, symbol)
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
        registered_as=_extract_registered_as(dec_meta),
        block_metadata=(
            {"main_entry": True}
            if ca.category == "__main__"
            else ({"decorators": dec_meta} if dec_meta else {})
        ),
    )

def _merge_parsed_anchor(anchors: dict, parsed) -> None:
    """Merge one language-adapter record without weakening a richer anchor."""
    existing = anchors.get(parsed.id)
    if existing is None:
        anchors[parsed.id] = Anchor(
            id=parsed.id,
            symbol=parsed.symbol,
            file=parsed.file,
            line_start=parsed.line_start,
            line_end=parsed.line_end,
            hash=parsed.hash,
            language=parsed.language,
            symbol_type=parsed.symbol_type,
            qualified_name=parsed.symbol,
            signature=parsed.signature,
            imports=list(parsed.imports),
            parent_anchor=parsed.parent_anchor,
            callees=list(parsed.callees),
            call_sites=[dict(site) for site in parsed.call_sites],
            block_metadata=dict(getattr(parsed, "block_metadata", {}) or {}),
            registered_as=getattr(parsed, "registered_as", None),
        )
        return
    if parsed.line_end > existing.line_end:
        existing.line_end = parsed.line_end
    if not existing.parent_anchor and parsed.parent_anchor:
        existing.parent_anchor = parsed.parent_anchor
    if not existing.qualified_name:
        existing.qualified_name = parsed.symbol
    if not existing.signature:
        existing.signature = parsed.signature
    if not existing.imports:
        existing.imports = list(parsed.imports)
    # Analyzer call sites are useful even when codeGenome supplied the anchor.
    if parsed.call_sites and not existing.call_sites:
        existing.call_sites = [dict(site) for site in parsed.call_sites]
        existing.callees = list(parsed.callees)
    if getattr(parsed, "block_metadata", None):
        existing.block_metadata.update(parsed.block_metadata)
    if not existing.registered_as and getattr(parsed, "registered_as", None):
        existing.registered_as = parsed.registered_as

def _generate_anchors_for_paths(
    root: Path,
    file_paths: list[Path],
    include_virtual_blocks: bool = False,
) -> tuple[dict, list, set[str]]:
    anchors: dict = {}
    failed = []
    completed: set[str] = set()

    try:
        from scanner.language.python.genome import extract_python_file
        from scanner.language.cpp.genome import extract_cpp_file
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
                completed.add(_normalize_file_ref(root, file_path))
            except Exception as e:
                failed.append("{}: {}".format(file_path, e))
    except Exception as e:
        failed.append("codeGenome: {}".format(e))

    try:
        from scanner.language.pipeline import parse_paths
        # `include_python=True` 不能省。默认是 False，Python 文件会被整批跳过，
        # `_merge_parsed_anchor` 于是从来不为它们跑——增量更新出来的 anchor 就
        # 缺 qualified_name / signature / imports，而全量重建是有的。同一份代码
        # 走两条路得到两种记录，索引会随着每次编辑悄悄退化。
        parsed, language_failures, language_completed = parse_paths(
            root, file_paths, include_python=True
        )
        for parsed_anchor in parsed.values():
            _merge_parsed_anchor(anchors, parsed_anchor)
        failed.extend(language_failures)
        completed.update(language_completed)
    except Exception as e:
        failed.append("language_pipeline: {}".format(e))

    py_files = [p for p in file_paths if p.suffix == ".py"]
    try:
        from scanner.language import get_analyzer
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
            else:
                completed.add(rel)
    except Exception as e:
        failed.append("codeAnalysis: {}".format(e))

    for py_file in py_files:
        module_anchor = _module_anchor_for_file(root, py_file)
        if module_anchor is not None:
            anchors[module_anchor.id] = module_anchor

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
        from analyzer.inherit.language.python import build_class_index, compute_mro, find_subclasses
        from analyzer.inherit.language.python import resolve_inheritance
        from analyzer.inherit.language.python.override_analyzer import build_override_chain
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
            from analyzer.control_flow.file_blocks import extract_file_control_flow
            for source_file in file_paths:
                try:
                    rel = _normalize_file_ref(root, source_file)
                    source = source_file.read_text(encoding="utf-8", errors="replace")
                    anchors.update(extract_file_control_flow(root, rel, source))
                except Exception:
                    continue
        except Exception as e:
            failed.append("control_flow_blocks: {}".format(e))

    return anchors, failed, completed

def _slow_warn(phase: str, rel: str, dt: float, thresh: float = 1.0):
    """逐文件计时；超过阈值的单独标 SLOW，方便一眼揪出卡的文件。"""
    if _ANCHOR_DBG:
        tag = "  <<< SLOW" if dt >= thresh else ""
        print(f"[anchors {_time.strftime('%H:%M:%S')}] {phase} {rel}  {dt*1000:.0f}ms{tag}", flush=True)

def _write_anchors(root: Path, anchors: dict) -> None:
    output_path = root / ".codedendrite" / "anchors.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: _anchor_to_storage(v) for k, v in anchors.items()}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # One file for every ambiguous name, instead of one copy per call site.
    # A site carries the name; this is what the name means. Kept beside the
    # anchors rather than inside them so nothing that walks anchors.json as a
    # flat map of anchors has to learn about a new top-level key.
    table = getattr(_finalize_anchor_graph, "last_ambiguous", None)
    if isinstance(table, dict):
        with open(output_path.parent / "candidates.json", "w", encoding="utf-8") as f:
            json.dump(table, f, ensure_ascii=False, indent=2)

def check_all_anchors(root):
    from analyzer.repair.anchor_repair import check_all_anchors as _check_all_anchors
    return _check_all_anchors(root)

def create_anchor(anchor_id, file, symbol=None, line_start=None, line_end=None,
                  description="", hash_mode="struct", language="python", root="."):
    from analyzer.identity.engine import create_anchor as _create_anchor
    return _create_anchor(anchor_id, file, symbol, line_start, line_end,
                          description, hash_mode, language, root)
