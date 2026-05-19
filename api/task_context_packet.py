"""Task Context Packet — 给小模型/执行 agent 生成当前任务的窄上下文包。

设计文档: todo/codedentrite/CD_四类结构图认知整理.md §4

四级上下文:
  Level 0: Project Brief (30-80 tokens)  — 项目一句话 + 顶层区域
  Level 1: Area Map (100-300 tokens)     — 当前任务所在区域
  Level 2: Task Slice (300-800 tokens)   — 3-7 个候选 + why + next_command
  Level 3: Source Snippet (按需)         — 默认不给

验收标准:
  1. Level 0 不超过 3 句
  2. Level 1 只描述当前区域
  3. Level 2 只给 3-7 个候选
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
MIN_CANDIDATES = 3
NOISE_SYMBOLS = {
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set",
    "Path", "open", "json.dumps", "json.loads", "time.sleep",
}


# ── 工具函数 ─────────────────────────────────────────────────────

def _anchor_attr(anchor, key: str, default=""):
    """从 Anchor 对象或 dict 中读取属性。"""
    if isinstance(anchor, dict):
        return anchor.get(key, default)
    return getattr(anchor, key, default)


def _estimate_tokens(text: str) -> int:
    """粗估 token 数。英文 ~4 字符/token，中文 ~1.5 字符/token。"""
    if not text:
        return 0
    ascii_count = sum(1 for c in text if ord(c) < 128)
    cjk_count = len(text) - ascii_count
    return int(ascii_count / 4 + cjk_count / 1.5)


def _estimate_obj_tokens(obj) -> int:
    """估算 JSON 对象序列化后的 token 数。"""
    return _estimate_tokens(json.dumps(obj, ensure_ascii=False))


def _anchor_id(anchor) -> str:
    aid = _anchor_attr(anchor, "id", "")
    if aid:
        return aid.replace("\\", "/")
    fpath = _anchor_attr(anchor, "file", "").replace("\\", "/")
    symbol = _anchor_attr(anchor, "symbol", "")
    return "{}::{}".format(fpath, symbol) if fpath and symbol else ""


def _symbol_tail(symbol_id: str) -> str:
    symbol = symbol_id.split("::")[-1]
    return symbol.split(".")[-1]


def _is_noise_symbol(symbol_id: str) -> bool:
    tail = _symbol_tail(symbol_id)
    return tail in NOISE_SYMBOLS or tail.startswith("_print")


def _read_anchor_source(root: str, anchor, max_lines: int = 80) -> str:
    fpath = _anchor_attr(anchor, "file", "")
    start = int(_anchor_attr(anchor, "line_start", 1) or 1)
    end = int(_anchor_attr(anchor, "line_end", start) or start)
    path = Path(root) / fpath
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lo = max(0, start - 1)
    hi = min(len(lines), max(start, min(end, start + max_lines - 1)))
    return "\n".join(lines[lo:hi])


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return "{}.{}".format(base, node.attr) if base else node.attr
    return ""


def _short_condition(node: ast.AST, source: str) -> str:
    try:
        text = ast.get_source_segment(source, node)
    except Exception:
        text = None
    text = (text or ast.dump(node, include_attributes=False))
    text = " ".join(text.strip().split())
    return text[:160]


# ── 锚点解析 ─────────────────────────────────────────────────────

def resolve_task_anchor(
    query: str,
    anchors: dict,
) -> List[Tuple[str, Any, str]]:
    """将用户输入解析为匹配的锚点列表。

    匹配策略（按优先级）:
      1. 精确 ID: "file.py::symbol"
      2. 符号名:  "create_anchor"
      3. 文件路径: "api/anchors.py"
      4. 关键词:   "anchor"

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

    # 策略 2: 符号名匹配
    for aid, anchor in anchors.items():
        sym = _anchor_attr(anchor, "symbol", "")
        if sym == query_norm:
            results.append((aid, anchor, "symbol_name"))
    if results:
        return results[:MAX_CANDIDATES]

    # 策略 3: 文件路径匹配
    for aid, anchor in anchors.items():
        fpath = _anchor_attr(anchor, "file", "")
        if fpath.replace("\\", "/") == query_norm:
            results.append((aid, anchor, "file_path"))
    if results:
        return results[:MAX_CANDIDATES]

    # 策略 4: 关键词模糊匹配
    query_lower = query_norm.lower()
    scored = []
    for aid, anchor in anchors.items():
        sym = _anchor_attr(anchor, "symbol", "").lower()
        fpath = _anchor_attr(anchor, "file", "").lower()
        score = 0
        if query_lower in sym:
            score += 3
        if query_lower in fpath:
            score += 1
        if query_lower in aid.lower():
            score += 2
        if score > 0:
            scored.append((score, aid, anchor))

    scored.sort(key=lambda x: -x[0])
    return [(aid, anch, "keyword") for _, aid, anch in scored[:MAX_CANDIDATES]]


