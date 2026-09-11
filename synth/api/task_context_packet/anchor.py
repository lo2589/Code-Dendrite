"""Task Context Packet — 给小模型/执行 agent 生成当前任务的窄上下文包。

设计文档: todo/codedentrite/CD_四类结构图认知整理.md §4

四级上下文:
  Level 0: Project Brief (30-80 tokens)  — 项目一句话 + 顶层区域
  Level 1: Area Map (100-300 tokens)     — 当前任务所在区域
  Level 2: Task Slice (300-800 tokens)   — 0-3 个可信候选 + why + next_command
  Level 3: Source Snippet (按需)         — 默认不给

验收标准:
  1. Level 0 不超过 3 句
  2. Level 1 只描述当前区域
  3. Level 2 只给有证据支撑的候选，不为满足数量下限而补齐
  4. 每个候选都有 why 和 next_command
  5. 不默认给源码片段
  6. 小模型能只根据 packet 选择下一步
"""

import json
import os
import ast
import re
from pathlib import Path
from collections import defaultdict
from typing import Optional, List, Tuple, Any, Callable


# ── 常量 ─────────────────────────────────────────────────────────

DEFAULT_BUDGET = 1200   # 总 token 预算
L0_TOKEN_LIMIT = 80
L1_TOKEN_LIMIT = 300
L2_TOKEN_LIMIT = 800
MAX_CANDIDATES = 7
MIN_CANDIDATES = 0
RECOMMENDATION_LIMIT = 3
NOISE_SYMBOLS = {
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set",
    "Path", "open", "json.dumps", "json.loads", "time.sleep",
}
GENERIC_TASK_QUERIES = {
    "all", "binary", "code", "error", "extract", "file", "interactive",
    "line", "message", "module", "previous", "python", "range", "return",
    "self", "text", "the", "this", "value",
}
FILE_MATCH_TYPES = {"file_path", "file_suffix", "file_stem", "file_segment"}


# ── 工具函数 ─────────────────────────────────────────────────────

from synth.api.task_context_packet.plugin import _control_path_for_call, _estimate_obj_tokens, _estimate_tokens, _find_anchor_module, _is_noise_symbol, _is_test_file, _relation_resolution_counts, assemble_task_prompt, build_error_packet

def _anchor_attr(anchor, key: str, default=""):
    """从 Anchor 对象或 dict 中读取属性。"""
    if isinstance(anchor, dict):
        return anchor.get(key, default)
    return getattr(anchor, key, default)

def _anchor_id(anchor) -> str:
    aid = _anchor_attr(anchor, "id", "")
    if aid:
        return aid.replace("\\", "/")
    fpath = _anchor_attr(anchor, "file", "").replace("\\", "/")
    symbol = _anchor_attr(anchor, "symbol", "")
    return "{}::{}".format(fpath, symbol) if fpath and symbol else ""

def _match_sort_key(item) -> tuple:
    aid, anchor, _ = item
    file_name = _anchor_attr(anchor, "file", "").replace("\\", "/")
    return (
        1 if _is_test_file(file_name) else 0,
        file_name,
        int(_anchor_attr(anchor, "line_start", 0) or 0),
        aid,
    )

def _bounded_matches(items: list) -> list:
    """截断时保留跨文件证据，避免前 7 条恰好同文件造成虚假唯一性。"""
    if len(items) <= MAX_CANDIDATES:
        return items
    selected = list(items[:MAX_CANDIDATES])
    selected_files = {
        _anchor_attr(item[1], "file", "").replace("\\", "/")
        for item in selected
    }
    for item in items[MAX_CANDIDATES:]:
        file_name = _anchor_attr(item[1], "file", "").replace("\\", "/")
        if file_name not in selected_files:
            selected[-1] = item
            break
    return selected

