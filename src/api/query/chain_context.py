"""chain2context：对一个锚点打链，把链上所有 anchor 组装成上下文。

打链只回答"谁连着谁"；真正要投喂还得回答"每个 anchor 长什么样、给多少"。
所以这里分三步，一步一个函数：

  collect_chain    打链 → 有序去重的 anchor 列表（带跳数与方向）
  read_sources     逐个取源码，取不到就标出来，不假装有
  render_context   按字符预算组装 markdown，被挤掉的 anchor 单列一栏

不静默丢东西是这套东西的规矩：预算不够时，落选的 anchor 连同位置一起列出来，
看的人自己决定是加预算还是换目标。
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_DEPTH = 6
DEFAULT_BUDGET = 60000


def _resolve(symbol: str, root: str):
    """把用户给的写法收敛成一个 anchor。返回 (anchor, None) 或 (None, 退出码)。"""
    from analyzer.anchors import resolve_anchor_candidates

    candidates = [
        anchor for anchor in resolve_anchor_candidates(symbol, root)
        if not anchor.is_virtual
    ]
    if not candidates:
        print(f"No anchor found for: {symbol}", file=sys.stderr)
        return None, 1
    unique = {anchor.id: anchor for anchor in candidates}
    if len(unique) > 1:
        print(f"Ambiguous symbol '{symbol}'; no chain was guessed. "
              f"Use a full anchor ID:", file=sys.stderr)
        for anchor_id in sorted(unique):
            anchor = unique[anchor_id]
            print(f"  {anchor_id}  {anchor.file}:{anchor.line_start}", file=sys.stderr)
        return None, 2
    return next(iter(unique.values())), 0


def _entry(anchor_id: str, hop: int, direction: str) -> dict:
    return {"id": anchor_id, "hop": hop, "direction": direction}


def collect_chain(symbol: str, root: str, depth: int, direction: str):
    """打链。返回 (目标 anchor, 有序去重的条目列表, 统计, 退出码)。"""
    from api.inspector import get_downward_chain, get_upward_chain

    entry_anchor, code = _resolve(symbol, root)
    if entry_anchor is None:
        return None, [], {}, code

    start = entry_anchor.id
    entries = [_entry(start, 0, "start")]
    seen = {start}

    walks = []
    if direction in ("down", "both"):
        walks.append(("down", get_downward_chain(start, root, max_depth=depth)))
    if direction in ("up", "both"):
        walks.append(("up", get_upward_chain(start, root, max_depth=depth)))

    # 链里同一个 anchor 可能出现在多条路径上（DAG 不是树）。上下文里重复贴源码
    # 没有意义，所以去重；但重复了几处要报出来，否则"70 个"和"81 条"对不上。
    raw, repeats = 0, 0
    for name, chain in walks:
        for item in chain or []:
            raw += 1
            anchor_id = item.get("id")
            if not anchor_id or anchor_id in seen:
                repeats += 1
                continue
            seen.add(anchor_id)
            hop = int(item.get("depth") or 1)
            entries.append(_entry(anchor_id, max(1, hop), name))
    stats = {"raw": raw, "repeats": repeats}
    return entry_anchor, entries, stats, 0


def read_sources(entries: list[dict], root: str, context_lines: int = 0) -> None:
    """给每个条目挂上源码。取不到的记下原因，条目照样留在列表里。"""
    from analyzer.anchors import get_anchor
    from api.inspector import get_anchor_source

    for item in entries:
        anchor = get_anchor(item["id"], root)
        if anchor is not None:
            item.setdefault("file", anchor.file)
            item.setdefault("line", anchor.line_start)
            item.setdefault("symbol", anchor.symbol)
            item["callees"] = len(getattr(anchor, "callees", []) or [])
            item["callers"] = len(getattr(anchor, "callers", []) or [])
            item["symbol_type"] = getattr(anchor, "symbol_type", "")
        payload = get_anchor_source(item["id"], root, context=context_lines)
        if payload is None:
            item["source"] = None
            item["error"] = "源码取不到（文件可能已不在索引里）"
            continue
        item["source"] = payload["source"]
        item["line_start"] = payload["line_start"]
        item["line_end"] = payload["line_end"]


def _location(item: dict) -> str:
    file_name = item.get("file") or "?"
    line = item.get("line_start") or item.get("line") or "?"
    return f"{file_name}:{line}"


def render_context(entry_anchor, entries: list[dict], budget: int,
                   direction: str, depth: int, root: str, stats: dict) -> str:
    """组装 markdown。预算按块累加，塞不下的单列一栏。"""
    kept, dropped, used = [], [], 0
    for item in entries:
        block = _render_block(item)
        if item["hop"] == 0 or used + len(block) <= budget:
            kept.append(block)
            used += len(block)
        else:
            dropped.append(item)

    hops = max((item["hop"] for item in entries), default=0)
    repeat_note = ""
    if stats.get("repeats"):
        repeat_note = (f"（另有 {stats['repeats']} 处重复路径已去重："
                       f"同一个 anchor 被多条路走到，贴两遍没有意义）")
    lines = [
        f"# 调用链上下文：{entry_anchor.id}",
        "",
        f"- 目标：`{entry_anchor.id}`",
        f"- 方向：{direction}    深度：{depth}（实际 {hops} 跳）",
        f"- 链上 anchor：{len(entries)} 个{repeat_note}"
        f"    纳入预算：{len(kept)} 个（{used} 字符 / 预算 {budget}）",
        f"- 索引：`{Path(root).resolve() / '.codedendrite'}`",
        "",
        "## 链路",
        "",
        "| 跳 | 方向 | anchor | 位置 | 出入度 |",
        "|---:|---|---|---|---|",
    ]
    for item in entries:
        fan = ""
        if "callees" in item:
            fan = f"{item['callers']}↑ {item['callees']}↓"
        lines.append(
            f"| {item['hop']} | {item['direction']} | `{item['id']}` | "
            f"{_location(item)} | {fan} |"
        )
    lines.extend(["", "## 上下文", ""])
    lines.extend(kept)
    if dropped:
        lines.extend(["## 未纳入（超预算）", ""])
        for item in dropped:
            lines.append(f"- `{item['id']}`  {_location(item)}  第 {item['hop']} 跳")
        lines.append("")
    return "\n".join(lines)


def _render_block(item: dict) -> str:
    """一个 anchor 一节：元信息 + 源码；取不到源码就写明原因。"""
    title = item["id"]
    if item["hop"] == 0:
        title += "   ← 起点"
    head = [f"### [{item['hop']}] `{title}`", ""]
    meta = [f"{_location(item)}"]
    if item.get("symbol_type"):
        meta.append(item["symbol_type"])
    if "callees" in item:
        meta.append(f"调用 {item['callees']} 个 / 被 {item['callers']} 个调用")
    if item["hop"]:
        meta.append(f"经 {item['direction']} 边到达")
    head.append("  ·  ".join(meta))
    head.append("")
    if item.get("source"):
        lang = _fence_language(item.get("file", ""))
        head.extend([f"```{lang}", item["source"], "```", ""])
    else:
        head.extend([f"> {item.get('error', '源码取不到')}", ""])
    return "\n".join(head)


def _fence_language(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".java": "java", ".kt": "kotlin", ".go": "go", ".rs": "rust",
        ".c": "c", ".cc": "cpp", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
        ".rb": "ruby", ".php": "php", ".swift": "swift", ".cs": "csharp",
        ".html": "html", ".sh": "bash", ".sql": "sql",
    }.get(suffix, "")


def cmd_chain_context(symbol: str, root: str = ".", depth: int = DEFAULT_DEPTH,
                      direction: str = "down", budget: int = DEFAULT_BUDGET,
                      output: str = None, context_lines: int = 0) -> int:
    """cdd chain2context 的实现：打链 → 取源码 → 组装上下文。"""
    entry_anchor, entries, stats, code = collect_chain(symbol, root, depth, direction)
    if entry_anchor is None:
        return code
    read_sources(entries, root, context_lines)
    text = render_context(entry_anchor, entries, budget, direction, depth, root, stats)

    if output:
        path = Path(output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        kept = text.count("\n### ")
        print(f"上下文：{path}  （{len(entries)} 个 anchor，{len(text)} 字符，"
              f"纳入 {kept} 个）")
        return 0
    print(text)
    return 0
