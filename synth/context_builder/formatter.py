"""
formatter.py — 地图格式化工具

提供不同目标格式的输出：
  - Markdown（人类阅读）
  - JSON（机器处理）
  - Compact（AI system prompt，token 最省）
"""
from __future__ import annotations

import json
from typing import Any


def format_map(map_text: str, output_format: str = "markdown") -> str:
    """
    将 build_map() 的输出转换为指定格式。

    参数：
        map_text:      build_map() 返回的原始文本
        output_format: "markdown" | "compact" | "json"
    """
    if output_format == "markdown":
        return map_text  # 原始格式已经是 Markdown

    if output_format == "compact":
        return _to_compact(map_text)

    if output_format == "json":
        return _to_json(map_text)

    return map_text


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（按字符数 / 4）。"""
    return len(text) // 4


def truncate_to_budget(text: str, budget_tokens: int) -> str:
    """将文本截断到 token 预算内，保留完整行。"""
    budget_chars = budget_tokens * 4
    if len(text) <= budget_chars:
        return text

    lines = text.splitlines(keepends=True)
    result = []
    used = 0
    for line in lines:
        if used + len(line) > budget_chars:
            result.append("\n... (已截断，超出 token 预算)")
            break
        result.append(line)
        used += len(line)

    return "".join(result)


def _to_compact(map_text: str) -> str:
    """
    压缩格式：去掉空行、缩短缩进、合并短行。
    用于 token 极度紧张的场景。
    """
    lines = map_text.splitlines()
    compact = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # 节标题保留
        if stripped.startswith("#"):
            compact.append(stripped)
        else:
            compact.append(stripped)
    return "\n".join(compact)


def _to_json(map_text: str) -> str:
    """
    将 Markdown 地图解析为结构化 JSON。
    """
    sections: dict[str, Any] = {}
    current_section = "header"
    sections[current_section] = []

    for line in map_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped[3:].strip()
            sections[current_section] = []
        elif stripped and not stripped.startswith("#"):
            sections[current_section].append(stripped)

    return json.dumps(sections, ensure_ascii=False, indent=2)