# ── 边索引构建 ───────────────────────────────────────────────────

def _build_edge_indexes(relations: dict):
    """构建出边/入边索引。"""
    outgoing = defaultdict(list)   # symbol -> [(to_id, edge_type)]
    incoming = defaultdict(list)   # symbol -> [(from_id, edge_type)]
    edges = relations.get("edges", [])
    for e in edges:
        fid = e.get("from_id", "")
        tid = e.get("to_id", "")
        etype = e.get("edge_type", "")
        if fid and tid:
            outgoing[fid].append((tid, etype))
            incoming[tid].append((fid, etype))
    return outgoing, incoming


# ── Level 0: Project Brief ──────────────────────────────────────

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


# ── Level 1: Area Map ──────────────────────────────────────────

def _find_anchor_area(anchor_id: str, anchor) -> str:
    """确定锚点所在的区域（顶层目录）。"""
    fpath = _anchor_attr(anchor, "file", "")
    parts = fpath.replace("\\", "/").split("/")
    if len(parts) > 1:
        return parts[0]
    return ""


def _find_anchor_module(anchor_id: str, module_tree: Optional[dict]) -> Optional[dict]:
    """在 module_tree 中查找包含该锚点的模块。"""
    if not module_tree:
        return None
    for mod in module_tree.get("modules", []):
        # 检查 entrypoints
        if anchor_id in mod.get("entrypoints", []):
            return mod
        # 检查 functions
        if anchor_id in mod.get("functions", []):
            return mod
        # 检查文件
        fpath = anchor_id.split("::")[0] if "::" in anchor_id else ""
        if fpath and fpath in mod.get("files", []):
            return mod
    return None


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


