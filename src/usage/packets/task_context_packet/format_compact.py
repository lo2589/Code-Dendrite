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

from usage.packets.task_context_packet.plugin import _estimate_tokens

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
    navigation = context.get("navigation", {})
    lines.append("导航置信: {}/{} | {}".format(
        navigation.get("status", "unknown"),
        navigation.get("confidence", "unknown"),
        navigation.get("reason", ""),
    ))

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

    alternatives = task.get("alternatives", [])
    if alternatives:
        lines.append("Alternatives（仅证据，不执行）:")
        for item in alternatives[:3]:
            lines.append("  {} {}:{} [{}]".format(
                item["id"], item["file"], item["line"], item["match_type"],
            ))

    boundaries = task.get("boundaries", [])
    if boundaries:
        lines.append("关系边界:")
        for item in boundaries[:5]:
            lines.append("  {} {}→{} ({}/{})".format(
                item["id"], item["from"].split("::")[-1],
                item["to"].split("::")[-1], item["type"], item["resolution"],
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

def save_task_context(context: dict, root: str = ".") -> str:
    """保存 Task Context Packet 到 .codedendrite/task_context.json。"""
    output_dir = Path(root) / ".codedendrite"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "task_context.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(context, f, ensure_ascii=False, indent=2)

    return str(output_path)
