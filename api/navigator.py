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


@dataclass
class Step:
    """
    每跳的返回结构。
    小模型只需认识三个状态：
        ok       → 执行 next 字段，继续跳
        warn     → 停下来，把 signal 告诉用户
        dead_end → 按 recovery 列表逐个试，全失败再上报
    """
    status: str                          # "ok" | "warn" | "dead_end"
    signal: str                          # 人读的一句话
    next: Optional[str] = None           # 下一跳坐标，格式见 jump()
    recovery: List[str] = field(default_factory=list)  # dead_end 时的自救选项
    profile: str = _DEFAULT_PROFILE      # "4b" | "8b"，影响 step_to_str 输出


@dataclass
class Target:
    """
    导航终点：目标函数的完整上下文。
    小模型拿到这个就可以直接开始分析/修复。
    """
    symbol: str          # "file.py::ClassName.method"
    code: str            # 函数源码
    problem: str         # 工具链推断出的问题描述
    context: str         # 调用者/被调用者摘要（压缩过的）
    file: str = ""
    line_start: int = 0
    line_end: int = 0
    profile: str = _DEFAULT_PROFILE      # 跟随 start() 的 profile


# ─── 内部工具 ──────────────────────────────────────────────────────────────────

def _codekeeper_dir(project_path: str) -> Path:
    return Path(project_path) / ".codedendrite"


def _write_log(project_path: str, entry: dict):
    log_path = _codekeeper_dir(project_path) / "navigation_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = []
    if log_path.exists():
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            log = []
    log.append({**entry, "ts": datetime.now().isoformat()})
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_current_target(project_path: str, target: Target):
    p = _codekeeper_dir(project_path) / "current_target.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(target), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_current_target(project_path: str) -> Optional[Target]:
    p = _codekeeper_dir(project_path) / "current_target.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return Target(**d)
    except Exception:
        return None


def _refresh(project_path: str):
    """增量刷新索引（anchors + relations + module tree）"""
    try:
        from api.relations import generate_relations
        from api.anchors import generate_all_anchors
        from api.module_tree import generate_module_tree
        generate_all_anchors(root=project_path)
        generate_relations(root=project_path)
        generate_module_tree(root=project_path)
    except Exception:
        pass


def _extract_code(file: str, line_start: int, line_end: int, project_path: str) -> str:
    """从文件提取源码片段"""
    try:
        abs_path = file if os.path.isabs(file) else str(Path(project_path) / file)
        lines = Path(abs_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        lo = max(0, line_start - 1)
        hi = min(len(lines), line_end if line_end else line_start + 40)
        return "\n".join(lines[lo:hi])
    except Exception:
        return ""


def _build_context_summary(symbol: str, project_path: str, profile: str = _DEFAULT_PROFILE) -> str:
    """用 SymbolExpander 生成调用关系摘要。4B 极简，8B 含 signature 和 mro。"""
    try:
        from context_builder.expander import SymbolExpander
        ex = SymbolExpander(project_path)
        full = ex.expand_with_relations("anchor://{}".format(symbol), radius=1)

        if profile == PROFILE_4B:
            # 4B: 只列名字，最多各 2 个
            callers = full.get("callers", [])[:2]
            callees = full.get("callees", [])[:2]
            parts = []
            if callers:
                parts.append("callers: " + ", ".join(str(c) for c in callers))
            if callees:
                parts.append("callees: " + ", ".join(str(c) for c in callees))
            return " | ".join(parts) if parts else "no relations"
        else:
            # 8B: 多给 signature、mro、dispatch
            callers = full.get("callers", [])[:3]
            callees = full.get("callees", [])[:3]
            mro = full.get("mro", [])
            dispatch = full.get("dispatch_targets", [])[:2]
            parts = []
            if callers:
                parts.append("callers: " + ", ".join(str(c) for c in callers))
            if callees:
                parts.append("callees: " + ", ".join(str(c) for c in callees))
            if mro:
                parts.append("mro: " + " → ".join(str(m) for m in mro[:5]))
            if dispatch:
                parts.append("dispatch: " + ", ".join(str(d) for d in dispatch))
            return " | ".join(parts) if parts else "no relations"
    except Exception:
        return "context unavailable"


# ─── 五个核心函数 ──────────────────────────────────────────────────────────────

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
        from api.workflow import locate_bug
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
            from api.anchors import get_anchor as _ga
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
                    from api.anchors import get_anchor as _ga
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
            from api.anchors import get_anchor
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
            from api.module_tree import query_modules, get_module
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
            from api.anchors import filter_anchors_by_file, list_anchors
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
            from context_builder.builder import ContextBuilder
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
            from api.anchors import load_anchors
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


def get_target(project_path: str) -> Optional[Target]:
    """
    拿当前导航终点的函数代码和问题描述。
    在 start() + jump() 定位完成后调用。

    Returns:
        Target（含 symbol/code/problem/context），或 None（未定位到）
    """
    return _read_current_target(project_path)


def done(
    project_path: str,
    symbol: str,
    summary: str,
) -> None:
    """
    标记问题已解决。
    把解决方案写入 navigation_log.json，供后续回溯。

    Args:
        project_path: 项目根目录
        symbol:       已修复的函数（"file.py::func"）
        summary:      改了什么，一句话
    """
    _write_log(project_path, {
        "action": "done",
        "symbol": symbol,
        "summary": summary,
    })


def escalate(
    project_path: str,
    symbol: str,
    reason: str,
    tried: List[str] = None,
) -> None:
    """
    解决不了，上报。
    把卡住的位置和已尝试的方法写入 log，给用户看。

    Args:
        project_path: 项目根目录
        symbol:       卡住的函数
        reason:       卡在哪了
        tried:        已经试过什么（list of str）
    """
    _write_log(project_path, {
        "action": "escalate",
        "symbol": symbol,
        "reason": reason,
        "tried": tried or [],
    })


# ─── 便捷：把 Step/Target 转成小模型友好的字符串 ────────────────────────────────

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