# ── Level 2: Task Slice ──────────────────────────────────────────

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
    """生成 L2 — 3-7 个候选 + why + next_command。

    目标: 300-800 tokens，每个候选都有 why 和 next_command。
    """
    if not task_matches:
        return {"entry": "", "candidates": [], "context_edges": []}

    primary_id = task_matches[0][0]
    primary_anchor = task_matches[0][1]
    task_area = area_info.get("current_area", "")
    outgoing, incoming = _build_edge_indexes(relations)

    # ── 收集相关符号 ──
    related = []

    # 从任务锚点出发的出边（任务调用了什么）
    for to_id, etype in outgoing.get(primary_id, []):
        if to_id in anchors:
            s = _score_related_symbol(
                to_id, anchors[to_id], "callee", etype, task_area,
            )
            related.append((s, to_id, "被任务调用", etype))

    # 指向任务锚点的入边（谁调用了任务）
    for from_id, etype in incoming.get(primary_id, []):
        if from_id in anchors:
            s = _score_related_symbol(
                from_id, anchors[from_id], "caller", etype, task_area,
            )
            related.append((s, from_id, "调用了任务", etype))

    # 如果匹配了多个锚点，把其他匹配也加进来
    for aid, anchor, mtype in task_matches[1:]:
        related.append((4, aid, "同组匹配({})".format(mtype), ""))

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
        if len(candidates) >= MAX_CANDIDATES:
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

    # 确保至少 MIN_CANDIDATES 个 — 从同文件其他锚点补充
    if len(candidates) < MIN_CANDIDATES:
        primary_file = _anchor_attr(primary_anchor, "file", "")
        for aid, anchor in anchors.items():
            if len(candidates) >= MIN_CANDIDATES:
                break
            if aid in seen:
                continue
            if _anchor_attr(anchor, "file", "") == primary_file:
                seen.add(aid)
                candidates.append({
                    "id": "C{}".format(len(candidates)),
                    "name": _anchor_attr(anchor, "symbol", ""),
                    "entry": aid,
                    "file": _anchor_attr(anchor, "file", ""),
                    "line": _anchor_attr(anchor, "line_start", 0),
                    "why": "同文件符号",
                    "next_command": "expand {}".format(aid),
                })

    # ── 收集关键上下文边（不超过 10 条）──
    context_edges = []
    for to_id, etype in outgoing.get(primary_id, [])[:5]:
        context_edges.append({
            "from": primary_id.split("::")[-1] if "::" in primary_id else primary_id,
            "to": to_id.split("::")[-1] if "::" in to_id else to_id,
            "type": etype,
        })
    for from_id, etype in incoming.get(primary_id, [])[:5]:
        context_edges.append({
            "from": from_id.split("::")[-1] if "::" in from_id else from_id,
            "to": primary_id.split("::")[-1] if "::" in primary_id else primary_id,
            "type": etype,
        })

    return {
        "entry": primary_id,
        "candidates": candidates,
        "context_edges": context_edges[:10],
    }


# Task package plugins -----------------------------------------------------

def build_error_packet(error_text: Optional[str]) -> dict:
    if not error_text:
        return {}

    packet = {
        "raw_text": error_text.strip(),
        "error_type": "",
        "message": "",
        "file": "",
        "line": None,
        "stack": [],
    }

    lines = [line.rstrip() for line in error_text.splitlines() if line.strip()]
    if lines:
        packet["message"] = lines[-1]
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning))\s*:\s*(.*)", lines[-1])
        if m:
            packet["error_type"] = m.group(1)
            packet["message"] = m.group(2)

    frame_re = re.compile(r'File "([^"]+)", line (\d+)(?:, in ([^\s]+))?')
    for line in lines:
        m = frame_re.search(line)
        if not m:
            continue
        frame = {
            "file": m.group(1).replace("\\", "/"),
            "line": int(m.group(2)),
            "function": m.group(3) or "",
        }
        packet["stack"].append(frame)
        packet["file"] = frame["file"]
        packet["line"] = frame["line"]

    return packet


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
        return {"target": None, "upstream": [], "downstream": []}

    primary_id, primary_anchor, match_type = task_matches[0]
    outgoing, incoming = _build_edge_indexes(relations)

    def _related(items):
        rows = []
        for other_id, edge_type in items:
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
        "upstream": _related(incoming.get(primary_id, [])),
        "downstream": _related(outgoing.get(primary_id, [])),
    }


def _control_path_for_call(source: str, target_name: str, caller_line: int) -> list:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [{"kind": "parse_error", "detail": str(exc)}]

    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    target_tail = target_name.split(".")[-1]
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name == target_name or name.endswith("." + target_tail) or name == target_tail:
            calls.append(node)

    if not calls:
        return []

    calls.sort(key=lambda n: abs(getattr(n, "lineno", 0) - caller_line))
    call = calls[0]
    path = [{
        "kind": "call",
        "line": getattr(call, "lineno", 0),
        "target": _call_name(call.func),
    }]

    node = parents.get(call)
    controls = []
    while node is not None:
        if isinstance(node, ast.If):
            controls.append({
                "kind": "if",
                "line": getattr(node, "lineno", 0),
                "condition": _short_condition(node.test, source),
            })
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            controls.append({
                "kind": "for",
                "line": getattr(node, "lineno", 0),
                "condition": _short_condition(node.target, source) + " in " + _short_condition(node.iter, source),
            })
        elif isinstance(node, ast.While):
            controls.append({
                "kind": "while",
                "line": getattr(node, "lineno", 0),
                "condition": _short_condition(node.test, source),
            })
        elif isinstance(node, ast.Try):
            controls.append({
                "kind": "try",
                "line": getattr(node, "lineno", 0),
                "condition": "try/except",
            })
        node = parents.get(node)

    path.extend(reversed(controls))
    return path


