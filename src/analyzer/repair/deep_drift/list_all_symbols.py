"""
Deep Drift Analyzer
--------------------
专门处理大幅度增删改之后的"找回"问题。

普通 check_drift() 对每个锚点独立检查 → 适合日常小改动
deep_drift_report() 做全局分析 → 适合大重构之后

核心能力：
1. 找出所有 stale/missing 锚点，并附上具体 diff
2. 用智能 AI（一次调用）生成跨文件的变更叙述
3. 对 missing 锚点尝试"模糊匹配"——在现有代码里找最像原来的东西
4. 输出 Markdown 报告，直接可以粘贴进 CLAUDE.md
"""

import ast
import os
import difflib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from analyzer.identity.engine import (
    Anchor, check_drift_v2 as check_drift, compute_hash_v2 as compute_hash,
    _load_db, _save_db,
    _extract_symbol_source_v2 as _extract_symbol_source,
)


# ─────────────────────────────────────────────
# Git helpers
# ─────────────────────────────────────────────

@dataclass
class AnchorDriftDetail:
    anchor_id: str
    file: str
    symbol: Optional[str]
    description: str
    status: str           # "stale" | "missing_file" | "missing_symbol"
    diff: Optional[str]   # git diff 内容
    candidates: list      # fuzzy match 候选（仅 missing 时）
    old_source: Optional[str]  # 删除前的代码（仅 missing 时）

_DEFAULT_EXCLUDE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    'htmlcov', '.tox', '.mypy_cache', '.pytest_cache',
    'dist', 'build', 'egg-info',
}

_NARRATIVE_PROMPT = """\
You are a senior engineer reviewing a large refactor. Below is a summary of
documentation anchors that have drifted since the last stable state.

## Stale anchors (code changed)
{stale_section}

## Missing anchors (file/symbol deleted or renamed)
{missing_section}

## Changed files
{changed_files}

Write a concise technical narrative (3-5 paragraphs) that:
1. Summarises what the refactor appears to have done at a high level
2. Identifies which architectural areas were most affected
3. For each missing anchor, states your best guess about where the functionality moved
4. Lists the highest-risk areas where the documentation is most likely wrong

Write in plain English. Be direct. No bullet points in the narrative itself."""

def _build_action_items(
    stale: list[AnchorDriftDetail],
    missing: list[AnchorDriftDetail],
) -> list[dict]:
    items = []

    for d in stale:
        items.append({
            "priority": "medium",
            "action": "refresh_anchor",
            "anchor_id": d.anchor_id,
            "reason": f"Code changed. Run patrol.py or call refresh_anchor('{d.anchor_id}')",
        })

    for d in missing:
        if d.candidates:
            top = d.candidates[0]
            items.append({
                "priority": "high",
                "action": "rebind_anchor",
                "anchor_id": d.anchor_id,
                "reason": (
                    f"Symbol/file gone. Best candidate: {top['file']}::{top['symbol']} "
                    f"(similarity {top['similarity']}). "
                    f"Run: create_anchor('{d.anchor_id}', '{top['file']}', symbol='{top['symbol']}')"
                ),
                "suggested_rebind": {
                    "file": top["file"],
                    "symbol": top["symbol"],
                },
            })
        else:
            items.append({
                "priority": "high",
                "action": "manual_review",
                "anchor_id": d.anchor_id,
                "reason": f"Symbol/file gone, no candidates found. Functionality may have been deleted or split.",
            })

    return sorted(items, key=lambda x: {"high": 0, "medium": 1}.get(x["priority"], 2))

def git_log_files(root: str, since: str = "HEAD~1") -> list[str]:
    """获取自某个 commit 以来变动过的文件列表。"""
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", since],
            cwd=root, capture_output=True, text=True, timeout=10
        )
        return [f.strip() for f in r.stdout.splitlines() if f.strip()]
    except Exception:
        return []

def _generate_narrative(
    stale: list[AnchorDriftDetail],
    missing: list[AnchorDriftDetail],
    model_spec: str,
    root: str,
    since: str,
) -> str:
    try:
        from patrol import call_llm
    except ImportError:
        return "(patrol.py not found — cannot generate narrative)"

    changed_files = git_log_files(root, since)

    def fmt_stale(d: AnchorDriftDetail) -> str:
        diff_preview = (d.diff or "")[:400].replace("\n", "\n  ")
        return f"- [{d.anchor_id}] {d.file}::{d.symbol or 'file'}\n  was: {d.description}\n  diff:\n  {diff_preview}"

    def fmt_missing(d: AnchorDriftDetail) -> str:
        cands = ", ".join(f"{c['file']}::{c['symbol']} ({c['similarity']})" for c in d.candidates[:3])
        return f"- [{d.anchor_id}] {d.file}::{d.symbol or 'file'}\n  was: {d.description}\n  candidates: {cands or 'none found'}"

    prompt = _NARRATIVE_PROMPT.format(
        stale_section="\n".join(fmt_stale(d) for d in stale) or "(none)",
        missing_section="\n".join(fmt_missing(d) for d in missing) or "(none)",
        changed_files="\n".join(changed_files[:20]) or "(no git info)",
    )

    try:
        return call_llm(prompt, model_spec, max_tokens=800)
    except Exception as e:
        return f"(narrative generation failed: {e})"