def _read_anchor_source(root: str, anchor, max_lines: int = 80) -> str:
    fpath = _anchor_attr(anchor, "file", "")
    if _anchor_attr(anchor, "privacy_masked", False):
        return ""
    ignore_path = Path(root) / ".codedendrite_ignore"
    if ignore_path.exists():
        from base.shared.codedendrite_ignore import CodeDendriteIgnore
        if CodeDendriteIgnore(root).should_mask_content(Path(root) / fpath):
            return ""
    start = int(_anchor_attr(anchor, "line_start", 1) or 1)
    end = int(_anchor_attr(anchor, "line_end", start) or start)
    path = Path(root) / fpath
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lo = max(0, start - 1)
    hi = min(len(lines), max(start, min(end, start + max_lines - 1)))
    return "\n".join(lines[lo:hi])

def resolve_task_anchor(
    query: str,
    anchors: dict,
) -> List[Tuple[str, Any, str]]:
    """将用户输入解析为匹配的锚点列表。

    匹配策略（按优先级）:
      1. 精确 ID: "file.py::symbol"
      2. 符号名:  "create_anchor"
      3. 文件路径（也接受 traceback 中的绝对路径）
      4. 文件名/符号关键词: "anchor"

    Returns:
        [(anchor_id, anchor_obj, match_type), ...]
        最多返回 MAX_CANDIDATES 个，按相关度排序
    """
    if not query or not anchors:
        return []

    results = []
    query_norm = query.replace("\\", "/").strip()

    # 策略 1: 精确 ID
    if query_norm in anchors:
        return [(query_norm, anchors[query_norm], "exact_id")]

    query_lower = query_norm.casefold()

    # 策略 2: 文件路径。真实 issue 常带 site-packages/.../project/file.py，
    # 因此允许以仓库相对路径结尾；仅 basename 命中多个文件时留给置信评估判歧义。
    if "/" in query_norm or query_lower.endswith(".py"):
        path_results = []
        for aid, anchor in anchors.items():
            fpath = _anchor_attr(anchor, "file", "").replace("\\", "/")
            folded = fpath.casefold()
            if query_lower == folded:
                path_results.append((aid, anchor, "file_path"))
            elif (
                query_lower.endswith("/" + folded)
                or folded.endswith("/" + query_lower.lstrip("/"))
                or query_lower == Path(fpath).name.casefold()
            ):
                path_results.append((aid, anchor, "file_suffix"))
        if path_results:
            path_results.sort(key=_match_sort_key)
            return _bounded_matches(path_results)

    # issue 模板词即使恰好等于某个符号名，也不足以单独触发导航。
    if query_lower in GENERIC_TASK_QUERIES:
        return []

    # 策略 3: 符号名匹配
    for aid, anchor in anchors.items():
        sym = _anchor_attr(anchor, "symbol", "")
        tail = sym.rsplit(".", 1)[-1]
        if sym.casefold() == query_lower or tail.casefold() == query_lower:
            results.append((aid, anchor, "symbol_name"))
    if results:
        results.sort(key=_match_sort_key)
        return _bounded_matches(results)

    # 策略 4: 关键词模糊匹配。短词和 issue 模板词不具备导航辨识度。
    if len(query_lower) < 4:
        return []
    scored = []
    for aid, anchor in anchors.items():
        sym = _anchor_attr(anchor, "symbol", "").casefold()
        fpath = _anchor_attr(anchor, "file", "").replace("\\", "/").casefold()
        stem = Path(fpath).stem
        segments = set(re.split(r"[/._-]+", fpath))
        score = 0
        match_type = "keyword"
        if query_lower == stem:
            score += 10
            match_type = "file_stem"
        elif query_lower in segments:
            score += 7
            match_type = "file_segment"
        if query_lower in sym:
            score += 3
        if query_lower in fpath:
            score += 1
        if query_lower in aid.lower():
            score += 2
        if score > 0:
            scored.append((score, aid, anchor, match_type))

    scored.sort(key=lambda x: (-x[0], _match_sort_key((x[1], x[2], x[3]))))
    ordered = [(aid, anch, match_type) for _, aid, anch, match_type in scored]
    return _bounded_matches(ordered)

