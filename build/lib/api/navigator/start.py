"""
navigator.py — 小模型导航接口
================================
设计原则：工具链做侦探，小模型做外科医生。
- 工具链负责导航到目标函数
- 每步返回明确的 next 坐标，小模型直接跳
- 小模型只在函数级做判断和修复

五个核心函数：
    start(...)       → 从报错启动导航链
    jump(...)        → 执行一跳
    get_target(...)  → 拿到目标函数，准备修
    done(...)        → 标记解决
    escalate(...)    → 解决不了，上报

profile 参数控制输出详细度：
    "4b"  → 极简，每步 <100 tokens，recovery 2 个
    "8b"  → 标准，signal 含 why，context 多 3 行，recovery 3 个（默认）

返回结构固定：
    Step:   status(ok/warn/dead_end) + signal + next + recovery
    Target: symbol + code + problem + context
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# 确保当前目录在路径里
_HERE = Path(__file__).parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# ─── 数据结构 ──────────────────────────────────────────────────────────────────

PROFILE_4B = "4b"
PROFILE_8B = "8b"
_DEFAULT_PROFILE = PROFILE_8B

from api.navigator.target import Step, Target, _read_current_target, _refresh, _write_log
from api.navigator.jump import jump

def start(
    project_path: str,
    error_msg: str,
    file_path: str = None,
    entry_symbol: str = None,
    refresh: bool = True,
    profile: str = _DEFAULT_PROFILE,
) -> Step:
    """
    从报错启动导航链。
    会刷新索引，调用 locate_bug() 定位最可疑函数，返回第一跳坐标。

    Args:
        project_path:  项目根目录
        error_msg:     报错信息（traceback / 描述均可）
        file_path:     报错文件（可选，有更准）
        entry_symbol:  已知入口函数（可选，如 "ClassName.method"）
        refresh:       是否先刷新索引（建议 True）
        profile:       "4b" 极简输出 / "8b" 标准输出（含 why/context/多 recovery）

    Returns:
        Step，status=ok 时 next 字段是第一跳坐标
    """
    if refresh:
        _refresh(project_path)

    try:
        from usage.workflow import locate_bug
        result = locate_bug(
            error_msg=error_msg,
            file_path=file_path or "",
            root=project_path,
            entry_symbol=entry_symbol,
            refresh=False,
            limit=3,
        )

        suspects = result.get("suspects", [])
        _recovery_limit = 2 if profile == PROFILE_4B else 3

        if not suspects:
            top_module = result.get("top_module")
            if top_module:
                module_id = top_module.get("id", "")
                recovery = ["map::full", "anchors::{}".format(file_path or "")]
                if profile == PROFILE_8B:
                    recovery.append("refresh::{}".format(project_path))
                return Step(
                    status="warn",
                    signal="函数级定位失败，最相关模块: {}".format(top_module.get("name", module_id)),
                    next="modules::{}".format(module_id),
                    recovery=recovery[:_recovery_limit],
                    profile=profile,
                )
            return Step(
                status="dead_end",
                signal="locate_bug 未找到嫌疑函数，索引可能为空",
                recovery=["refresh::{}".format(project_path), "map::full"][:_recovery_limit],
                profile=profile,
            )

        top = suspects[0]
        symbol = top.get("symbol", "")
        score = top.get("score", 0)
        reasons = top.get("reasons", [])

        _write_log(project_path, {
            "action": "start",
            "error": error_msg[:200],
            "top_suspect": symbol,
            "score": score,
            "reasons": reasons,
            "profile": profile,
        })

        if profile == PROFILE_4B:
            signal = "最可疑: {} (score={})".format(symbol, score)
        else:
            # 8B: 给出 why，列出 top-3 嫌疑
            why = reasons[0] if reasons else "no reason"
            others = [s.get("symbol", "") for s in suspects[1:3]]
            signal = "最可疑: {} (score={}, why: {})".format(symbol, score, why)
            if others:
                signal += "  其他候选: {}".format(", ".join(others))

        # 用全格式 ID，避免 expand_node 在 relations 里找不到短名节点
        try:
            from analyzer.anchors import get_anchor as _ga
            _a = _ga(symbol, root=project_path)
            expand_id = _a.id if _a else symbol
        except Exception:
            expand_id = symbol

        return Step(
            status="ok",
            signal=signal,
            next="expand::{}".format(expand_id),
            profile=profile,
        )

    except Exception as e:
        return Step(
            status="dead_end",
            signal="start 失败: {}".format(str(e)),
            recovery=["refresh::{}".format(project_path), "map::full"],
            profile=profile,
        )

def navigate(
    project_path: str = None,
    error_msg: str = "",
    file_path: str = None,
    profile: str = _DEFAULT_PROFILE,
    max_steps: int = 12,
) -> Optional[Target]:
    """
    一步导航：从报错直达目标函数。
    内部执行 start() + jump() 循环，处理所有状态转换。

    Args:
        project_path: 项目根目录，None 或 "." → 当前工作目录
        error_msg:    报错信息（traceback / 描述均可）；省略时只刷新索引
        file_path:    报错文件（可选，有更准）
        profile:      "4b" 极简 / "8b" 标准（默认）
        max_steps:    最大跳数，防止死循环

    Returns:
        Target（直接可用），或 None（导航失败 / 无 error_msg 时只刷新索引）
    """
    if not project_path or project_path == ".":
        project_path = str(Path.cwd())
    else:
        project_path = str(Path(project_path).resolve())

    if not error_msg:
        _refresh(project_path)
        return None

    # 覆盖检查：file_path 指定时，确认索引里有该文件的 anchor
    # 没有 → 索引未覆盖，后续结果不可信，提前返回带警告的 Target
    if file_path:
        try:
            from analyzer.anchors import load_anchors
            anchors = load_anchors(project_path)
            norm = file_path.replace("\\", "/")
            covered = any(norm in str(k).replace("\\", "/") for k in anchors)
            if not covered:
                _write_log(project_path, {
                    "action": "navigate_warn",
                    "reason": "file_path not in index",
                    "file_path": file_path,
                    "hint": "add to [include] in .codekeeper_ignore, then re-run --update",
                })
                return Target(
                    symbol="UNCOVERED::" + file_path,
                    file=file_path,
                    line_start=0,
                    line_end=0,
                    code="",
                    problem="[索引未覆盖] {} 不在索引里，导航结果不可信。\n"
                            "检查 .codekeeper_ignore 的 [include] 列表，加入该目录后重新 --update。".format(file_path),
                    context="",
                    profile=profile,
                )
        except Exception:
            pass

    step = start(project_path, error_msg=error_msg, file_path=file_path, profile=profile)

    for _ in range(max_steps):
        # locate 完成：warn + next=None 是终点信号
        if step.status == "warn" and not step.next:
            return _read_current_target(project_path)

        if step.status == "dead_end":
            next_step = None
            for coord in step.recovery:
                r = jump(coord, project_path, profile=profile)
                if r.status == "warn" and not r.next:
                    # locate 在 recovery 里完成了
                    return _read_current_target(project_path)
                if r.status != "dead_end" and r.next:
                    # 得到一个真正可以继续走的 next
                    next_step = r
                    break
                # ok-but-no-next（如 refresh）不算真正 recovery，继续试下一个
            if next_step is None:
                return None
            step = next_step
            continue

        # ok 或 warn-with-next：继续跳
        if not step.next:
            return _read_current_target(project_path)

        step = jump(step.next, project_path, profile=profile)

    # 超过步数，返回当前 target（如有）
    return _read_current_target(project_path)

def step_to_str(step: Step) -> str:
    """把 Step 格式化成小模型容易理解的提示。profile 影响详细度。"""
    is_4b = step.profile == PROFILE_4B
    if step.status == "ok":
        nxt = step.next or "get_target()"
        if is_4b:
            return "[OK] {} → {}".format(step.signal, nxt)
        else:
            return "[OK] {}\n→ next: {}".format(step.signal, nxt)
    elif step.status == "warn":
        if is_4b:
            return "[WARN] {}".format(step.signal)
        else:
            return "[WARN] {}\n→ 停止跳跃，把此信息告诉用户，然后调用 get_target()".format(step.signal)
    else:
        rec_limit = 2 if is_4b else 3
        rec = "\n  ".join(step.recovery[:rec_limit]) if step.recovery else "none"
        if is_4b:
            return "[DEAD_END] {} | try: {}".format(step.signal, " | ".join(step.recovery[:2]))
        else:
            return "[DEAD_END] {}\n→ 按顺序尝试:\n  {}".format(step.signal, rec)

def target_to_str(target: Target) -> str:
    """把 Target 格式化成小模型的工作上下文。profile 影响 context 详细度。"""
    is_4b = target.profile == PROFILE_4B
    d = asdict(target)
    if is_4b:
        # 极简：省略 profile 字段，context 截断到 100 字符
        ctx = d["context"][:100] + "..." if len(d["context"]) > 100 else d["context"]
        return (
            "## {symbol}\n"
            "File: {file} L{line_start}-{line_end}\n"
            "Ctx: {ctx}\n"
            "Problem: {problem}\n\n"
            "```python\n{code}\n```"
        ).format(ctx=ctx, **d)
    else:
        return (
            "## Target: {symbol}\n"
            "File: {file} L{line_start}-{line_end}\n"
            "Context: {context}\n"
            "Problem: {problem}\n\n"
            "```python\n{code}\n```"
        ).format(**d)