def build_control_packet(
    root: str,
    task_matches: List[Tuple[str, Any, str]],
    anchors: dict,
    relations: dict,
    max_callers: int = 3,
) -> dict:
    if not task_matches:
        return {"target": None, "call_paths": []}

    primary_id, primary_anchor, _ = task_matches[0]
    target_name = _anchor_attr(primary_anchor, "symbol", "")
    _, incoming = _build_edge_indexes(relations)

    call_paths = []
    for caller_id, edge_type in incoming.get(primary_id, []):
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


def _plugin_framework(ctx: dict) -> Optional[str]:
    return "Read the package in order: project, error, anchors, control. If more context is needed, reply with @anchor_id or @function_name."


def _plugin_project(ctx: dict) -> Optional[str]:
    brief = ctx.get("project_brief") or {}
    if not brief:
        return None
    return "Project:\n{}".format(json.dumps(brief, ensure_ascii=False, indent=2))


def _plugin_error(ctx: dict) -> Optional[str]:
    packet = ctx.get("error_packet") or {}
    if not packet:
        return None
    return "Error:\n{}".format(json.dumps(packet, ensure_ascii=False, indent=2))


def _plugin_anchor(ctx: dict) -> Optional[str]:
    packet = ctx.get("anchor_packet") or {}
    if not packet:
        return None
    return "Anchors:\n{}".format(json.dumps(packet, ensure_ascii=False, indent=2))


def _plugin_control(ctx: dict) -> Optional[str]:
    packet = ctx.get("control_packet") or {}
    if not packet:
        return None
    return "Control:\n{}".format(json.dumps(packet, ensure_ascii=False, indent=2))


def _plugin_source(ctx: dict) -> Optional[str]:
    slices = ctx.get("source_slices") or []
    if not slices:
        return None
    rendered = []
    for item in slices[:1]:
        rendered.append("{}:{}\n```python\n{}\n```".format(
            item.get("file", ""),
            item.get("line_start", ""),
            item.get("source", ""),
        ))
    return "Source:\n{}".format("\n\n".join(rendered))


SMALL_PROMPT_PLUGINS: List[Callable[[dict], Optional[str]]] = [
    _plugin_framework,
    _plugin_project,
    _plugin_error,
    _plugin_anchor,
    _plugin_control,
]

LARGE_PROMPT_PLUGINS: List[Callable[[dict], Optional[str]]] = [
    _plugin_framework,
    _plugin_project,
    _plugin_error,
    _plugin_anchor,
    _plugin_control,
    _plugin_source,
]


def assemble_task_prompt(context: dict, profile: str = "small") -> str:
    plugins = LARGE_PROMPT_PLUGINS if profile == "large" else SMALL_PROMPT_PLUGINS
    parts = []
    for plugin in plugins:
        part = plugin(context)
        if part:
            parts.append(part)
    return "\n\n".join(parts)


