"""
inspector.py — 轻量代码导航接口

    list_file_anchors(file_path, root)   → 文件内所有函数/类列表
    find_anchor(keyword, root)           → 按函数名模糊搜索
    get_anchor_source(symbol, root)      → anchor 源码（上下各 +3 行）
    get_anchor_relations(symbol, root)   → 调用者 + 被调用者（一层），带跳转历史
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

from api.inspector.find_anchor import _current_python_range

def get_anchor_source(symbol: str, root: str = ".", context: int = 3) -> Optional[dict]:
    """
    返回 anchor 的源码，上下各扩展 context 行。

    Returns:
        {symbol, file, line_start, line_end, actual_start, actual_end, source}
        或 None（找不到 anchor）
    """
    from analyzer.anchors import get_anchor
    anchor = get_anchor(symbol, root)
    if not anchor:
        return None

    file_path = anchor.file
    if not Path(file_path).is_absolute():
        file_path = str(Path(root) / file_path)

    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    line_start = anchor.line_start
    line_end = anchor.line_end
    if Path(file_path).suffix.lower() == ".py":
        line_start, line_end = _current_python_range(
            source,
            anchor.symbol,
            line_start,
            line_end,
        )

    lines = source.splitlines()
    lo = max(0, line_start - 1 - context)
    hi = min(len(lines), line_end + context)
    numbered = "\n".join(f"{lo + 1 + i:4d}  {line}" for i, line in enumerate(lines[lo:hi]))

    return {
        "symbol": anchor.symbol,
        "file": anchor.file,
        "line_start": line_start,
        "line_end": line_end,
        "actual_start": lo + 1,
        "actual_end": hi,
        "source": numbered,
    }

def get_downward_chain(
    symbol: str,
    root: str = ".",
    max_depth: int = 6,
    active_registry_keys: Optional[set[str]] = None,
    yaml_profile: Optional[dict] = None,
    include_candidates: bool = False,
) -> List[dict]:
    """
    从 symbol 出发，沿 callees 方向往下追，返回整条下行调用树。
    每层取所有 callees，虚拟块自动透视到叶子真实函数。

    同一节点可以出现在不同父节点之下；只在当前路径内防环。这样菱形
    调用图不会因为全局去重而丢掉 ``A -> B`` 这类真实父子关系。

    Args:
        include_candidates: 是否把**未解析的属性调用**（``receiver.method()``）
            作为候选节点一并返回。这些调用没有 canonical id，按设计不进
            调用图（见 analyzer/anchors/resolve.py 的说明：接收者类型在
            Python AST 上通常无法证明），所以它们默认不出现。打开后，只在
            该叶子名在整个索引里**唯一**时才给出，并标
            ``resolution="candidate"``，与真实边区分。默认 False，行为不变。

    Returns:
        [
          {"symbol": "main",         "file": "main.py", "line": 10, "depth": 0},
          {"symbol": "process_data", "file": "proc.py", "line": 30, "depth": 1},
          ...
        ]
        depth=0 是入口本身，depth 越大越往下。
        候选节点额外带 ``resolution="candidate"`` / ``candidate_reason`` / ``call_line``。
    """
    from analyzer.anchors import get_anchor, load_anchors
    from api.relations import flatten_virtual

    try:
        all_anchors = load_anchors(root)
    except Exception:
        all_anchors = {}

    # 叶子名 → 唯一 anchor。只用于未解析属性调用的候选提示：名字在索引里
    # 唯一才有提示价值，同名多解一律不给（那种"提示"只会把人带偏）。
    unique_by_leaf: dict[str, object] = {}
    if include_candidates:
        grouped: dict[str, list] = {}
        for candidate_anchor in all_anchors.values():
            if candidate_anchor.is_virtual:
                continue
            grouped.setdefault(candidate_anchor.symbol.rsplit(".", 1)[-1], []).append(candidate_anchor)
        unique_by_leaf = {name: found[0] for name, found in grouped.items() if len(found) == 1}

    registered_by_key: dict[str, list] = {}
    for registered_anchor in all_anchors.values():
        registration_keys = {str(getattr(registered_anchor, "registered_as", "") or "")}
        registration_keys.update(
            str(item.get("key") or "")
            for item in getattr(registered_anchor, "block_metadata", {}).get("decorators", [])
            if isinstance(item, dict)
        )
        for registration_key in registration_keys - {""}:
            registered_by_key.setdefault(registration_key, []).append(registered_anchor)

    yaml_dependencies: dict[str, set[str]] = {}
    yaml_data = dict((yaml_profile or {}).get("data") or {})
    if active_registry_keys is not None:
        def collect_active_values(value) -> set[str]:
            found = set()
            if isinstance(value, dict):
                for child in value.values():
                    found.update(collect_active_values(child))
            elif isinstance(value, list):
                for child in value:
                    found.update(collect_active_values(child))
            elif isinstance(value, str) and value in active_registry_keys:
                found.add(value)
            return found

        for registration_key in active_registry_keys:
            section = yaml_data.get(registration_key)
            if section is not None:
                yaml_dependencies[registration_key] = collect_active_values(section) - {registration_key}

    def factory_keys_for_site(site: dict) -> set[str]:
        if active_registry_keys is None:
            return set()
        selected = set()
        literal = str(site.get("factory_key") or "")
        if literal in active_registry_keys:
            selected.add(literal)
        template = str(site.get("factory_template") or "")
        if template:
            import re
            pattern = "^{}$".format(re.escape(template).replace(r"\*", ".+"))
            selected.update(key for key in active_registry_keys if re.match(pattern, key))
        flat = dict((yaml_profile or {}).get("flat") or {})
        for path in site.get("factory_config_paths", []) or []:
            value = flat.get(path)
            if value is None:
                matches = [candidate for field, candidate in flat.items() if field.endswith("." + path)]
                value = matches[0] if len(matches) == 1 else None
            if isinstance(value, str) and value in active_registry_keys:
                selected.add(value)
        return selected

    def callees_of(node: dict) -> List[dict]:
        anchor_id = node["id"]
        anchor = all_anchors.get(anchor_id) or all_anchors.get(anchor_id.replace("\\", "/"))
        if anchor is None:
            anchor = get_anchor(anchor_id, root)
        if not anchor:
            return []
        sites = list(getattr(anchor, "call_sites", []) or [])
        active_by_template = {}
        if active_registry_keys is not None:
            for site in sites:
                if not isinstance(site, dict):
                    continue
                template = site.get("registry_template")
                key = site.get("registry_key")
                if template and key in active_registry_keys:
                    active_by_template.setdefault(template, set()).add(key)
        seen: set = set()
        result = []
        factory_selected_keys = set()
        for site in sites:
            if isinstance(site, dict) and str(site.get("target") or "").endswith("::create"):
                factory_selected_keys.update(factory_keys_for_site(site))
        # ``call_sites`` are occurrence-level while ``callees`` are a unique
        # summary.  Index-zipping them shifts targets after any repeated call
        # and can turn an unresolved ``ctx.get`` into an unrelated project
        # function.  Traverse the evidence records themselves when present.
        refs = sites if sites else list(anchor.callees)
        for index, raw in enumerate(refs):
            site = raw if isinstance(raw, dict) else {}
            template = site.get("registry_template")
            registry_key = site.get("registry_key")
            selected = active_by_template.get(template, set()) if template else set()
            if selected and registry_key not in selected:
                continue
            route_metadata = {}
            if (
                active_registry_keys is not None
                and template
                and registry_key in active_registry_keys
            ):
                route_metadata = {
                    "yaml_selected": True,
                    "registry_key": registry_key,
                    "registry_template": template,
                }
            target = raw.get("target", raw) if isinstance(raw, dict) else raw
            target = str(target or "")
            if not target or target in seen:
                continue
            # A finalized occurrence without a canonical id is explicitly
            # unresolved. Never feed that bare name into fuzzy anchor lookup.
            if sites and "::" not in target and "#" not in target:
                continue
            seen.add(target)
            if "#" in target:
                for leaf in flatten_virtual(target, all_anchors):
                    leaf_id = str(leaf.get("func_id") or "")
                    if not leaf_id or leaf_id in seen:
                        continue
                    seen.add(leaf_id)
                    la = all_anchors.get(leaf_id) or all_anchors.get(leaf_id.replace("\\", "/"))
                    if la and not la.is_virtual:
                        result.append({
                            "id": la.id,
                            "symbol": la.symbol,
                            "file": la.file,
                            "line": la.line_start,
                            **route_metadata,
                        })
            else:
                norm = target.replace("\\", "/")
                ca = all_anchors.get(norm) or all_anchors.get(target)
                if ca is None and ("::" in target or "#" in target):
                    ca = get_anchor(target, root)
                if ca and not ca.is_virtual:
                    child = {
                        "id": ca.id,
                        "symbol": ca.symbol,
                        "file": ca.file,
                        "line": ca.line_start,
                        **route_metadata,
                    }
                    if ca.symbol.rsplit(".", 1)[-1] == "create" and factory_selected_keys:
                        child["factory_selected_keys"] = sorted(factory_selected_keys)
                    result.append(child)
        selected_for_factory = set(node.get("factory_selected_keys") or ())
        if selected_for_factory and anchor.symbol.rsplit(".", 1)[-1] == "create":
            for candidate in all_anchors.values():
                keys = {str(getattr(candidate, "registered_as", "") or "")}
                keys.update(
                    str(item.get("key") or "")
                    for item in getattr(candidate, "block_metadata", {}).get("decorators", [])
                    if isinstance(item, dict)
                )
                selected_keys = sorted((keys - {""}) & selected_for_factory)
                if not selected_keys or candidate.id in seen or candidate.is_virtual:
                    continue
                seen.add(candidate.id)
                result.append({
                    "id": candidate.id,
                    "symbol": candidate.symbol,
                    "file": candidate.file,
                    "line": candidate.line_start,
                    "yaml_selected": True,
                    "registry_key": selected_keys[0],
                    "registry_template": "@register",
                })
        anchor_keys = {
            str(getattr(anchor, "registered_as", "") or ""),
            *(
                str(item.get("key") or "")
                for item in getattr(anchor, "block_metadata", {}).get("decorators", [])
                if isinstance(item, dict)
            ),
        } - {""}
        dependency_keys = set()
        for anchor_key in anchor_keys:
            dependency_keys.update(yaml_dependencies.get(anchor_key, set()))
        for dependency_key in sorted(dependency_keys):
            matches = registered_by_key.get(dependency_key, [])
            if len(matches) != 1:
                continue
            candidate = matches[0]
            if candidate.id in seen or candidate.is_virtual:
                continue
            seen.add(candidate.id)
            result.append({
                "id": candidate.id,
                "symbol": candidate.symbol,
                "file": candidate.file,
                "line": candidate.line_start,
                "yaml_selected": True,
                "registry_key": dependency_key,
                "registry_template": "yaml_dependency",
            })
        if include_candidates:
            for site in sites:
                if not isinstance(site, dict) or site.get("call_kind") != "attribute":
                    continue
                if site.get("resolution") == "exact":
                    continue
                leaf = str(site.get("target") or "").rsplit(".", 1)[-1].strip()
                hinted = unique_by_leaf.get(leaf)
                if hinted is None or hinted.id in seen or hinted.id == anchor.id:
                    continue
                seen.add(hinted.id)
                result.append({
                    "id": hinted.id,
                    "symbol": hinted.symbol,
                    "file": hinted.file,
                    "line": hinted.line_start,
                    "resolution": "candidate",
                    "candidate_reason": "unresolved-attribute-call",
                    "call_line": site.get("line"),
                })
        return result

    entry_anchor = get_anchor(symbol, root)
    if entry_anchor:
        entry = {
            "id": entry_anchor.id,
            "symbol": entry_anchor.symbol,
            "file": entry_anchor.file,
            "line": entry_anchor.line_start,
        }
    else:
        entry = {"id": symbol, "symbol": symbol, "file": None, "line": None}

    chain: List[dict] = []

    def visit(node: dict, depth: int, path: tuple, parent_id: Optional[str]) -> None:
        node_id = node["id"]
        chain.append({**node, "depth": depth, "parent_id": parent_id})
        if depth >= max_depth:
            return
        # 候选节点是"值得看一眼"的提示，不是被证明的边：不沿着它继续展开。
        # 否则一个类名候选（如 Flask）会把整个框架子树拖进链里。
        if node.get("resolution") == "candidate":
            return
        next_path = path + (node_id,)
        for child in callees_of(node):
            if child["id"] in next_path:
                continue
            visit(child, depth + 1, next_path, node_id)

    visit(entry, 0, (), None)

    return chain