def assess_task_matches(query: str, matches: List[Tuple[str, Any, str]]) -> dict:
    """判断匹配是否足以生成导航命令；歧义结果仍保留为证据。"""
    if not matches:
        return {
            "status": "unresolved", "confidence": "none",
            "safe_to_recommend": False, "reason": "没有锚点证据",
            "candidate_files": [],
        }

    match_types = {item[2] for item in matches}
    files = sorted({
        _anchor_attr(item[1], "file", "").replace("\\", "/")
        for item in matches if _anchor_attr(item[1], "file", "")
    })
    unique_file = len(files) == 1

    if match_types == {"exact_id"}:
        status, confidence, safe, reason = "resolved", "high", True, "完整 anchor ID"
    elif match_types == {"error_line"} and unique_file:
        status, confidence, safe, reason = "resolved", "high", True, "traceback 行号落在唯一锚点内"
    elif match_types == {"near_error_line"} and unique_file:
        status, confidence, safe, reason = "resolved", "medium", True, "traceback 文件中的最近锚点"
    elif match_types <= {"file_path", "file_suffix"} and unique_file:
        status, confidence, safe, reason = "resolved", "high", True, "唯一文件路径证据"
    elif match_types == {"symbol_name"} and len(matches) == 1:
        status, confidence, safe, reason = "resolved", "high", True, "唯一符号精确匹配"
    elif match_types == {"symbol_name"} and unique_file:
        status, confidence, safe, reason = "resolved", "medium", True, "同文件内的符号精确匹配"
    elif match_types <= {"file_stem", "file_segment", "keyword"} and unique_file:
        status, confidence, safe, reason = "resolved", "medium", True, "模糊命中集中在唯一文件"
    else:
        status, confidence, safe = "ambiguous", "low", False
        reason = "匹配跨越 {} 个文件，不能当作下一步建议".format(len(files))

    return {
        "status": status,
        "confidence": confidence,
        "safe_to_recommend": safe,
        "reason": reason,
        "match_types": sorted(match_types),
        "candidate_files": files[:MAX_CANDIDATES],
        "raw_match_count": len(matches),
        "query": query,
        "evidence_boundary": "候选表示静态定位证据，不表示缺陷已确认",
    }

def _build_edge_indexes(relations: dict):
    """构建保留 resolution/evidence 的出边、入边索引。

    v1 自己生成的 relations 没有 resolution 字段。这种投影证据必须明确
    标为 resolution_unavailable，不能因为端点恰好存在就伪装成 exact。
    """
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    edges = relations.get("edges", [])
    for e in edges:
        fid = e.get("from_id", "")
        tid = e.get("to_id", "")
        etype = e.get("edge_type", "")
        if fid and tid:
            resolution = e.get("resolution") or "resolution_unavailable"
            evidence = {
                "anchor_id": tid,
                "edge_type": etype,
                "resolution": resolution,
                "evidence": e.get("evidence"),
            }
            outgoing[fid].append(evidence)
            incoming[tid].append({**evidence, "anchor_id": fid})
    return outgoing, incoming

def build_level0(
    root: str,
    module_tree: Optional[dict],
    anchors: dict,
    policy=None,
) -> dict:
    """生成 L0 — 项目一句话 + 顶层区域。

    目标: 30-80 tokens，不超过 3 句。
    """
    # 从 module_tree_v2 提取
    if module_tree and module_tree.get("modules"):
        modules = module_tree["modules"]
        summary = module_tree.get("summary", {})
        total = summary.get("total_modules", len(modules))
        by_status = summary.get("by_status", {})

        # 提取顶层区域
        areas = set()
        for mod in modules:
            for f in mod.get("files", []):
                parts = f.replace("\\", "/").split("/")
                if len(parts) > 1:
                    areas.add(parts[0])

        project_name = Path(root).resolve().name
        status_parts = []
        for k, v in sorted(by_status.items(), key=lambda x: -x[1]):
            status_parts.append("{} {}".format(v, k))
        status_desc = ", ".join(status_parts)
        brief = "{}: {} 个功能模块 ({})".format(project_name, total, status_desc)

        return {
            "project": brief,
            "areas": sorted(areas),
        }

    # 无 module_tree，从锚点/目录推断
    areas = set()
    for aid, anchor in anchors.items():
        fpath = _anchor_attr(anchor, "file", "")
        parts = fpath.replace("\\", "/").split("/")
        if len(parts) > 1:
            areas.add(parts[0])

    project_name = Path(root).resolve().name
    brief = "{}: {} 个符号，{} 个区域".format(project_name, len(anchors), len(areas))

    return {
        "project": brief,
        "areas": sorted(areas),
    }

