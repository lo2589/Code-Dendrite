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

def _plugin_error(ctx: dict) -> Optional[str]:
    packet = ctx.get("error_packet") or {}
    if not packet:
        return None
    return "Error:\n{}".format(json.dumps(packet, ensure_ascii=False, indent=2))

def _plugin_framework(ctx: dict) -> Optional[str]:
    return (
        "Read the package in order: navigation, project, error, anchors, control. "
        "Candidates are static evidence, not a confirmed bug location. "
        "If navigation is ambiguous, search before expanding."
    )

def _plugin_navigation(ctx: dict) -> Optional[str]:
    packet = ctx.get("navigation") or {}
    return "Navigation:\n{}".format(json.dumps(packet, ensure_ascii=False, indent=2)) if packet else None

def _plugin_project(ctx: dict) -> Optional[str]:
    brief = ctx.get("project_brief") or {}
    if not brief:
        return None
    return "Project:\n{}".format(json.dumps(brief, ensure_ascii=False, indent=2))

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

LARGE_PROMPT_PLUGINS: List[Callable[[dict], Optional[str]]] = [
    _plugin_framework,
    _plugin_navigation,
    _plugin_project,
    _plugin_error,
    _plugin_anchor,
    _plugin_control,
    _plugin_source,
]

SMALL_PROMPT_PLUGINS: List[Callable[[dict], Optional[str]]] = [
    _plugin_framework,
    _plugin_navigation,
    _plugin_project,
    _plugin_error,
    _plugin_anchor,
    _plugin_control,
]

def _is_test_file(file_name: str) -> bool:
    normalized = file_name.replace("\\", "/")
    return normalized.startswith("tests/") or "/tests/" in normalized

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

def _short_condition(node: ast.AST, source: str) -> str:
    try:
        text = ast.get_source_segment(source, node)
    except Exception:
        text = None
    text = (text or ast.dump(node, include_attributes=False))
    text = " ".join(text.strip().split())
    return text[:160]

def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return "{}.{}".format(base, node.attr) if base else node.attr
    return ""

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

def _symbol_tail(symbol_id: str) -> str:
    symbol = symbol_id.split("::")[-1]
    return symbol.split(".")[-1]

def _is_noise_symbol(symbol_id: str) -> bool:
    tail = _symbol_tail(symbol_id)
    return tail in NOISE_SYMBOLS or tail.startswith("_print")

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

def assemble_task_prompt(context: dict, profile: str = "small") -> str:
    plugins = LARGE_PROMPT_PLUGINS if profile == "large" else SMALL_PROMPT_PLUGINS
    parts = []
    for plugin in plugins:
        part = plugin(context)
        if part:
            parts.append(part)
    return "\n\n".join(parts)

def _relation_resolution_counts(relations: dict) -> dict:
    counts = defaultdict(int)
    for edge in relations.get("edges", []):
        counts[edge.get("resolution") or "resolution_unavailable"] += 1
    return dict(sorted(counts.items()))
