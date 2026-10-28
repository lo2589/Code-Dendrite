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

from usage.navigator.target import Step, Target, _build_context_summary, _extract_code, _refresh, _write_current_target, _write_log

def jump(
    coordinate: str,
    project_path: str,
    profile: str = _DEFAULT_PROFILE,
) -> Step:
    """
    执行一跳。coordinate 格式：

        expand::<symbol>          展开节点关系，返回调用者/被调用者
        read::<file>:<line>       读文件片段（line 可选）
        modules::<keyword>        查模块树
        anchors::<keyword>        按关键词查 anchor
        locate::<file>::<symbol>  精确定位到函数，准备 get_target
        map::full                 生成全局模块地图
        refresh::<path>           刷新索引

    当 coordinate 包含足够的函数定位信息时，自动写入 current_target.json。

    Returns:
        Step，status=ok 时 next 是下一跳，dead_end 时带 recovery
    """
    _recovery_limit = 2 if profile == PROFILE_4B else 3

    try:
        parts = coordinate.split("::", 1)
        action = parts[0].strip()
        arg = parts[1].strip() if len(parts) > 1 else ""

        # ── expand ───────────────────────────────────────────────
        if action == "expand":
            from api.relations import expand_node
            graph = expand_node(arg, root=project_path, radius=1)
            edges = graph.get("edges", [])

            if not edges:
                # relations 缺边时，直接从 anchor.callees 找项目内调用
                try:
                    from analyzer.anchors import get_anchor as _ga
                    # arg 可能是全格式 file::symbol，get_anchor 只认 symbol 部分
                    _sym = arg.split("::")[-1] if "::" in arg else arg
                    _anchor = _ga(_sym, root=project_path)
                    if _anchor and _anchor.callees:
                        for callee_name in _anchor.callees:
                            if isinstance(callee_name, dict):
                                callee_name = callee_name.get("target") or callee_name.get("id") or callee_name.get("symbol") or ""
                            callee_anchor = _ga(callee_name, root=project_path)
                            if callee_anchor and not callee_anchor.is_virtual:
                                return Step(
                                    status="ok",
                                    signal="relations 缺边，anchor.callees → {}".format(callee_anchor.symbol),
                                    next="expand::{}".format(callee_anchor.id),
                                    profile=profile,
                                )
                except Exception:
                    pass

                recovery = [
                    "locate::{}".format(arg),
                    "anchors::{}".format(arg.split("::")[0] if "::" in arg else arg),
                    "refresh::{}".format(project_path),
                ]
                return Step(
                    status="dead_end",
                    signal="expand {} 无边且 anchor.callees 无项目内调用".format(arg),
                    recovery=recovery[:_recovery_limit],
                    profile=profile,
                )

            # 找最可疑的被调用者（出边）
            callees = [e for e in edges if e.get("direction") == "out"]
            callers = [e for e in edges if e.get("direction") == "in"]
            dispatch = [e for e in edges if e.get("edge_type") == "dispatch"]

            # 如果有 dispatch 边，优先追 dispatch
            if dispatch:
                next_sym = dispatch[0].get("to_id") or dispatch[0].get("from_id", "")
                if profile == PROFILE_4B:
                    signal = "dispatch → {}".format(next_sym)
                else:
                    signal = "发现 dispatch 边: {} → {}（共 {} 条边）".format(
                        dispatch[0].get("from_id", ""), next_sym, len(edges))
            elif callees:
                next_sym = callees[0].get("to_id", "")
                if profile == PROFILE_4B:
                    signal = "出边 → {}".format(next_sym)
                else:
                    signal = "{} 有 {} 个出边，追最近一个: {}（callers: {}）".format(
                        arg, len(callees), next_sym, len(callers))
            else:
                # 只有入边，说明是叶子节点，可以 locate 了
                signal = "{} 是叶子节点，准备定位".format(arg)
                return Step(
                    status="ok",
                    signal=signal,
                    next="locate::{}".format(arg),
                    profile=profile,
                )

            _write_log(project_path, {"action": "expand", "symbol": arg,
                                       "edges": len(edges), "next": next_sym})
            return Step(status="ok", signal=signal, next="expand::{}".format(next_sym), profile=profile)

        # ── locate ───────────────────────────────────────────────
        elif action == "locate":
            # 精确定位到函数，写入 current_target
            from analyzer.anchors import get_anchor
            symbol = arg
            anchor = get_anchor(symbol, root=project_path)

            if not anchor:
                recovery = [
                    "refresh::{}".format(project_path),
                    "anchors::{}".format(symbol.split("::")[0] if "::" in symbol else symbol),
                ]
                if profile == PROFILE_8B:
                    recovery.append("map::full")
                return Step(
                    status="dead_end",
                    signal="anchor 不存在: {}".format(symbol),
                    recovery=recovery[:_recovery_limit],
                    profile=profile,
                )

            code = _extract_code(anchor.file, anchor.line_start, anchor.line_end, project_path)
            ctx = _build_context_summary(symbol, project_path, profile=profile)

            target = Target(
                symbol=anchor.symbol,
                file=anchor.file,
                line_start=anchor.line_start,
                line_end=anchor.line_end,
                code=code,
                problem="定位到嫌疑函数，请分析并修复",
                context=ctx,
                profile=profile,
            )
            _write_current_target(project_path, target)
            _write_log(project_path, {"action": "locate", "symbol": symbol,
                                       "file": anchor.file, "lines": "{}-{}".format(
                                           anchor.line_start, anchor.line_end)})

            if profile == PROFILE_4B:
                signal = "定位: {} L{}-{}，call get_target()".format(
                    anchor.file, anchor.line_start, anchor.line_end)
            else:
                signal = "已定位: {} ({}:{}-{})，调用 get_target() 拿代码".format(
                    symbol, anchor.file, anchor.line_start, anchor.line_end)

            return Step(
                status="warn",
                signal=signal,
                next=None,  # 链结束，下一步是 get_target()
                profile=profile,
            )

        # ── read ─────────────────────────────────────────────────
        elif action == "read":
            # read::backend/main.py:230  或  read::backend/main.py:230-280
            file_part = arg
            line_hint = 0
            if ":" in arg:
                file_part, line_str = arg.rsplit(":", 1)
                try:
                    if "-" in line_str:
                        lo, hi = line_str.split("-")
                        line_hint = int(lo)
                    else:
                        line_hint = int(line_str)
                except ValueError:
                    line_hint = 0

            code = _extract_code(file_part, line_hint, line_hint + 40, project_path)
            if not code:
                return Step(
                    status="dead_end",
                    signal="读取失败: {}".format(arg),
                    recovery=["anchors::{}".format(file_part)],
                )

            # 读到了，建议用 locate 精确定位
            signal = "读到 {}:{} 附近代码，如需精确定位用 locate::".format(file_part, line_hint)
            return Step(status="ok", signal=signal, next=None)

        # ── modules ──────────────────────────────────────────────
        elif action == "modules":
            from usage.structure.module_tree import query_modules, get_module
            # 可以是 keyword 或 module_id（sm_xxx）
            if arg.startswith("sm_"):
                module = get_module(arg, root=project_path)
                if not module:
                    return Step(
                        status="dead_end",
                        signal="模块 {} 不存在".format(arg),
                        recovery=["map::full"],
                    )
                entries = module.get("entries", [])
                signal = "模块 {}: {}，入口: {}".format(
                    module.get("name", arg),
                    module.get("summary", ""),
                    ", ".join(str(e) for e in entries[:3]),
                )
                next_sym = entries[0] if entries else None
                return Step(
                    status="ok",
                    signal=signal,
                    next="expand::{}".format(next_sym) if next_sym else None,
                )
            else:
                results = query_modules(arg, root=project_path, limit=3)
                if not results:
                    return Step(
                        status="dead_end",
                        signal="没有匹配模块: {}".format(arg),
                        recovery=["map::full"],
                    )
                top = results[0]
                entries = top.get("entries", [])
                signal = "最相关模块: {} — {}".format(top.get("name", ""), top.get("summary", ""))
                next_sym = entries[0] if entries else None
                return Step(
                    status="ok",
                    signal=signal,
                    next="expand::{}".format(next_sym) if next_sym else "modules::{}".format(
                        top.get("id", "")),
                )

        # ── anchors ──────────────────────────────────────────────
        elif action == "anchors":
            from analyzer.anchors import filter_anchors_by_file, list_anchors
            if arg:
                anchors = filter_anchors_by_file(arg, root=project_path)
            else:
                anchors = list_anchors(root=project_path)
            if not anchors:
                return Step(
                    status="dead_end",
                    signal="没有找到 anchors: {}".format(arg),
                    recovery=["refresh::{}".format(project_path)],
                )
            top = anchors[0]
            sym = "{}::{}".format(top.get("file", ""), top.get("symbol", ""))
            signal = "找到 {} 个 anchors，最近: {}".format(len(anchors), sym)
            return Step(status="ok", signal=signal, next="expand::{}".format(sym))

        # ── map ───────────────────────────────────────────────────
        elif action == "map":
            from usage.structure.context_builder.builder import ContextBuilder
            cb = ContextBuilder(project_path)
            budget = 1500 if arg == "full" else 800
            text = cb.build_map(budget_tokens=budget)
            # 找 entries 作为下一跳建议
            import re
            entries = re.findall(r"entries: ([^\n]+)", text)
            first_entry = entries[0].split(",")[0].strip() if entries else None
            signal = "地图生成完毕，建议先看: {}".format(first_entry or "无入口建议")
            return Step(
                status="ok",
                signal=signal,
                next="expand::{}".format(first_entry) if first_entry else None,
            )

        # ── refresh ───────────────────────────────────────────────
        elif action == "refresh":
            path = arg or project_path
            _refresh(path)
            return Step(
                status="ok",
                signal="索引刷新完毕: {}".format(path),
                next=None,
            )

        else:
            return Step(
                status="dead_end",
                signal="未知 action: {}".format(action),
                recovery=["map::full", "anchors::"],
            )

    except Exception as e:
        return Step(
            status="dead_end",
            signal="jump 异常: {}".format(str(e)),
            recovery=[
                "refresh::{}".format(project_path),
                "map::full",
            ],
        )
