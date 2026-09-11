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

def _build_context_summary(symbol: str, project_path: str, profile: str = _DEFAULT_PROFILE) -> str:
    """用 SymbolExpander 生成调用关系摘要。4B 极简，8B 含 signature 和 mro。"""
    try:
        from synth.context_builder.expander import SymbolExpander
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

def _codekeeper_dir(project_path: str) -> Path:
    return Path(project_path) / ".codedendrite"

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
        from relate.api.relations import generate_relations
        from index.api.anchors import generate_all_anchors
        from synth.api.module_tree import generate_module_tree
        generate_all_anchors(root=project_path)
        generate_relations(root=project_path)
        generate_module_tree(root=project_path)
    except Exception:
        pass

def _write_current_target(project_path: str, target: Target):
    p = _codekeeper_dir(project_path) / "current_target.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(target), ensure_ascii=False, indent=2), encoding="utf-8")

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

def get_target(project_path: str) -> Optional[Target]:
    """
    拿当前导航终点的函数代码和问题描述。
    在 start() + jump() 定位完成后调用。

    Returns:
        Target（含 symbol/code/problem/context），或 None（未定位到）
    """
    return _read_current_target(project_path)
