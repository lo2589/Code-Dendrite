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

from usage.cli.anchor_cli.load_config import cmd_check, cmd_coverage, cmd_diff, cmd_init, cmd_report, load_config, save_config

def cmd_schedule(args):
    """设置定时任务"""
    config = load_config(args.root)
    
    if args.disable:
        config["schedule"]["enabled"] = False
        config["schedule"]["cron"] = None
        print("⏸️  Auto-patrol disabled")
    elif args.cron:
        config["schedule"]["enabled"] = True
        config["schedule"]["cron"] = args.cron
        print(f"⏰ Auto-patrol scheduled: {args.cron}")
        print(f"\n💡 To activate, run one of these:")
        print(f"   # Using cron (Linux/Mac)")
        print(f"   crontab -e")
        print(f"   # Add: {args.cron} cd {Path(args.root).resolve()} && anchor-cli check >> anchor_patrol.log 2>&1")
        print(f"")
        print(f"   # Using systemd timer (Linux)")
        print(f"   See docs/systemd_timer.md for setup instructions")
    else:
        # 显示当前状态
        if config["schedule"]["enabled"]:
            print(f"⏰ Auto-patrol is enabled")
            print(f"   Schedule: {config['schedule']['cron']}")
            print(f"   Last run: {config['schedule'].get('last_run', 'Never')}")
        else:
            print("⏸️  Auto-patrol is disabled")
            print(f"\n💡 Enable with: anchor-cli schedule --cron \"0 9 * * *\"")
    
    save_config(config, args.root)

def main():
    parser = argparse.ArgumentParser(
        prog="anchor-cli",
        description="CodeAnchor Auto-Patrol CLI - 自动巡回检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  anchor-cli init                    # Initialize configuration
  anchor-cli check                   # Run a patrol check
  anchor-cli coverage -o report.md   # Generate coverage report
  anchor-cli diff --since HEAD~1     # Check recent changes
  anchor-cli schedule --cron "0 9 * * *"  # Daily at 9 AM
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # init 命令
    init_parser = subparsers.add_parser("init", help="Initialize configuration")
    init_parser.add_argument("--root", default=".", help="Project root directory")
    init_parser.add_argument("--core-modules", help="Comma-separated core module paths")
    init_parser.set_defaults(func=cmd_init)
    
    # check 命令
    check_parser = subparsers.add_parser("check", help="Run a full patrol check")
    check_parser.add_argument("--root", default=".", help="Project root directory")
    check_parser.set_defaults(func=cmd_check)
    
    # coverage 命令
    cov_parser = subparsers.add_parser("coverage", help="Generate coverage report")
    cov_parser.add_argument("--root", default=".", help="Project root directory")
    cov_parser.add_argument("-o", "--output", help="Output file path")
    cov_parser.set_defaults(func=cmd_coverage)
    
    # diff 命令
    diff_parser = subparsers.add_parser("diff", help="Check Git diff")
    diff_parser.add_argument("--root", default=".", help="Project root directory")
    diff_parser.add_argument("--since", default="HEAD~1", help="Git ref to compare against")
    diff_parser.set_defaults(func=cmd_diff)
    
    # schedule 命令
    sched_parser = subparsers.add_parser("schedule", help="Configure auto-patrol schedule")
    sched_parser.add_argument("--root", default=".", help="Project root directory")
    sched_parser.add_argument("--cron", help="Cron expression (e.g. '0 9 * * *')")
    sched_parser.add_argument("--disable", action="store_true", help="Disable auto-patrol")
    sched_parser.set_defaults(func=cmd_schedule)
    
    # report 命令
    report_parser = subparsers.add_parser("report", help="Generate detailed report")
    report_parser.add_argument("--root", default=".", help="Project root directory")
    report_parser.add_argument("-o", "--output", help="Output file path")
    report_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    report_parser.set_defaults(func=cmd_report)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()