def _find_anchor_area(anchor_id: str, anchor) -> str:
    """确定锚点所在的区域（顶层目录）。"""
    fpath = _anchor_attr(anchor, "file", "")
    parts = fpath.replace("\\", "/").split("/")
    if len(parts) > 1:
        return parts[0]
    return ""

def build_level1(
    task_matches: List[Tuple[str, Any, str]],
    module_tree: Optional[dict],
    anchors: dict,
    relations: dict,
    policy=None,
) -> dict:
    """生成 L1 — 当前任务所在区域。

    目标: 100-300 tokens，只描述当前区域。
    """
    if not task_matches:
        return {
            "current_area": "unknown",
            "task_anchor": "",
            "area_modules": [],
            "responsibility": "无法定位任务锚点",
        }

    primary_id, primary_anchor, match_type = task_matches[0]
    area = _find_anchor_area(primary_id, primary_anchor)
    current_module = _find_anchor_module(primary_id, module_tree)

    # 找同区域的其他模块
    area_modules = []
    if module_tree:
        for mod in module_tree.get("modules", []):
            mod_files = mod.get("files", [])
            in_area = any(
                f.replace("\\", "/").startswith(area + "/")
                for f in mod_files
            ) if area else False
            if in_area:
                area_modules.append({
                    "name": mod["name"],
                    "status": mod["status"],
                    "what": mod.get("what", ""),
                })

    # 构建区域职责描述
    if current_module:
        responsibility = current_module.get("what", "")
        if not responsibility or responsibility == "unknown":
            responsibility = "{} 区域功能".format(area)
    else:
        responsibility = "{} 区域".format(area) if area else "未知区域"

    return {
        "current_area": area or "root",
        "task_anchor": primary_id,
        "match_type": match_type,
        "area_modules": area_modules[:10],
        "responsibility": responsibility,
    }

def _score_related_symbol(
    symbol_id: str,
    anchor,
    relation_to_task: str,
    edge_type: str,
    task_area: str,
) -> int:
    """给相关符号打分。"""
    score = 0
    sym_file = _anchor_attr(anchor, "file", "").replace("\\", "/")
    sym_type = _anchor_attr(anchor, "symbol_type", "")

    # 同区域加分
    if task_area and sym_file.startswith(task_area + "/"):
        score += 2
    # 调用关系加分
    if relation_to_task == "callee":
        score += 3
    elif relation_to_task == "caller":
        score += 2
    elif "dataflow" in relation_to_task:
        score += 1
    # 类型加分
    if sym_type == "class":
        score += 1
    # call 边比 dataflow 更直接
    if edge_type == "call":
        score += 1

    return score

