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

from base.shared.types import Anchor
from base.shared.codedendrite_ignore import CodeDendriteIgnore
from base.shared.formula_skip import should_skip as _should_skip_formula

_EMBED_STYLE_RE = _re.compile(r'<style[^>]*>(.*?)</style>', _re.DOTALL | _re.IGNORECASE)
_EMBED_SCRIPT_RE = _re.compile(r'<script[^>]*>(.*?)</script>', _re.DOTALL | _re.IGNORECASE)
_EMBED_DOM_ID_RE = _re.compile(r'\bid=["\']([A-Za-z][\w-]*)["\']')
_EMBED_CSS_SEL_RE = _re.compile(r'(?:^|[\s,>+~])([.#][A-Za-z][\w-]*)', _re.MULTILINE)
_EMBED_JS_FUNC_RE = _re.compile(r'function\s+([A-Za-z$_][\w$]*)\s*\(')
_EMBED_JS_QUERY_RE = _re.compile(r'(?:querySelectorAll?|getElementById)\s*\(\s*["\']([^"\']+)["\']')

# ── 调试日志（环境变量 CD_ANCHOR_LOG 开关；默认不打，不污染生产 run）──
import time as _time
_ANCHOR_DBG = bool(os.environ.get("CD_ANCHOR_LOG"))

from index.api.anchors.subscript_string import BUILTIN_NOISE
from index.api.anchors.build_effective_methods_table import _build_unique_class_ids, _build_unique_symbol_ids, _call_target, _extract_module_call_sites, _registration_entries, _resolve_super_call

def _resolve_import_attribute(target: str, raw_callee: dict, anchors: dict,
                              caller_file: str | None) -> Optional[str]:
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
    matches = [
        anchor_id
        for anchor_id in anchors
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
            target, raw_callee, anchors, caller_file,
        )
        if imported_target:
            return imported_target
        return None
    if caller_file:
        candidate = "{}::{}".format(caller_file.replace("\\", "/"), target)
        if candidate in anchors:
            return candidate
    return unique_symbol_ids.get(target)

def _finalize_anchor_graph(anchors: dict, *, only_ids: "set[str] | None" = None) -> None:
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
    unique_class_ids = _build_unique_class_ids(anchors)

    def resolve_ids(resolution_ref, anchor) -> list[str]:
        if isinstance(resolution_ref, dict) and resolution_ref.get("call_kind") == "registry_template":
            template = str(resolution_ref.get("registry_template") or "")
            pattern = "^{}$".format(_re.escape(template).replace(r"\*", ".+"))
            receiver_names = {
                str(resolution_ref.get("receiver") or ""),
                str(resolution_ref.get("registry_name") or ""),
            } - {""}
            exact = []
            fallback = []
            for candidate in anchors.values():
                for entry in _registration_entries(candidate):
                    if not _re.match(pattern, entry["key"]):
                        continue
                    pair = (entry["key"], candidate.id)
                    if pair not in fallback:
                        fallback.append(pair)
                    if entry["name"] in receiver_names and pair not in exact:
                        exact.append(pair)
            selected = exact or fallback
            resolution_ref["_registry_matches"] = selected
            return [anchor_id for _, anchor_id in selected]
        direct = _resolve_call_id(
            resolution_ref,
            anchors,
            unique_symbol_ids,
            caller_file=anchor.file,
            caller_anchor=anchor,
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
        for idx, raw_callee in enumerate(anchor.callees):
            if idx < len(sites) and isinstance(sites[idx], dict):
                site = dict(sites[idx])
                resolution_ref = site
            elif isinstance(raw_callee, dict):
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
                normalized_sites.append(kept_site)
                normalized_callees.append(kept_site.get("target") or raw_callee)
                continue
            for target_id in target_ids:
                resolved_site = dict(site)
                resolved_site["target"] = target_id
                registry_matches = (
                    resolution_ref.get("_registry_matches", [])
                    if isinstance(resolution_ref, dict) else []
                )
                for key, candidate_id in registry_matches:
                    if candidate_id == target_id:
                        resolved_site["registry_key"] = key
                        break
                resolved_site.setdefault("seq", idx)
                resolved_site.setdefault("line", 0)
                resolved_site.setdefault("conds", ["nocond"])
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
