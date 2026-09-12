"""
锚点管理接口层
========================
generate_all_anchors: 从 5 个源 merge，写入 .codedendrite/anchors.json
load_anchors / get_anchor: 唯一读取接口
"""

import json
import os
import ast
import posixpath
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

from analyzer.anchors.subscript_string import BUILTIN_NOISE
from analyzer.anchors.build_effective_methods_table import _build_leaf_symbol_ids, _build_unique_class_ids, _build_unique_symbol_ids, _call_target, _extract_module_call_sites, _registration_entries, _resolve_super_call

_JS_LANGUAGES = {"javascript", "typescript", "js", "ts", "jsx", "tsx"}


class _ResolveIndex:
    """解析循环里复用的一份查表。

    这两条解析路径原来每个调用点都要把整个 anchors 扫一遍找目标：一个仓库 4632 次
    调用 × 9244 个锚点 ≈ 4300 万次比较，光这一步就 36 秒 CPU；而且和"这次改了哪个
    文件"无关，增量更新也照扫。表建一次，之后都是字典查——判断条件一个字没改，
    只是候选集从"全部锚点"缩成"对得上的那几个"。
    """

    def __init__(self, anchors: dict):
        self.by_symbol: dict = {}
        self.by_file_tail: dict = {}
        for anchor in anchors.values():
            symbol = str(anchor.symbol or "")
            self.by_symbol.setdefault(symbol, []).append(anchor.id)
            key = (anchor.file.replace("\\", "/"), symbol.rsplit(".", 1)[-1])
            self.by_file_tail.setdefault(key, []).append(anchor.id)


def _resolve_import_attribute(target: str, raw_callee: dict, anchors: dict,
                              caller_file: str | None,
                              index: "_ResolveIndex | None" = None) -> Optional[str]:
    """Resolve ``module_alias.func()`` when the alias comes from an import."""
    ref = raw_callee.get("import_ref")
    if not isinstance(ref, dict) or not caller_file:
        return None

    module = str(ref.get("module") or "")
    imported = str(ref.get("imported") or "")
    level = int(ref.get("level") or 0)
    module_parts = [part for part in module.split(".") if part]
    imported_parts = [part for part in imported.split(".") if part]
    if level:
        package_parts = caller_file.replace("\\", "/").split("/")[:-1]
        ascend = max(level - 1, 0)
        if ascend > len(package_parts):
            return None
        base = package_parts[:len(package_parts) - ascend] if ascend else package_parts
        module_parts = base + module_parts
    module_parts += imported_parts
    if not module_parts:
        return None

    module_path = "/".join(module_parts)
    suffixes = (
        "{}.py::{}".format(module_path, target),
        "{}/__init__.py::{}".format(module_path, target),
    )
    pool = anchors if index is None else index.by_symbol.get(target, ())
    matches = [
        anchor_id
        for anchor_id in pool
        if any(anchor_id.replace("\\", "/").endswith(suffix) for suffix in suffixes)
    ]
    return matches[0] if len(matches) == 1 else None

def _resolve_registered_call(key: str, receiver: str, anchors: dict,
                             registry_name: str = "") -> Optional[str]:
    """Resolve ``registry[\"key\"](...)`` against decorated definitions."""
    exact = []
    fallback = []
    accepted_names = {name for name in (receiver, registry_name) if name}
    for anchor in anchors.values():
        entries = [item for item in _registration_entries(anchor) if item["key"] == key]
        if not entries:
            continue
        fallback.append(anchor.id)
        if any(item["name"] in accepted_names for item in entries):
            exact.append(anchor.id)
    if len(exact) == 1:
        return exact[0]
    return fallback[0] if len(fallback) == 1 else None