def build_level2(
    task_matches: List[Tuple[str, Any, str]],
    area_info: dict,
    anchors: dict,
    relations: dict,
    module_tree: Optional[dict],
    policy=None,
    budget: int = L2_TOKEN_LIMIT,
) -> dict:
    """生成 L2 — 最多 3 个有证据支撑的候选 + why + next_command。

    目标: 300-800 tokens，每个候选都有 why 和 next_command。
    """
    if not task_matches:
        return {
            "entry": "", "candidates": [], "alternatives": [],
            "boundaries": [], "context_edges": [],
        }

    primary_id = task_matches[0][0]
    primary_anchor = task_matches[0][1]
    task_area = area_info.get("current_area", "")
    outgoing, incoming = _build_edge_indexes(relations)

    # ── 收集相关符号 ──
    related = []

    # v1 没有 v2 的 exact/possible/unresolved 标记，因此只在精确符号入口上
    # 使用投影关系；文件级和模糊入口不再用任意首符号扩散。
    primary_match_type = task_matches[0][2]
    if primary_match_type in {"exact_id", "symbol_name"}:
        # 从任务锚点出发的出边（任务调用了什么）
        for edge in outgoing.get(primary_id, []):
            to_id = edge["anchor_id"]
            etype = edge["edge_type"]
            if edge["resolution"] != "exact":
                continue
            if to_id in anchors:
                s = _score_related_symbol(
                    to_id, anchors[to_id], "callee", etype, task_area,
                )
                related.append((s, to_id, "被任务调用", etype))

        # 指向任务锚点的入边（谁调用了任务）
        for edge in incoming.get(primary_id, []):
            from_id = edge["anchor_id"]
            etype = edge["edge_type"]
            if edge["resolution"] != "exact":
                continue
            if from_id in anchors:
                s = _score_related_symbol(
                    from_id, anchors[from_id], "caller", etype, task_area,
                )
                related.append((s, from_id, "调用了任务", etype))

    # 多锚点仅保留少量同组证据；文件查询不应展开成一排任意符号。
    if primary_match_type not in FILE_MATCH_TYPES:
        for aid, anchor, mtype in task_matches[1:RECOMMENDATION_LIMIT]:
            related.append((100, aid, "同组匹配({})".format(mtype), ""))

    # 去重 + 排序
    seen = {primary_id}
    unique_related = []
    for score, sid, relation, etype in sorted(related, key=lambda x: -x[0]):
        if sid not in seen:
            seen.add(sid)
            unique_related.append((score, sid, relation, etype))

    # ── 构建候选列表 ──
    candidates = []

    # 第一个候选始终是任务锚点自身
    candidates.append({
        "id": "C0",
        "name": _anchor_attr(primary_anchor, "symbol", ""),
        "entry": primary_id,
        "file": _anchor_attr(primary_anchor, "file", ""),
        "line": _anchor_attr(primary_anchor, "line_start", 0),
        "why": "任务目标 ({})".format(task_matches[0][2]),
        "next_command": "expand {}".format(primary_id),
    })

    # 剩余候选
    for i, (score, sid, relation, etype) in enumerate(unique_related):
        if len(candidates) >= RECOMMENDATION_LIMIT:
            break
        anchor = anchors[sid]
        sym = _anchor_attr(anchor, "symbol", "")
        fpath = _anchor_attr(anchor, "file", "")
        line = _anchor_attr(anchor, "line_start", 0)

        # 构建 why
        why_parts = [relation]
        if etype:
            why_parts.append("via {}".format(etype))
        mod = _find_anchor_module(sid, module_tree)
        if mod:
            why_parts.append("模块: {}".format(mod["name"]))

        candidates.append({
            "id": "C{}".format(i + 1),
            "name": sym,
            "entry": sid,
            "file": fpath,
            "line": line,
            "why": " | ".join(why_parts),
            "next_command": "expand {}".format(sid),
        })

    # ── 收集关键上下文边（不超过 10 条）──
    context_edges = []
    relation_boundaries = []
    for edge in outgoing.get(primary_id, [])[:5]:
        to_id = edge["anchor_id"]
        etype = edge["edge_type"]
        context_edges.append({
            "from": primary_id.split("::")[-1] if "::" in primary_id else primary_id,
            "to": to_id.split("::")[-1] if "::" in to_id else to_id,
            "type": etype,
            "resolution": edge["resolution"],
            "actionable": edge["resolution"] == "exact",
        })
        if edge["resolution"] != "exact":
            relation_boundaries.append({
                "id": "B{}".format(len(relation_boundaries)),
                "from": primary_id,
                "to": to_id,
                "type": etype,
                "resolution": edge["resolution"],
                "evidence": edge.get("evidence"),
                "reason": "非 exact 关系只作为边界，不生成命令",
            })
    for edge in incoming.get(primary_id, [])[:5]:
        from_id = edge["anchor_id"]
        etype = edge["edge_type"]
        context_edges.append({
            "from": from_id.split("::")[-1] if "::" in from_id else from_id,
            "to": primary_id.split("::")[-1] if "::" in primary_id else primary_id,
            "type": etype,
            "resolution": edge["resolution"],
            "actionable": edge["resolution"] == "exact",
        })
        if edge["resolution"] != "exact":
            relation_boundaries.append({
                "id": "B{}".format(len(relation_boundaries)),
                "from": from_id,
                "to": primary_id,
                "type": etype,
                "resolution": edge["resolution"],
                "evidence": edge.get("evidence"),
                "reason": "非 exact 关系只作为边界，不生成命令",
            })

    return {
        "entry": primary_id,
        "candidates": candidates,
        "alternatives": [],
        "boundaries": relation_boundaries[:10],
        "context_edges": context_edges[:10],
        "candidate_policy": "只推荐有直接定位证据的候选；不按数量补齐",
    }

