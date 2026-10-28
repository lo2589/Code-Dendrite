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

from usage.navigator.target import Step, Target, _build_context_summary, _codekeeper_dir, _extract_code, _read_current_target, _refresh, _write_current_target, _write_log, done, escalate, get_target
from usage.navigator.jump import jump
from usage.navigator.start import start, navigate, step_to_str, target_to_str

__all__ = ['Step', 'Target', '_build_context_summary', '_codekeeper_dir', '_extract_code', '_read_current_target', '_refresh', '_write_current_target', '_write_log', 'done', 'escalate', 'get_target', 'jump', 'start', 'navigate', 'step_to_str', 'target_to_str']