def _resolve_js_module_call(target: str, raw_callee: dict, anchors: dict,
                            caller_file: str | None, root=None,
                            index: "_ResolveIndex | None" = None) -> Optional[str]:
    """Resolve a require/import alias to the anchor it names.

    A relative specifier was always handled. A bare one — `pkg/deep/path`, which
    is what a package's own parts use to reach each other — was answered with
    "packages remain external", so a project organised into modules produced no
    cross-file edges at all and said nothing about it. Now the specifier goes to
    the resolver, which answers only from what the project itself declared:
    package.json exports, tsconfig paths, a workspace sibling's name.
    """
    ref = raw_callee.get("module_ref")
    if not isinstance(ref, dict) or not caller_file:
        return None
    module = str(ref.get("module") or "")
    if not module:
        return None
    imported = str(ref.get("imported") or "")
    symbol = target if imported in {"", "*", "default"} else imported
    files = []
    if root is not None:
        try:
            from scanner.language.typescript.js_resolver import resolver_for
            files = resolver_for(str(root)).candidates(module, caller_file.replace("\\", "/"))
        except Exception:
            files = []
    if not files:
        if not module.startswith("."):
            return None
        base = posixpath.dirname(caller_file.replace("\\", "/"))
        raw_path = posixpath.normpath(posixpath.join(base, module))
        suffix = posixpath.splitext(raw_path)[1]
        files = [raw_path] if suffix else [
            raw_path + ext for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
        ]
        if not suffix:
            files += [posixpath.join(raw_path, "index" + ext)
                      for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")]
    matches = []
    for file_name in files:
        exact = "{}::{}".format(file_name, symbol)
        if exact in anchors:
            matches.append(exact)
        if index is None:
            matches.extend(
                anchor.id for anchor in anchors.values()
                if anchor.file.replace("\\", "/") == file_name
                and str(anchor.symbol or "").rsplit(".", 1)[-1] == symbol
                and anchor.id != exact
            )
        else:
            matches.extend(
                anchor_id for anchor_id in index.by_file_tail.get((file_name, symbol), ())
                if anchor_id != exact
            )
    matches = list(dict.fromkeys(matches))
    return matches[0] if len(matches) == 1 else None

def _resolve_js_factory_member(target: str, raw_callee: dict, anchors: dict,
                               caller_file: str | None,
                               caller_anchor=None) -> Optional[str]:
    """Resolve `value.member()` when value came from `createThing()`."""
    factory = str(raw_callee.get("factory_ref") or "")
    if not factory or not caller_file:
        return None
    file_name = caller_file.replace("\\", "/")
    prefixes = []
    symbol = str(getattr(caller_anchor, "symbol", "") or "")
    owner = symbol.rsplit(".", 1)[0] if "." in symbol else ""
    while owner:
        prefixes.append(owner + "." + factory)
        owner = owner.rsplit(".", 1)[0] if "." in owner else ""
    prefixes.append(factory)
    for prefix in prefixes:
        candidate = "{}::{}.{}".format(file_name, prefix, target)
        if candidate in anchors:
            return candidate
    return None

def _resolve_call_id(raw_callee, anchors: dict, unique_symbol_ids: dict,
                     unique_leaf_ids: dict | None = None,
                     caller_file: str | None = None,
                     caller_anchor=None, root=None,
                     index: "_ResolveIndex | None" = None) -> str | None:
    target = _call_target(raw_callee)
    if not target:
        return None
    target = str(target).replace("\\", "/")
    # super::method_name → MRO-aware 解析
    if target.startswith("super::") and caller_anchor is not None:
        return _resolve_super_call(target[len("super::"):], caller_anchor, anchors)
    if target in BUILTIN_NOISE:
        return None
    # Persisted call sites already contain canonical anchor IDs.  Accept them
    # before re-evaluating lexical call kind so incremental refresh is
    # idempotent and does not erase previously resolved calls. This has to
    # run before the registry branch below: on a second pass over a
    # previously-resolved "registry" call site, `target` is no longer the
    # raw registry key (e.g. "tables.initialize") but the already-resolved
    # anchor id (e.g. "code/manager/runtime.py::initialize_tables") baked
    # into call_sites[i]["target"] by the first pass. Feeding that id back
    # into _resolve_registered_call as if it were still a bare registry key
    # never matches any @decorator("...") registration, so the call site
    # silently drops out of the graph — this is what made `cdd update` erase
    # registry-resolved edges (e.g. main.py's `manager["tables.initialize"]`)
    # for files that were not part of the incremental update's changed set.
    if "::" in target:
        return target if target in anchors else None
    if isinstance(raw_callee, dict) and raw_callee.get("call_kind") == "registry":
        return _resolve_registered_call(
            target,
            str(raw_callee.get("receiver") or ""),
            anchors,
            str(raw_callee.get("registry_name") or ""),
        )
    # Per language, because the languages do not resolve alike. Python says
    # where a name comes from in the import statement itself, so following the
    # import is enough. JavaScript says it in a specifier that has to be run
    # through the project's own manifests first. Sharing one chain meant every
    # new language's rules were appended to the same function and applied to
    # everyone, which held only as long as no two languages disagreed.
    language = str(getattr(caller_anchor, "language", "") or "")
    if isinstance(raw_callee, dict) and language in _JS_LANGUAGES:
        module_target = _resolve_js_module_call(
            target, raw_callee, anchors, caller_file, root, index,
        )
        if module_target:
            return module_target
        factory_target = _resolve_js_factory_member(
            target, raw_callee, anchors, caller_file, caller_anchor,
        )
        if factory_target:
            return factory_target
    # ``receiver.method(...)`` is only a lexical attribute call.  A short
    # method name is not enough evidence to bind it to the one same-named
    # function that happens to exist elsewhere in the project.  This mirrors
    # the v2 Program Model's possible/unresolved distinction.
    if isinstance(raw_callee, dict) and raw_callee.get("call_kind") == "attribute":
        receiver = str(raw_callee.get("receiver") or "")
        if receiver in {"self", "cls"} and caller_file and caller_anchor is not None:
            symbol = str(getattr(caller_anchor, "symbol", "") or "")
            if "." in symbol:
                owner = symbol.rsplit(".", 1)[0]
                class_id = "{}::{}".format(caller_file.replace("\\", "/"), owner)
                class_anchor = anchors.get(class_id)
                effective = getattr(class_anchor, "effective_methods", {}) if class_anchor else {}
                resolved = effective.get(target) if isinstance(effective, dict) else None
                if resolved in anchors:
                    return resolved
                candidate = "{}::{}.{}".format(
                    caller_file.replace("\\", "/"), owner, target,
                )
                if candidate in anchors:
                    return candidate
        imported_target = _resolve_import_attribute(
            target, raw_callee, anchors, caller_file, index,
        )
        if imported_target:
            return imported_target
        return None
    if caller_file:
        if caller_anchor is not None:
            own_nested = "{}::{}.{}".format(
                caller_file.replace("\\", "/"),
                str(caller_anchor.symbol or ""), target,
            )
            if own_nested in anchors:
                return own_nested
        if caller_anchor is not None and "." in str(caller_anchor.symbol or ""):
            owner = str(caller_anchor.symbol).rsplit(".", 1)[0]
            # Walk lexical parents from the innermost nested callback/function
            # out to the file scope: apply.handler@343 -> apply -> file.
            while owner:
                owner_candidate = "{}::{}.{}".format(
                    caller_file.replace("\\", "/"), owner, target,
                )
                if owner_candidate in anchors:
                    return owner_candidate
                owner = owner.rsplit(".", 1)[0] if "." in owner else ""
        candidate = "{}::{}".format(caller_file.replace("\\", "/"), target)
        if candidate in anchors:
            return candidate
    return unique_symbol_ids.get(target) or (unique_leaf_ids or {}).get(target)

def _finalize_anchor_graph(anchors: dict, *, only_ids: "set[str] | None" = None,
                           root=None) -> None:
    """Re-resolve callees/call_sites for every anchor, or only a scoped subset.

    ``only_ids`` (used by the incremental update path) restricts the
    expensive resolve pass to: anchors from the just-rescanned files
    themselves, anchors elsewhere that call into an id that was added,
    changed, or removed by this update, and anchors carrying a call site
    that never resolved in an earlier pass (so it gets retried in case the
    target now exists). Everything else keeps whatever it already has —
    correct, since a full pass already resolved it and nothing that would
    change its answer has moved. A full rebuild passes ``None`` and always
    resolves everything, which stays correct by construction (see below).
    """
    unique_symbol_ids = _build_unique_symbol_ids(anchors)
    unique_leaf_ids, leaf_candidates = _build_leaf_symbol_ids(anchors)
    ambiguous_names: set[str] = set()
    registry_templates: dict[str, list[str]] = {}
    unique_class_ids = _build_unique_class_ids(anchors)
    # 查表在这里建一次就够：下面每个锚点的每个调用点都会用到它，
    # 原来每用一次就把整个 anchors 重扫一遍。
    index = _ResolveIndex(anchors)

    def resolve_ids(resolution_ref, anchor) -> list[str]:
        if isinstance(resolution_ref, dict) and resolution_ref.get("call_kind") == "registry_template":
            template = str(resolution_ref.get("registry_template") or "")
            # A template of nothing but wildcards matches every key there is.
            # `**` compiled to `^.+.+$`, so an ordinary `sd.update(...)` was
            # read as a call to the entire registry — and then the entire
            # registry was copied into that one call site. A pattern that
            # cannot exclude anything is not evidence; it is the absence of it.
            if template.replace("*", "").strip() == "":
                return []
            pattern = "^{}$".format(_re.escape(template).replace(r"\*", ".+"))
            receiver_names = {
                str(resolution_ref.get("receiver") or ""),
                str(resolution_ref.get("registry_name") or ""),
            } - {""}
            exact = []
            matched = 0
            counted = set()
            taken = set()
            for candidate in anchors.values():
                for entry in _registration_entries(candidate):
                    if not _re.match(pattern, entry["key"]):
                        continue
                    pair = (entry["key"], candidate.id)
                    if pair not in counted:
                        counted.add(pair)
                        matched += 1
                    # One registration yields two entries: one carrying the
                    # decorator that made it and one without. Deduplicating on
                    # (key, id) alone let the nameless entry win the slot, so
                    # the receiver check below never saw the name and every
                    # template resolved to nothing.
                    if entry["name"] in receiver_names and pair not in taken:
                        taken.add(pair)
                        exact.append(pair)
            # No receiver match means the target is unknown. Answering with
            # every key that fit the pattern says "all of them", which is a
            # different claim and a false one — and it is the claim that made
            # one anchor record grow past a hundred megabytes.
            if not exact:
                resolution_ref["registry_matched"] = matched
                return []
            resolution_ref["_registry_matches"] = exact
            registry_templates[template] = sorted({aid for _, aid in exact})
            return [anchor_id for _, anchor_id in exact]
        direct = _resolve_call_id(
            resolution_ref,
            anchors,
            unique_symbol_ids,
            unique_leaf_ids,
            caller_file=anchor.file,
            caller_anchor=anchor,
            root=root,
            index=index,
        )
        if direct:
            return [direct]
        if not isinstance(resolution_ref, dict) or resolution_ref.get("call_kind") != "attribute":
            return []
        method_name = str(resolution_ref.get("target") or "")
        resolved = []
        for class_name in resolution_ref.get("receiver_types", []) or []:
            class_id = unique_class_ids.get(str(class_name))
            class_anchor = anchors.get(class_id) if class_id else None
            method_id = (
                getattr(class_anchor, "effective_methods", {}).get(method_name)
                if class_anchor else None
            )
            if method_id in anchors and method_id not in resolved:
                resolved.append(method_id)
        return resolved

    scope = anchors.values() if only_ids is None else (
        anchors[aid] for aid in only_ids if aid in anchors
    )
    for anchor in scope:
        normalized_callees = []
        normalized_sites = []
        sites = list(getattr(anchor, "call_sites", []) or [])
        # call_sites carry occurrence-level evidence and may legitimately be
        # longer than the de-duplicated `callees` summary. Pairing the two by
        # list index shifted every target after the first repeated call.
        refs = sites if sites else list(anchor.callees)
        for idx, raw_callee in enumerate(refs):
            if isinstance(raw_callee, dict):
                site = dict(raw_callee)
                resolution_ref = site
            else:
                site = {}
                resolution_ref = raw_callee
            target_ids = resolve_ids(resolution_ref, anchor)
            if not target_ids:
                # Keep the call rather than dropping it: its target is still
                # unresolved (e.g. a registry key with no matching decorator
                # yet), not gone. call_sites and callees stay index-aligned
                # (a placeholder goes in both) so a later pass over this same
                # anchor can retry using the original site data — and
                # because an unresolved target never contains "::", the fast
                # accept-path above never mistakes it for already resolved.
                kept_site = dict(site)
                kept_site.setdefault("seq", idx)
                kept_site.setdefault("line", 0)
                kept_site.setdefault("conds", ["nocond"])
                raw_target = str(kept_site.get("raw_target") or kept_site.get("target") or raw_callee)
                # A receiver call such as ``ctx.get()`` is not evidence that
                # the only project function named ``get`` is its target.  In
                # particular this used to connect production code to test
                # doubles. Candidate hints are useful only for unresolved
                # bare-name calls.
                is_attribute = kept_site.get("call_kind") == "attribute"
                leaf_name = raw_target.replace("::", ".").rsplit(".", 1)[-1]
                candidates = [] if is_attribute else leaf_candidates.get(leaf_name, [])
                kept_site["resolution"] = "possible" if len(candidates) > 1 else "unresolved"
                if candidates:
                    # The candidate set belongs to the NAME, not to the call
                    # site. Copying it into every site multiplied one list by
                    # every place the name is called: with a few thousand
                    # same-named symbols (a venv full of torch and numpy will
                    # do it) and a hundred call sites, one anchor record grew
                    # past a hundred megabytes. The set is written once, beside
                    # the anchors, and a site points at it.
                    kept_site["candidates"] = leaf_name
                    kept_site["candidate_count"] = len(candidates)
                    ambiguous_names.add(leaf_name)
                normalized_sites.append(kept_site)
                kept_target = kept_site.get("target") or raw_callee
                if kept_target not in normalized_callees:
                    normalized_callees.append(kept_target)
                continue
            for target_id in target_ids:
                resolved_site = dict(site)
                resolved_site["target"] = target_id
                resolved_site.setdefault("raw_target", _call_target(resolution_ref))
                resolved_site["resolution"] = "exact"
                resolved_site.setdefault("evidence", "canonical-id" if "::" in str(_call_target(resolution_ref)) else "unique-symbol")
                registry_matches = (
                    resolution_ref.get("_registry_matches", [])
                    if isinstance(resolution_ref, dict) else []
                )
                for key, candidate_id in registry_matches:
                    if candidate_id == target_id:
                        resolved_site["registry_key"] = key
                        break
                # The pair list is how this site found its key; it is not part
                # of the answer. Left in, it was copied into every site of every
                # caller of a registry — one record reached 534.8KB from 87
                # copies of the same 7,392-byte list, and one index reached
                # 68.6GB. The key above is what a reader needs.
                resolved_site.pop("_registry_matches", None)
                resolved_site.setdefault("seq", idx)
                resolved_site.setdefault("line", 0)
                resolved_site.setdefault("conds", ["nocond"])
                if target_id not in normalized_callees:
                    normalized_callees.append(target_id)
                normalized_sites.append(resolved_site)
        if anchor.symbol_type == "class":
            constructor_id = getattr(anchor, "effective_methods", {}).get("__init__")
            if constructor_id in anchors and constructor_id not in normalized_callees:
                normalized_callees.append(constructor_id)
                normalized_sites.append({
                    "target": constructor_id,
                    "seq": len(normalized_sites),
                    "line": anchor.line_start,
                    "conds": ["nocond"],
                    "call_kind": "constructor",
                })
        anchor.callees = normalized_callees
        anchor.call_sites = normalized_sites

    # Handed to the writer so the shared table lands next to the anchors.
    _finalize_anchor_graph.last_ambiguous = {
        "names": {name: list(leaf_candidates.get(name, [])) for name in sorted(ambiguous_names)},
        "registry": {k: registry_templates[k] for k in sorted(registry_templates)},
    }

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

def _normalize_file_ref(root: Path, file_path) -> str:
    path = Path(str(file_path).replace("\\", "/"))
    if path.is_absolute():
        try:
            return str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")
    normalized = str(path).replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized

def _module_anchor_for_file(root: Path, file_path: Path) -> Optional[Anchor]:
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception:
        return None
    call_sites = _extract_module_call_sites(tree)
    if not call_sites:
        return None
    rel = _normalize_file_ref(root, file_path)
    anchor_id = "{}::<module>".format(rel)
    return Anchor(
        id=anchor_id,
        symbol="<module>",
        file=rel,
        line_start=1,
        line_end=max(1, len(source.splitlines())),
        hash="",
        language="python",
        symbol_type="module",
        callees=[site["target"] for site in call_sites],
        call_sites=call_sites,
        block_metadata={"module_entry": True},
    )

def _normalize_registration_decorators(decorators: list, symbol: str) -> list[dict]:
    """Give bare ``@register`` decorators their class/function symbol key."""
    normalized = []
    leaf = str(symbol or "").rsplit(".", 1)[-1]
    for item in decorators:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        if entry.get("name") == "register" and not entry.get("key") and leaf:
            entry["key"] = leaf
            entry["implicit_key"] = True
        if entry.get("name") or entry.get("key"):
            normalized.append(entry)
    return normalized