def match_anchor_from_error(error_packet: dict, anchors: dict) -> List[Tuple[str, Any, str]]:
    if not error_packet:
        return []

    file_hint = (error_packet.get("file") or "").replace("\\", "/")
    line_hint = error_packet.get("line")
    if file_hint and line_hint:
        containing = []
        near = []
        for aid, anchor in anchors.items():
            fpath = _anchor_attr(anchor, "file", "").replace("\\", "/")
            if not file_hint.endswith(fpath) and not fpath.endswith(Path(file_hint).name):
                continue
            start = int(_anchor_attr(anchor, "line_start", 0) or 0)
            end = int(_anchor_attr(anchor, "line_end", start) or start)
            if start <= int(line_hint) <= end:
                containing.append((aid, anchor, "error_line"))
            else:
                distance = min(abs(start - int(line_hint)), abs(end - int(line_hint)))
                near.append((distance, aid, anchor))
        if containing:
            containing.sort(key=lambda item: (
                int(_anchor_attr(item[1], "line_end", 0) or 0)
                - int(_anchor_attr(item[1], "line_start", 0) or 0)
            ))
            return containing[:MAX_CANDIDATES]
        if near:
            near.sort(key=lambda item: item[0])
            return [(aid, anchor, "near_error_line") for _, aid, anchor in near[:MAX_CANDIDATES]]

    text = "{} {}".format(error_packet.get("message", ""), error_packet.get("raw_text", ""))
    names = re.findall(r"[A-Za-z_][A-Za-z0-9_\.]{2,}", text)
    for name in names:
        matches = resolve_task_anchor(name, anchors)
        if matches:
            return matches
    return []

def build_anchor_packet(
    task_matches: List[Tuple[str, Any, str]],
    anchors: dict,
    relations: dict,
    max_related: int = 8,
) -> dict:
    if not task_matches:
        return {"target": None, "upstream": [], "downstream": [], "boundaries": []}

    primary_id, primary_anchor, match_type = task_matches[0]
    outgoing, incoming = _build_edge_indexes(relations)

    boundaries = []

    def _related(items, direction):
        rows = []
        for edge in items:
            other_id = edge["anchor_id"]
            edge_type = edge["edge_type"]
            if edge["resolution"] != "exact":
                if len(boundaries) < min(3, max_related):
                    boundaries.append({
                        "anchor": other_id,
                        "edge_type": edge_type,
                        "resolution": edge["resolution"],
                        "direction": direction,
                        "evidence": edge.get("evidence"),
                    })
                continue
            if other_id not in anchors or _is_noise_symbol(other_id):
                continue
            other = anchors[other_id]
            rows.append({
                "anchor": other_id,
                "symbol": _anchor_attr(other, "symbol", ""),
                "file": _anchor_attr(other, "file", ""),
                "line": _anchor_attr(other, "line_start", 0),
                "edge_type": edge_type,
            })
            if len(rows) >= max_related:
                break
        return rows

    return {
        "target": {
            "anchor": primary_id,
            "symbol": _anchor_attr(primary_anchor, "symbol", ""),
            "file": _anchor_attr(primary_anchor, "file", ""),
            "line": _anchor_attr(primary_anchor, "line_start", 0),
            "match_type": match_type,
        },
        "upstream": _related(incoming.get(primary_id, []), "upstream"),
        "downstream": _related(outgoing.get(primary_id, []), "downstream"),
        "boundaries": boundaries[:min(3, max_related)],
    }

