"""
dynamic_store.py — 动态分析数据存储层

读写 trace_events.jsonl / executed_edges.json / routes.json。
不依赖 CodeDendrite 其他模块。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


# ── 默认路径 ────────────────────────────────────────────

_CODEDENDRITE_BASE = Path.home() / ".codedendrite"


def get_dynamic_dir(project_path: str) -> Path:
    """返回动态数据目录，自动创建。"""
    project_name = Path(project_path).resolve().name
    dyn_dir = _CODEDENDRITE_BASE / project_name / "dynamic"
    dyn_dir.mkdir(parents=True, exist_ok=True)
    return dyn_dir


# ── trace_events.jsonl ──────────────────────────────────

def append_trace_event(project_path: str, event: dict) -> None:
    """追加一条 trace 事件到 JSONL 文件。"""
    dyn_dir = get_dynamic_dir(project_path)
    filepath = dyn_dir / "trace_events.jsonl"
    with open(filepath, "a", encoding="utf-8", errors="replace") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def iter_trace_events(project_path: str):
    """逐行读取 trace_events.jsonl，返回 dict 迭代器。"""
    dyn_dir = get_dynamic_dir(project_path)
    filepath = dyn_dir / "trace_events.jsonl"
    if not filepath.exists():
        return
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


# ── executed_edges.json ─────────────────────────────────

def save_executed_edges(project_path: str, edges: list[dict]) -> Path:
    """保存执行边列表。"""
    dyn_dir = get_dynamic_dir(project_path)
    filepath = dyn_dir / "executed_edges.json"
    with open(filepath, "w", encoding="utf-8", errors="replace") as f:
        json.dump(edges, f, ensure_ascii=False, indent=2)
    return filepath


def load_executed_edges(project_path: str) -> list[dict]:
    """加载执行边列表。"""
    dyn_dir = get_dynamic_dir(project_path)
    filepath = dyn_dir / "executed_edges.json"
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


# ── routes.json ─────────────────────────────────────────

def save_routes(project_path: str, routes: dict) -> Path:
    """保存路由映射。"""
    dyn_dir = get_dynamic_dir(project_path)
    filepath = dyn_dir / "routes.json"
    with open(filepath, "w", encoding="utf-8", errors="replace") as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)
    return filepath


def load_routes(project_path: str) -> dict:
    """加载路由映射。"""
    dyn_dir = get_dynamic_dir(project_path)
    filepath = dyn_dir / "routes.json"
    if not filepath.exists():
        return {"dispatch_routes": []}
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


# ── 清理 ────────────────────────────────────────────────

def clear_trace_events(project_path: str) -> None:
    """清空 trace_events.jsonl（重新收集前调用）。"""
    dyn_dir = get_dynamic_dir(project_path)
    filepath = dyn_dir / "trace_events.jsonl"
    if filepath.exists():
        filepath.write_text("", encoding="utf-8")