def _list_all_symbols(
    root: Path,
    extensions: tuple = (".py",),
    exclude_dirs: "set | None" = None,
) -> list[dict]:
    """遍历项目，提取所有 Python 函数/类名及其位置。
    
    参数:
        root: 项目根目录
        extensions: 要扫描的文件扩展名
        exclude_dirs: 要排除的目录名集合，None 时使用默认排除列表
    """
    skip = exclude_dirs if exclude_dirs is not None else _DEFAULT_EXCLUDE_DIRS
    symbols = []
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fname in filenames:
            p = dp / fname
            if p.suffix not in extensions:
                continue
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except Exception:
            continue
        rel = str(p.relative_to(root))
        # 只处理顶层节点
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                end = getattr(node, 'end_lineno', node.lineno)
                symbols.append({"file": rel, "symbol": node.name, "type": "class", "line": node.lineno, "line_end": end})
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        child_end = getattr(child, 'end_lineno', child.lineno)
                        symbols.append({
                            "file": rel,
                            "symbol": f"{node.name}.{child.name}",
                            "type": "method",
                            "line": child.lineno,
                            "line_end": child_end,
                        })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, 'end_lineno', node.lineno)
                symbols.append({"file": rel, "symbol": node.name, "type": "function", "line": node.lineno, "line_end": end})
    return symbols

def _render_markdown(
    stale: list[AnchorDriftDetail],
    missing: list[AnchorDriftDetail],
    narrative: str,
    action_items: list[dict],
    since: str,
) -> str:
    lines = [
        "# CodeAnchor Deep Drift Report",
        f"\n_Generated after refactor (comparing against `{since}`)_\n",
    ]

    if narrative:
        lines += ["\n## AI 变更叙述\n", narrative, ""]

    lines.append(f"\n## 需要处理的锚点 ({len(stale) + len(missing)} 个)\n")

    if missing:
        lines.append("### ✗ Missing（文件或符号已消失）\n")
        for d in missing:
            lines.append(f"#### `{d.anchor_id}`")
            lines.append(f"- **原路径**: `{d.file}` :: `{d.symbol or 'whole file'}`")
            lines.append(f"- **原描述**: {d.description}")
            if d.candidates:
                lines.append("- **模糊匹配候选**:")
                for c in d.candidates[:3]:
                    lines.append(f"  - `{c['file']}::{c['symbol']}` (相似度 {c['similarity']})")
            if d.old_source:
                lines.append(f"\n<details><summary>原代码片段</summary>\n\n```python\n{d.old_source[:600]}\n```\n</details>")
            lines.append("")

    if stale:
        lines.append("### ⚠ Stale（代码已改变）\n")
        for d in stale:
            lines.append(f"#### `{d.anchor_id}`")
            lines.append(f"- **路径**: `{d.file}` :: `{d.symbol or 'whole file'}`")
            lines.append(f"- **当前描述**: {d.description}")
            if d.diff:
                preview = "\n".join(d.diff.splitlines()[:30])
                lines.append(f"\n<details><summary>Diff 预览</summary>\n\n```diff\n{preview}\n```\n</details>")
            lines.append("")

    lines.append("\n## 行动清单\n")
    for item in action_items:
        priority_icon = "🔴" if item["priority"] == "high" else "🟡"
        lines.append(f"{priority_icon} **[{item['anchor_id']}]** {item['reason']}\n")

    return "\n".join(lines)

def git_show_deleted(file: str, root: str) -> Optional[str]:
    """获取已删除文件在最后一个 commit 时的内容。"""
    try:
        r = subprocess.run(
            ["git", "show", f"HEAD:{file}"],
            cwd=root, capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return r.stdout
        return None
    except Exception:
        return None

def git_diff_file(file: str, root: str, since: str = "HEAD") -> Optional[str]:
    """获取单文件相对于某个 commit 的 diff。"""
    try:
        r = subprocess.run(
            ["git", "diff", since, "--", file],
            cwd=root, capture_output=True, text=True, timeout=15
        )
        return r.stdout.strip() or None
    except Exception:
        return None

def fuzzy_find_symbol(original_symbol: str, original_file: str, root: str) -> list[dict]:
    """
    当锚点的 symbol 消失后，在整个项目里找最相似的候选。
    返回按相似度排序的候选列表（最多5个）。
    """
    rp = Path(root)
    all_symbols = _list_all_symbols(rp)

    # 用 SequenceMatcher 对 symbol 名字做模糊匹配
    scored = []
    for s in all_symbols:
        name_score = difflib.SequenceMatcher(None, original_symbol, s["symbol"]).ratio()
        # 同目录/同文件加分
        file_bonus = 0.15 if Path(s["file"]).parent == Path(original_file).parent else 0
        scored.append((name_score + file_bonus, s))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {**s, "similarity": round(score, 2)}
        for score, s in scored[:5]
        if score > 0.4
    ]