def build_control_packet(
    root: str,
    task_matches: List[Tuple[str, Any, str]],
    anchors: dict,
    relations: dict,
    max_callers: int = 3,
) -> dict:
    if not task_matches:
        return {"target": None, "call_paths": [], "boundaries": []}

    primary_id, primary_anchor, _ = task_matches[0]
    target_name = _anchor_attr(primary_anchor, "symbol", "")
    _, incoming = _build_edge_indexes(relations)

    call_paths = []
    boundaries = []
    for edge in incoming.get(primary_id, []):
        caller_id = edge["anchor_id"]
        edge_type = edge["edge_type"]
        if edge["resolution"] != "exact":
            if len(boundaries) < max_callers:
                boundaries.append({
                    "caller": caller_id,
                    "edge_type": edge_type,
                    "resolution": edge["resolution"],
                    "reason": "控制路径需要 exact relation",
                })
            continue
        if caller_id not in anchors or _is_noise_symbol(caller_id):
            continue
        caller = anchors[caller_id]
        source = _read_anchor_source(root, caller, max_lines=120)
        path = _control_path_for_call(
            source,
            target_name,
            int(_anchor_attr(caller, "line_start", 1) or 1),
        ) if source else []
        call_paths.append({
            "caller": caller_id,
            "edge_type": edge_type,
            "file": _anchor_attr(caller, "file", ""),
            "line": _anchor_attr(caller, "line_start", 0),
            "control_path": path,
        })
        if len(call_paths) >= max_callers:
            break

    return {
        "target": primary_id,
        "call_paths": call_paths,
        "boundaries": boundaries[:max_callers],
    }

def build_source_slices(
    root: str,
    task_matches: List[Tuple[str, Any, str]],
    max_lines: int = 40,
) -> list:
    if not task_matches:
        return []
    primary_id, primary_anchor, _ = task_matches[0]
    source = _read_anchor_source(root, primary_anchor, max_lines=max_lines)
    if not source:
        return []
    return [{
        "anchor": primary_id,
        "file": _anchor_attr(primary_anchor, "file", ""),
        "line_start": _anchor_attr(primary_anchor, "line_start", 0),
        "line_end": _anchor_attr(primary_anchor, "line_end", 0),
        "source": source,
    }]

