"""
jump_packet.py — 每跳一个任务包，给 lite 模型用

    build_jump_packet(symbol, root, error_text, visited_chain) → str
    SYSTEM_PROMPT → 固定系统提示
"""

from __future__ import annotations
from typing import List, Optional

SYSTEM_PROMPT = """你是代码修复 agent。每轮收到一个任务包，只做一件事：

1. 当前源码 + 调用关系够定位 bug → 直接输出修复（unified diff 格式）
2. 需要看其他函数 → 输出 {"jump": "symbol名"}
3. 改完 → 输出 {"fixed": "一句话说改了什么"}

规则：
- 每次只跳一层，不要一次跳多个
- 已探索链路里的 symbol 不要重复跳
- 看不出来但信息足够多时，优先尝试修复而不是继续跳"""


def build_jump_packet(
    symbol: str,
    root: str = ".",
    error_text: str = "",
    visited_chain: Optional[List[str]] = None,
    project_brief: str = "",
) -> str:
    """
    构建单跳任务包。每次 lite 模型跳到新函数时调用。

    Args:
        symbol:        当前 anchor symbol
        root:          项目根目录
        error_text:    报错信息（整个任务期间保持不变）
        visited_chain: 已跳过的路径（从上一跳的结果里取）
        project_brief: 项目一句话描述（第一跳时生成，之后复用）

    Returns:
        给 lite 模型的完整 prompt 字符串
    """
    from api.inspector import get_anchor_source, get_anchor_relations, get_upward_chain

    src = get_anchor_source(symbol, root)
    rel = get_anchor_relations(symbol, root, history=visited_chain)
    up_chain = get_upward_chain(symbol, root)

    if not src or not rel:
        return f"[ERROR] 找不到 anchor: {symbol}"

    chain = rel["visited_chain"]

    # 项目简介
    brief = project_brief or _infer_brief(root)

    # 源码块
    source_block = src["source"]

    # 调用关系
    callers_resolved = [c for c in rel["callers"] if c["resolved"]]
    callees_resolved = [c for c in rel["callees"] if c["resolved"]]
    callers_str = ", ".join(c["symbol"] for c in callers_resolved) or "（无）"
    callees_str = ", ".join(
        f'{c["symbol"]}({"✓" if c["resolved"] else "✗"})' for c in rel["callees"]
    ) or "（无）"

    # 跳转选项
    options = []
    for c in callees_resolved:
        if c["symbol"] not in chain:
            options.append(f'  → {c["symbol"]}  ({c["file"]}:{c["line"]})')
    for c in callers_resolved:
        if c["symbol"] not in chain:
            options.append(f'  ← {c["symbol"]}  ({c["file"]}:{c["line"]})')
    options_str = "\n".join(options) if options else "  （已探索完毕或无关联）"

    # 上行链路（谁调用了当前函数，往上追）
    up_lines = []
    for node in up_chain:
        prefix = "  " * node["depth"]
        loc = f"  ({node['file']}:{node['line']})" if node["file"] else ""
        up_lines.append(f"{prefix}{node['symbol']}{loc}")
    up_chain_str = "\n".join(up_lines) if up_chain else "  （无）"

    return f"""## 项目
{brief}

## 报错
{error_text or "（无报错信息）"}

## 上行调用链（谁调用了当前函数）
{up_chain_str}

## 已探索链路
{" → ".join(chain)}

## 当前 anchor
{src["symbol"]}  {src["file"]} L{src["line_start"]}-{src["line_end"]}
```python
{source_block}
```

## 调用关系
callers: {callers_str}
callees: {callees_str}

## 可跳转选项
{options_str}

---
判断：信息够修 → 直接给 diff；需要更多 → {{"jump": "symbol"}}"""


def _infer_brief(root: str) -> str:
    """从 project_summary.md 取第一句，没有就返回目录名。"""
    from pathlib import Path
    summary_path = Path(root) / ".codedendrite" / "project_summary.md"
    if summary_path.exists():
        for line in summary_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line[:120]
    return Path(root).resolve().name
