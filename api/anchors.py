"""
锚点管理接口层
========================
generate_all_anchors: 从 5 个源 merge，写入 .codedendrite/anchors.json
load_anchors / get_anchor: 唯一读取接口
"""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional, List

from shared.types import Anchor
from shared.codedendrite_ignore import CodeDendriteIgnore

BUILTIN_NOISE = {
    "print", "append", "get", "len", "str", "int", "list", "dict",
    "set", "type", "range", "enumerate", "zip", "map", "filter",
    "isinstance", "hasattr", "getattr", "setattr", "open", "any",
    "all", "sorted", "reversed", "join", "split", "format", "update",
    "extend", "items", "values", "keys", "pop", "insert", "read",
    "write", "close", "encode", "decode", "replace", "strip",
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


def _resolve_call_id(raw_callee, anchors: dict, unique_symbol_ids: dict, caller_file: str | None = None) -> str | None:
    target = _call_target(raw_callee)
    if not target:
        return None
    target = str(target).replace("\\", "/")
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
    "inputs": [],
    "outputs": [],
    "parent_classes": [],
    "overrides": None,
    "overridden_by": [],
    "mro": [],
    "observations": [],
    "language": "python",
    "symbol_type": "function",
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
        for raw_callee in anchor.callees:
            target_id = _resolve_call_id(raw_callee, anchors, unique_symbol_ids, caller_file=anchor.file)
            if not target_id:
                continue
            if isinstance(raw_callee, dict):
                item = dict(raw_callee)
                item["target"] = target_id
                normalized_callees.append(item)
            else:
                normalized_callees.append(target_id)
        anchor.callees = normalized_callees

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

def generate_all_anchors(root=".", exclude_dirs=None, include_virtual_blocks=True) -> dict:
    root = Path(root)
    output_path = root / ".codedendrite" / "anchors.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    exclude = set(exclude_dirs or [])
    ignore = CodeDendriteIgnore(str(root))

    anchors: dict = {}
    failed = []

    # ── 源 1: codeGenome ──────────────────────────────────────
    try:
        from codeGenome import scan_project as genome_scan
        query = genome_scan(str(root))

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

    # ── 源 2: codeAnalysis（补 codeGenome 缺失的 Python 符号）──
    try:
        from codeAnalysis.analyzer import get_analyzer
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
                rel = str(py_file.relative_to(root))
            except ValueError:
                rel = str(py_file)
            try:
                analyzer = get_analyzer(str(root), language="python")
                module = analyzer.analyze_file(str(py_file))

                for cls in module.classes:
                    key_cls = "{}::{}".format(rel, cls.name)
                    if key_cls not in anchors:
                        anchors[key_cls] = Anchor(
                            id=key_cls, symbol=cls.name, file=rel,
                            line_start=cls.line_number, line_end=cls.line_number,
                            hash="", language="python", symbol_type="class",
                        )
                    for method in getattr(cls, "methods", []):
                        # symbol 格式统一为 ClassName.method_name，便于 override 检测
                        qualified = "{}.{}".format(cls.name, method.name)
                        mkey = "{}::{}".format(rel, qualified)
                        if mkey not in anchors:
                            anchors[mkey] = Anchor(
                                id=mkey, symbol=qualified, file=rel,
                                line_start=method.line_number, line_end=method.line_number,
                                hash="", language="python", symbol_type="method",
                            )

                for func in module.functions:
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

    # ── 源 3: dataFlow（callees / inputs / outputs）────────────
    try:
        from dataFlow import analyze_function_flow
        for key, anchor in anchors.items():
            if anchor.language != "python" or anchor.symbol_type == "class":
                continue
            try:
                flow = analyze_function_flow(str(root / anchor.file), anchor.symbol)
                if flow:
                    # 提取 FunctionCall 的 target 字符串
                    anchor.callees = [c.target if hasattr(c, 'target') else str(c) for c in (flow.calls or [])]
                    anchor.inputs = [
                        {"name": v.name, "type": v.var_type or ""}
                        for v in (flow.inputs or [])
                    ]
                    anchor.outputs = [
                        {"name": v.name, "type": v.var_type or ""}
                        for v in (flow.outputs or [])
                    ]
            except Exception:
                pass
    except Exception as e:
        failed.append("dataFlow: {}".format(e))

    # ── 源 4: inheritance（mro / parent_classes / overridden_by / overrides）
    try:
        from inheritance import build_class_index, compute_mro, find_subclasses
        from inheritance import resolve_inheritance
        from inheritance.override_analyzer import build_override_chain

        index = build_class_index(str(root))

        _apply_inheritance_refs(anchors, index, compute_mro, find_subclasses)

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
                # override_chain 按继承链从子到根排列：
                # chain[0] = 当前类（is_override=False），chain[1..] = 父类（is_override=True）
                # 只要 chain 长度 > 1 且 chain[0] 是当前类，说明该方法覆盖了父类
                if (len(override_chain) > 1
                        and override_chain[0]["class"] == class_name):
                    anchor.overrides = override_chain[1]["class"]
            except Exception:
                pass
    except Exception as e:
        failed.append("inheritance: {}".format(e))

    # ── 源 5: control flow virtual blocks（if / loop / try）─────
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
    unique_symbol_ids = _build_unique_symbol_ids(anchors)
    for anchor in anchors.values():
        normalized_callees = []
        for raw_callee in anchor.callees:
            target_id = _resolve_call_id(raw_callee, anchors, unique_symbol_ids, caller_file=anchor.file)
            if not target_id:
                continue
            if isinstance(raw_callee, dict):
                item = dict(raw_callee)
                item["target"] = target_id
                normalized_callees.append(item)
            else:
                normalized_callees.append(target_id)
        anchor.callees = normalized_callees

    for anchor in anchors.values():
        anchor.callers = []
    for key, anchor in anchors.items():
        if anchor.is_virtual:
            continue
        for raw_callee in anchor.callees:
            target_id = _call_target(raw_callee)
            target = anchors.get(target_id)
            if not target:
                continue
            if anchor.id not in target.callers:
                target.callers.append(anchor.id)

    # ── 写入 anchors.json ──────────────────────────────────────
    data = {k: _anchor_to_storage(v) for k, v in anchors.items()}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    include_virtual_blocks: bool = True,
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
                    key_cls = "{}::{}".format(rel, cls.name)
                    if key_cls not in anchors:
                        anchors[key_cls] = Anchor(
                            id=key_cls, symbol=cls.name, file=rel,
                            line_start=cls.line_number, line_end=cls.line_number,
                            hash="", language="python", symbol_type="class",
                        )
                    for method in getattr(cls, "methods", []):
                        qualified = "{}.{}".format(cls.name, method.name)
                        mkey = "{}::{}".format(rel, qualified)
                        if mkey not in anchors:
                            anchors[mkey] = Anchor(
                                id=mkey, symbol=qualified, file=rel,
                                line_start=method.line_number, line_end=method.line_number,
                                hash="", language="python", symbol_type="method",
                            )
                for func in module.functions:
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
        from dataFlow import analyze_function_flow
        for anchor in anchors.values():
            if anchor.language != "python" or anchor.symbol_type == "class":
                continue
            try:
                flow = analyze_function_flow(str(root / anchor.file), anchor.symbol)
                if flow:
                    anchor.callees = [c.target if hasattr(c, "target") else str(c) for c in (flow.calls or [])]
                    anchor.inputs = [
                        {"name": v.name, "type": v.var_type or ""}
                        for v in (flow.inputs or [])
                    ]
                    anchor.outputs = [
                        {"name": v.name, "type": v.var_type or ""}
                        for v in (flow.outputs or [])
                    ]
            except Exception:
                pass
    except Exception as e:
        failed.append("dataFlow: {}".format(e))

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


def update_anchors_for_files(root=".", changed_files=None, include_virtual_blocks=True) -> dict:
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