def generate_task_context(
    task_anchor: str,
    root: str = ".",
    budget: int = DEFAULT_BUDGET,
    error_text: Optional[str] = None,
    model_profile: str = "small",
    module_tree: Optional[dict] = None,
    anchors: Optional[dict] = None,
    relations: Optional[dict] = None,
    policy=None,
) -> dict:
    """生成 Task Context Packet。

    Args:
        task_anchor: 任务锚点（symbol_id / 符号名 / 文件路径 / 关键词）
        root: 项目根目录
        budget: token 预算（默认 1200）
        module_tree: Module Tree V2 数据（可选，自动加载）
        anchors: 锚点字典（可选，自动加载）
        relations: 关系字典（可选，自动加载）
        policy: 路径策略（可选，自动加载）

    Returns:
        Task Context Packet JSON 结构
    """
    # ── 加载依赖 ──
    if policy is None:
        from synth.api.path_policy import load_path_policy
        policy = load_path_policy(root)

    if anchors is None:
        from index.api.anchors import load_anchors
        anchors = load_anchors(root)

    relation_coverage = "available"
    if relations is None:
        from relate.api.relations import load_relations
        try:
            relations = load_relations(root)
        except FileNotFoundError:
            # 关系是增强证据，不应让基础任务定位整体失效。
            relations = {"edges": [], "meta": {"status": "unavailable"}}
            relation_coverage = "unavailable"

    if module_tree is None:
        tree_path = Path(root) / ".codedendrite" / "module_tree_v2.json"
        if tree_path.exists():
            with open(tree_path, encoding="utf-8") as f:
                module_tree = json.load(f)

    # ── 解析任务锚点 ──
    raw_task_matches = resolve_task_anchor(task_anchor, anchors)
    error_packet = build_error_packet(error_text)
    if not raw_task_matches and error_packet:
        raw_task_matches = match_anchor_from_error(error_packet, anchors)
    navigation = assess_task_matches(task_anchor, raw_task_matches)
    navigation["relation_coverage"] = relation_coverage
    navigation["relation_resolution_counts"] = _relation_resolution_counts(relations)
    task_matches = raw_task_matches if navigation["safe_to_recommend"] else []

    # ── 构建三层 ──
    level0 = build_level0(root, module_tree, anchors, policy)
    level1 = build_level1(task_matches, module_tree, anchors, relations, policy)
    level2 = build_level2(
        task_matches, level1, anchors, relations, module_tree, policy, budget,
    )
    ambiguous_matches = [
        {
            "id": "A{}".format(index),
            "anchor": aid,
            "file": _anchor_attr(anchor, "file", ""),
            "line": _anchor_attr(anchor, "line_start", 0),
            "match_type": match_type,
            "resolution": "possible",
            "reason": "任务入口存在歧义；只作为 alternative，不生成命令",
        }
        for index, (aid, anchor, match_type) in enumerate(
            raw_task_matches[:MAX_CANDIDATES]
        )
    ] if not task_matches else []
    level2["alternatives"] = ambiguous_matches
    anchor_packet = build_anchor_packet(task_matches, anchors, relations)
    control_packet = build_control_packet(root, task_matches, anchors, relations)
    source_slices = build_source_slices(root, task_matches) if model_profile == "large" else []

    # ── 组装 ──
    context = {
        "version": "task_context_packet_v1",
        "task_query": task_anchor,
        "model_profile": model_profile,
        "resolved_anchor": task_matches[0][0] if task_matches else None,
        "match_count": len(raw_task_matches),
        "navigation": navigation,
        "ambiguous_matches": ambiguous_matches,
        "project_brief": level0,
        "error_packet": error_packet,
        "area_map": level1,
        "task_slice": level2,
        "anchor_packet": anchor_packet,
        "control_packet": control_packet,
        "source_slices": source_slices,
        "_level3_on_demand": True,
        "token_estimate": {
            "level0": _estimate_obj_tokens(level0),
            "level1": _estimate_obj_tokens(level1),
            "level2": _estimate_obj_tokens(level2),
            "error": _estimate_obj_tokens(error_packet),
            "navigation": _estimate_obj_tokens(navigation),
            "anchor_packet": _estimate_obj_tokens(anchor_packet),
            "control_packet": _estimate_obj_tokens(control_packet),
            "source_slices": _estimate_obj_tokens(source_slices),
            "total": (
                _estimate_obj_tokens(level0)
                + _estimate_obj_tokens(level1)
                + _estimate_obj_tokens(level2)
                + _estimate_obj_tokens(error_packet)
                + _estimate_obj_tokens(navigation)
                + _estimate_obj_tokens(anchor_packet)
                + _estimate_obj_tokens(control_packet)
                + _estimate_obj_tokens(source_slices)
            ),
        },
    }
    context["prompt"] = assemble_task_prompt(context, profile=model_profile)
    context["token_estimate"]["prompt"] = _estimate_tokens(context["prompt"])

    return context
