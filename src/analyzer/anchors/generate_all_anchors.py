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

from analyzer.anchors.call_site_collector import _alog
from analyzer.anchors.build_effective_methods_table import _anchor_to_storage, _apply_inheritance_refs, _build_effective_methods_table, _extract_call_sites_from_tree, _extract_function_io_from_tree
from analyzer.anchors.resolve import _finalize_anchor_graph, _module_anchor_for_file, _normalize_file_ref
from analyzer.anchors.core_anchor import _merge_code_anchor, _merge_parsed_anchor, _slow_warn

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
        from scanner import scan_project as genome_scan
        _alog("源1 codeGenome.scan_project START (whole project)")
        _g0 = _time.perf_counter()
        query = genome_scan(str(root))
        _alog(f"源1 codeGenome.scan_project DONE {_time.perf_counter()-_g0:.1f}s")
        parse_failures.extend(getattr(query, 'parse_failures', []))
        auto_fixed.extend(getattr(query, 'auto_fixed', []))

        for ca in (query.find_functions() + query.find_classes()
                   + query.find_methods() + query.find_main_blocks()):
            if not ignore.should_scan(Path(ca.file)):
                continue
            if any(p in exclude for p in Path(ca.file).parts):
                continue
            _merge_code_anchor(anchors, ca, root)
    except Exception as e:
        failed.append("codeGenome: {}".format(e))

    # Python module bodies are executable code too.  Keep one anchor only for
    # files that actually make top-level calls (including ``if __main__``).
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            directory = Path(dirpath)
            dirnames[:] = [
                name for name in dirnames
                if ignore.should_scan(directory / name / "_x.py")
                and name not in exclude
            ]
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                file_path = directory / filename
                if not ignore.should_scan(file_path):
                    continue
                module_anchor = _module_anchor_for_file(root, file_path)
                if module_anchor is not None:
                    anchors[module_anchor.id] = module_anchor
    except Exception as e:
        failed.append("python_module_entries: {}".format(e))
    try:
        from scanner.language import get_analyzer
        _alog(f"源2 codeAnalysis per-.py analyze START (phase elapsed {_time.perf_counter()-_phase0:.1f}s)")
        def _iter_py(root_p):
            for dirpath, dirnames, filenames in os.walk(root_p):
                dp = Path(dirpath)
                dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.py")]
                for fname in filenames:
                    if fname.endswith(".py"):
                        yield dp / fname

        for py_file in _iter_py(root):
            if not ignore.should_scan(py_file):
                continue
            if any(p in exclude for p in py_file.parts):
                continue
            try:
                rel = str(py_file.relative_to(root)).replace("\\", "/")
            except ValueError:
                rel = str(py_file).replace("\\", "/")
            try:
                analyzer = get_analyzer(str(root), language="python")
                _t0 = _time.perf_counter()
                module = analyzer.analyze_file(str(py_file))
                _slow_warn("py.analyze", rel, _time.perf_counter() - _t0)

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
                        # symbol 格式统一为 ClassName.method_name，便于 override 检测
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
            except Exception:
                pass
    except Exception as e:
        failed.append("codeAnalysis: {}".format(e))

    # ── 源 2a2: inline <script> blocks inside .html ───────────
    # _TS_EXTS never included .html, so a page's real logic living in an
    # inline <script> — as opposed to a linked .js file — was invisible to
    # every pass above: not walked, not opened, not scanned, regardless of
    # what the script contained. This is a directory-walk filter problem,
    # not a parsing one, so the fix is a second small pass rather than
    # touching _TS_EXTS itself (a bare .html file is markup first; running
    # the JS extractor over the whole document would match against tag
    # attributes and text content that only coincidentally look like code).
    try:
        html_ts_analyzer = get_analyzer(str(root), language="typescript")
        _script_re = _re.compile(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', _re.I | _re.S)
        for dirpath, dirnames, filenames in os.walk(root):
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.html")]
            for fname in filenames:
                if Path(fname).suffix.lower() != ".html":
                    continue
                html_file = dp / fname
                if not ignore.should_scan(html_file):
                    continue
                if any(p in exclude for p in html_file.parts):
                    continue
                try:
                    rel = str(html_file.relative_to(root)).replace("\\", "/")
                except ValueError:
                    rel = str(html_file).replace("\\", "/")
                try:
                    doc = html_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for match in _script_re.finditer(doc):
                    content = match.group(1)
                    if not content.strip():
                        continue
                    # Line 1 of this block's own text is the line the <script>
                    # tag's body actually starts on in the full document —
                    # every function found inside needs that offset added so
                    # line_start points at the real file, not a 1-based count
                    # that resets at every <script> tag.
                    script_line = doc[:match.start(1)].count("\n") + 1
                    try:
                        functions = html_ts_analyzer._extract_functions(content, rel)
                    except Exception:
                        continue
                    for func in functions:
                        if not func.name:
                            continue
                        fkey = "{}::{}".format(rel, func.name)
                        if fkey in anchors:
                            continue
                        local_line = getattr(func, "line_number", 1)
                        anchors[fkey] = Anchor(
                            id=fkey, symbol=func.name, file=rel,
                            line_start=script_line + local_line - 1,
                            line_end=script_line + local_line - 1,
                            hash="", language="javascript", symbol_type="function",
                            callees=list(getattr(func, "calls", None) or []),
                        )
    except Exception as e:
        failed.append("html_inline_script: {}".format(e))

    # ── 统一语言适配层 ────────────────────────────────────────
    # Dedicated Python extraction above remains the richest implementation.
    # Every other language now enters through the same path used by update,
    # so a rebuild and an incremental refresh cannot disagree by language.
    try:
        from scanner.language.pipeline import parse_paths, walk_source_paths
        source_paths = walk_source_paths(root, ignore=ignore, exclude_dirs=exclude)
        parsed, language_failures, _completed = parse_paths(root, source_paths)
        for parsed_anchor in parsed.values():
            _merge_parsed_anchor(anchors, parsed_anchor)
        failed.extend(language_failures)
    except Exception as e:
        failed.append("language_pipeline: {}".format(e))


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
        from analyzer.inherit.language.python import build_class_index, compute_mro, find_subclasses
        from analyzer.inherit.language.python import resolve_inheritance
        from analyzer.inherit.language.python.override_analyzer import build_override_chain

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
            from api.control_flow import extract_file_control_flow
            from scanner.language.pipeline import walk_source_paths
            for source_file in walk_source_paths(root, ignore=ignore, exclude_dirs=exclude):
                rel = _normalize_file_ref(root, source_file)
                source = source_file.read_text(encoding="utf-8", errors="replace")
                for key, block_anchor in extract_file_control_flow(root, rel, source).items():
                    if key not in anchors:
                        anchors[key] = block_anchor
        except Exception as e:
            failed.append("control_flow_blocks: {}".format(e))

    # ── 运行时桥：HTTP 与 JS Worker 的可证明异步跳转 ──────────
    try:
        from api.bridges import apply_runtime_bridges
        apply_runtime_bridges(root, anchors)
    except Exception as e:
        failed.append("runtime_bridges: {}".format(e))

    # ── 反向构建 callers ──────────────────────────────────────
    _finalize_anchor_graph(anchors, root=root)

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
