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
from index.codeTree.anchor_engine_v2 import (
    Anchor, check_drift_v2 as check_drift, compute_hash_v2 as compute_hash,
    _load_db, _save_db,
    _extract_symbol_source_v2 as _extract_symbol_source,
)


# ─────────────────────────────────────────────
# Git helpers
# ─────────────────────────────────────────────

from synth.codeTree.deep_drift.list_all_symbols import AnchorDriftDetail, _build_action_items, _generate_narrative, _render_markdown, fuzzy_find_symbol, git_diff_file, git_log_files, git_show_deleted

def deep_drift_report(
    root: str = ".",
    since: str = "HEAD",
    llm_model: Optional[str] = None,   # 如果提供，用 AI 生成叙述
    output_md: Optional[str] = None,   # 输出 Markdown 报告路径
) -> dict:
    """
    大幅改动后的全局漂移分析。

    Args:
        root:       项目根目录
        since:      对比的 git ref，默认 HEAD（未提交的变化）
                    用 "HEAD~3" 可以看最近3个commit的变动
        llm_model:  可选，用于生成叙述的模型（格式同 patrol.py）
        output_md:  可选，输出 Markdown 报告路径

    Returns:
        完整分析报告 dict，含：
        - stale_details:    stale 锚点的详细 diff
        - missing_details:  missing 锚点 + fuzzy 候选
        - narrative:        AI 生成的整体变更叙述（若提供 llm_model）
        - action_items:     建议的下一步操作列表
        - markdown:         完整 Markdown 报告字符串
    """
    rp = Path(root)
    db = _load_db(rp)

    print(f"\n🔬 Deep drift analysis (since {since})...")

    # Step 1: 基础 drift 检测
    drift = check_drift(root=root)
    stale_items = drift["stale"]
    missing_items = drift["missing"]

    print(f"   Found {len(stale_items)} stale, {len(missing_items)} missing")

    # Step 2: 丰富每个 stale 锚点的信息
    stale_details: list[AnchorDriftDetail] = []
    for item in stale_items:
        aid = item["anchor_id"]
        anchor = Anchor(**db[aid]) if aid in db else None
        if not anchor:
            continue
        diff_text = git_diff_file(anchor.file, root, since)
        stale_details.append(AnchorDriftDetail(
            anchor_id=aid,
            file=anchor.file,
            symbol=anchor.symbol,
            description=anchor.description,
            status="stale",
            diff=diff_text,
            candidates=[],
            old_source=None,
        ))

    # Step 3: 丰富 missing 锚点 — fuzzy 找候选
    missing_details: list[AnchorDriftDetail] = []
    for item in missing_items:
        aid = item["anchor_id"]
        anchor = Anchor(**db[aid]) if aid in db else None
        if not anchor:
            continue

        candidates = []
        old_source = None

        if anchor.symbol:
            # 符号消失了 → 模糊找
            candidates = fuzzy_find_symbol(anchor.symbol, anchor.file, root)
            # 尝试从 git 拿旧代码
            old_content = git_show_deleted(anchor.file, root)
            if old_content:
                lines = old_content.splitlines()
                # 简单搜索 symbol 名字所在行
                for i, line in enumerate(lines):
                    if f"def {anchor.symbol.split('.')[-1]}" in line or f"class {anchor.symbol.split('.')[-1]}" in line:
                        end = min(i + 30, len(lines))
                        old_source = "\n".join(lines[i:end])
                        break
        else:
            # 整个文件消失了
            old_source = git_show_deleted(anchor.file, root)
            if not old_source:
                old_source = "(file content not recoverable from git)"

        diff_text = git_diff_file(anchor.file, root, since)

        missing_details.append(AnchorDriftDetail(
            anchor_id=aid,
            file=anchor.file,
            symbol=anchor.symbol,
            description=anchor.description,
            status=item["status"],
            diff=diff_text,
            candidates=candidates,
            old_source=old_source,
        ))

    # Step 4: 可选 — AI 生成整体叙述
    narrative = ""
    if llm_model and (stale_details or missing_details):
        narrative = _generate_narrative(stale_details, missing_details, llm_model, root, since)

    # Step 5: 生成 action items
    action_items = _build_action_items(stale_details, missing_details)

    # Step 6: 生成 Markdown 报告
    md = _render_markdown(stale_details, missing_details, narrative, action_items, since)

    if output_md:
        Path(output_md).write_text(md, encoding="utf-8")
        print(f"   📄 Report written to {output_md}")

    print(f"   ✅ Deep analysis done\n")

    return {
        "stale_details": [vars(d) for d in stale_details],
        "missing_details": [vars(d) for d in missing_details],
        "narrative": narrative,
        "action_items": action_items,
        "markdown": md,
        "changed_files": git_log_files(root, since),
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deep drift analysis after large refactors")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--since", default="HEAD", help="Git ref to compare against (e.g. HEAD~3, main)")
    parser.add_argument("--model", default=None, help="LLM for narrative (e.g. ollama/qwen2.5-coder:7b)")
    parser.add_argument("--out", default="drift_report.md", help="Output markdown path")
    args = parser.parse_args()

    result = deep_drift_report(
        root=args.root,
        since=args.since,
        llm_model=args.model,
        output_md=args.out,
    )
    print(result["markdown"])
