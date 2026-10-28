#!/usr/bin/env python3
"""
CodeAnchor Auto-Patrol CLI
--------------------------
自动巡回检查工具 - 定期检查代码变更并生成报告

功能:
1. 全量扫描 - 发现所有 symbols
2. 增量检测 - 基于 Git diff 只检查变动文件
3. 覆盖度分析 - 找出未绑定的核心 API
4. 自动报告 - Markdown/JSON/邮件通知
5. 定时任务 - cron/systemd 自动巡检

使用示例:
    # 初始化配置
    anchor-cli init
    
    # 手动执行一次检查
    anchor-cli check
    
    # 查看覆盖度报告
    anchor-cli coverage --core-modules "src,core"
    
    # 设置定时任务 (每天上午 9 点)
    anchor-cli schedule --cron "0 9 * * *"
    
    # 查看最近的变更
    anchor-cli diff --since HEAD~1
    
    # 导出报告
    anchor-cli report -o weekly_report.md --format markdown
"""

import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────
# 导入现有模块
# ─────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent))

try:
    from analyzer.repair.deep_drift import _list_all_symbols, git_log_files, deep_drift_report
    from analyzer.identity.engine import list_anchors, create_anchor, check_drift_v2
    HAS_CORE = True
except ImportError as e:
    print(f"⚠️  Warning: Cannot import core modules: {e}")
    HAS_CORE = False


# ─────────────────────────────────────────────
# 配置文件管理
# ─────────────────────────────────────────────

CONFIG_FILE = ".anchor_config.json"
DEFAULT_CONFIG = {
    "version": "1.0",
    "created_at": "",
    "project_root": ".",
    "core_modules": ["src", "core", "app"],
    "scan_mode": "incremental",  # "full" | "incremental"
    "auto_report": True,
    "report_format": "markdown",  # "markdown" | "json"
    "notify_email": None,
    "schedule": {
        "enabled": False,
        "cron": None,
        "last_run": None
    }
}

from usage.cli.anchor_cli.load_config import load_config, cmd_check, generate_report, cmd_coverage, cmd_diff, save_config, cmd_init, cmd_report
from usage.cli.anchor_cli.cmd_schedule import cmd_schedule, main

__all__ = ['load_config', 'cmd_check', 'generate_report', 'cmd_coverage', 'cmd_diff', 'save_config', 'cmd_init', 'cmd_report', 'cmd_schedule', 'main']