# ── 主入口 ────────────────────────────────────────────────────────

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
        from api.path_policy import load_path_policy
        policy = load_path_policy(root)

    if anchors is None:
        from api.anchors import load_anchors
        anchors = load_anchors(root)

    if relations is None:
        from api.relations import load_relations
        relations = load_relations(root)

    if module_tree is None:
        tree_path = Path(root) / ".codedendrite" / "module_tree_v2.json"
        if tree_path.exists():
            with open(tree_path, encoding="utf-8") as f:
                module_tree = json.load(f)

    # ── 解析任务锚点 ──
    task_matches = resolve_task_anchor(task_anchor, anchors)
    error_packet = build_error_packet(error_text)
    if not task_matches and error_packet:
        task_matches = match_anchor_from_error(error_packet, anchors)

    # ── 构建三层 ──
    level0 = build_level0(root, module_tree, anchors, policy)
    level1 = build_level1(task_matches, module_tree, anchors, relations, policy)
    level2 = build_level2(
        task_matches, level1, anchors, relations, module_tree, policy, budget,
    )
    anchor_packet = build_anchor_packet(task_matches, anchors, relations)
    control_packet = build_control_packet(root, task_matches, anchors, relations)
    source_slices = build_source_slices(root, task_matches) if model_profile == "large" else []

    # ── 组装 ──
    context = {
        "version": "task_context_packet_v1",
        "task_query": task_anchor,
        "model_profile": model_profile,
        "resolved_anchor": task_matches[0][0] if task_matches else None,
        "match_count": len(task_matches),
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
            "anchor_packet": _estimate_obj_tokens(anchor_packet),
            "control_packet": _estimate_obj_tokens(control_packet),
            "total": (
                _estimate_obj_tokens(level0)
                + _estimate_obj_tokens(level1)
                + _estimate_obj_tokens(level2)
                + _estimate_obj_tokens(error_packet)
                + _estimate_obj_tokens(anchor_packet)
                + _estimate_obj_tokens(control_packet)
            ),
        },
    }
    context["prompt"] = assemble_task_prompt(context, profile=model_profile)
    context["token_estimate"]["prompt"] = _estimate_tokens(context["prompt"])

    return context


def save_task_context(context: dict, root: str = ".") -> str:
    """保存 Task Context Packet 到 .codedendrite/task_context.json。"""
    output_dir = Path(root) / ".codedendrite"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "task_context.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(context, f, ensure_ascii=False, indent=2)

    return str(output_path)


# ── 紧凑文本格式（直接喂给小模型）──────────────────────────────

def format_compact(context: dict) -> str:
    """将 Task Context Packet 转为紧凑纯文本，直接注入小模型 prompt。

    输出示例:
    ---
    项目: CodeDendrite (30 个功能模块)
    区域: api | 提供 create_anchor 等入口能力
    任务: api/anchors.py::create_anchor

    候选:
    C0 create_anchor [任务目标] → expand api/anchors.py::create_anchor
    C1 Anchor [被任务调用 via call] → expand shared/types.py::Anchor

    边: create_anchor→Anchor(call), load_anchors→create_anchor(call)
    ---
    """
    lines = []

    # L0
    brief = context.get("project_brief", {})
    lines.append("项目: {}".format(brief.get("project", "?")))
    areas = brief.get("areas", [])
    if areas:
        lines.append("区域列表: {}".format(", ".join(areas)))

    # L1
    area = context.get("area_map", {})
    lines.append("当前区域: {} | {}".format(
        area.get("current_area", "?"),
        area.get("responsibility", "?"),
    ))
    lines.append("任务锚点: {}".format(area.get("task_anchor", "?")))

    area_mods = area.get("area_modules", [])
    if area_mods:
        mod_names = [m["name"] for m in area_mods[:5]]
        lines.append("区域模块: {}".format(", ".join(mod_names)))

    lines.append("")

    # L2
    task = context.get("task_slice", {})
    candidates = task.get("candidates", [])
    if candidates:
        lines.append("候选:")
        for c in candidates:
            lines.append("  {} {} [{}] → {}".format(
                c["id"], c["name"], c["why"], c["next_command"],
            ))

    edges = task.get("context_edges", [])
    if edges:
        lines.append("")
        edge_strs = [
            "{}→{}({})".format(e["from"], e["to"], e["type"])
            for e in edges[:6]
        ]
        lines.append("边: {}".format(", ".join(edge_strs)))

    return "\n".join(lines)


def format_compact_tokens(context: dict) -> int:
    """估算 compact 格式的 token 数。"""
    return _estimate_tokens(format_compact(context))
