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
    from deep_drift import _list_all_symbols, git_log_files, deep_drift_report
    from code_anchor.anchor_engine_v2 import list_anchors, create_anchor, check_drift_v2
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


def load_config(root: str = ".") -> dict:
    """加载配置文件"""
    config_path = Path(root) / CONFIG_FILE
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return DEFAULT_CONFIG.copy()


def save_config(config: dict, root: str = "."):
    """保存配置文件"""
    config_path = Path(root) / CONFIG_FILE
    config["updated_at"] = datetime.now().isoformat()
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Config saved to {config_path}")


# ─────────────────────────────────────────────
# CLI Commands
# ─────────────────────────────────────────────

def cmd_init(args):
    """初始化配置"""
    config = DEFAULT_CONFIG.copy()
    config["created_at"] = datetime.now().isoformat()
    config["project_root"] = str(Path(args.root).resolve())
    
    if args.core_modules:
        config["core_modules"] = args.core_modules.split(",")
    
    save_config(config, args.root)
    
    print("\n🎉 CodeAnchor initialized!")
    print(f"📁 Project root: {config['project_root']}")
    print(f"📦 Core modules: {', '.join(config['core_modules'])}")
    print(f"\nNext steps:")
    print(f"  1. Run 'anchor-cli check' to scan your code")
    print(f"  2. Run 'anchor-cli coverage' to see unanchored APIs")
    print(f"  3. Run 'anchor-cli schedule --cron \"0 9 * * *\"' for daily auto-check")


def cmd_check(args):
    """执行一次全面检查"""
    if not HAS_CORE:
        print("❌ Error: Core modules not available")
        sys.exit(1)
    
    config = load_config(args.root)
    rp = Path(args.root)
    
    print(f"\n🔍 Starting patrol check...")
    print(f"   Project: {config['project_root']}")
    print(f"   Mode: {config['scan_mode']}")
    print()
    
    # Step 1: 获取所有 symbols
    print("📊 Scanning all symbols...")
    start_time = datetime.now()
    all_symbols = _list_all_symbols(rp)
    scan_time = (datetime.now() - start_time).total_seconds()
    print(f"   ⏱️  Found {len(all_symbols)} symbols in {scan_time*1000:.2f}ms")
    
    # Step 2: 获取已绑定的锚点
    print("\n📋 Loading anchored symbols...")
    anchored_data = list_anchors(root=args.root)
    anchored_keys = {f"{a['file']}::{a['symbol']}" for a in anchored_data["anchors"] if a.get("symbol")}
    print(f"   ✓ Loaded {len(anchored_data['anchors'])} anchors")
    
    # Step 3: 对比分析
    print("\n🔬 Analyzing coverage...")
    unanchored = []
    core_unanchored = []
    
    for s in all_symbols:
        key = f"{s['file']}::{s['symbol']}"
        if key not in anchored_keys:
            unanchored.append(s)
            
            # 判断是否在核心模块
            is_core = any(s["file"].startswith(m) for m in config["core_modules"])
            if is_core:
                core_unanchored.append(s)
    
    # Step 4: 检查结果
    print("\n" + "="*60)
    print("📈 PATROL CHECK RESULTS")
    print("="*60)
    print(f"Total symbols:     {len(all_symbols)}")
    print(f"Anchored:          {len(anchored_data['anchors'])} ✅")
    print(f"Unanchored:        {len(unanchored)} ⚠️")
    print(f"  - Core modules:  {len(core_unanchored)} 🔴")
    print(f"  - Other:         {len(unanchored) - len(core_unanchored)} 🟡")
    print(f"Coverage rate:     {len(anchored_keys)/len(all_symbols)*100:.1f}%")
    print("="*60)
    
    if core_unanchored:
        print("\n🔴 CRITICAL: Unanchored core APIs:")
        for s in core_unanchored[:10]:
            print(f"   - {s['file']}::{s['symbol']} ({s['type']}, line {s['line']})")
        
        if len(core_unanchored) > 10:
            print(f"   ... and {len(core_unanchored) - 10} more")
        
        print("\n💡 Suggestion: Run 'anchor-cli coverage' for detailed report")
    
    # Step 5: Git diff 增量检查（如果是 incremental 模式）
    if config["scan_mode"] == "incremental":
        print("\n🔀 Checking recent Git changes...")
        changed_files = git_log_files(args.root, "HEAD~1")
        if changed_files:
            print(f"   Found {len(changed_files)} changed files since last commit")
            
            # 只检查变动文件中的新 symbols
            changed_py = [f for f in changed_files if f.endswith(".py")]
            if changed_py:
                print(f"   Python files: {', '.join(changed_py[:5])}")
        else:
            print("   No recent changes detected")
    
    # Step 6: 自动生成报告
    if config.get("auto_report", True):
        print("\n📄 Generating report...")
        report_path = generate_report(
            all_symbols=all_symbols,
            anchored=anchored_data["anchors"],
            unanchored=unanchored,
            core_unanchored=core_unanchored,
            config=config,
            root=args.root
        )
        print(f"   ✓ Report saved to {report_path}")
    
    print("\n✅ Patrol check completed!")
    
    # 返回状态码（如果有未绑定的核心 API，返回警告状态）
    if core_unanchored:
        sys.exit(2)  # Warning
    sys.exit(0)  # Success


def cmd_coverage(args):
    """详细的覆盖度分析报告"""
    if not HAS_CORE:
        print("❌ Error: Core modules not available")
        sys.exit(1)
    
    config = load_config(args.root)
    rp = Path(args.root)
    
    # 获取数据
    all_symbols = _list_all_symbols(rp)
    anchored_data = list_anchors(root=args.root)
    anchored_keys = {f"{a['file']}::{a['symbol']}" for a in anchored_data["anchors"] if a.get("symbol")}
    
    # 分类
    unanchored_core = []
    unanchored_other = []
    
    for s in all_symbols:
        key = f"{s['file']}::{s['symbol']}"
        if key not in anchored_keys:
            is_core = any(s["file"].startswith(m) for m in config["core_modules"])
            if is_core:
                unanchored_core.append(s)
            else:
                unanchored_other.append(s)
    
    # 生成 Markdown 报告
    lines = [
        "# CodeAnchor Coverage Report",
        f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
        "",
        "## 📊 Overall Statistics",
        "",
        f"- **Total Symbols**: {len(all_symbols)}",
        f"- **Anchored**: {len(anchored_data['anchors'])}",
        f"- **Unanchored**: {len(unanchored_core) + len(unanchored_other)}",
        f"- **Coverage Rate**: **{len(anchored_keys)/len(all_symbols)*100:.1f}%**",
        "",
    ]
    
    if unanchored_core:
        lines.append("## 🔴 Unanchored Core APIs")
        lines.append("")
        lines.append("| File | Symbol | Type | Line |")
        lines.append("|------|--------|------|------|")
        for s in sorted(unanchored_core, key=lambda x: x["file"])[:50]:
            lines.append(f"| `{s['file']}` | `{s['symbol']}` | {s['type']} | {s['line']} |")
        
        if len(unanchored_core) > 50:
            lines.append(f"\n... and {len(unanchored_core) - 50} more")
        
        lines.append("")
        lines.append("💡 **Recommendation**: Create anchors for these core APIs to maintain documentation consistency.")
        lines.append("")
    
    if unanchored_other:
        lines.append("## 🟡 Other Unanchored Symbols")
        lines.append(f"\nFound {len(unanchored_other)} symbols in non-core modules.\n")
    
    # 输出或保存
    report_text = "\n".join(lines)
    
    if args.output:
        Path(args.output).write_text(report_text, encoding="utf-8")
        print(f"📄 Report saved to {args.output}")
    else:
        print(report_text)


def cmd_diff(args):
    """查看 Git diff 中的变更"""
    if not HAS_CORE:
        print("❌ Error: Core modules not available")
        sys.exit(1)
    
    changed_files = git_log_files(args.root, args.since)
    
    if not changed_files:
        print(f"\nℹ️  No changes since {args.since}")
        return
    
    print(f"\n🔀 Changed files (since {args.since}):")
    print(f"   Total: {len(changed_files)} files\n")
    
    # 只关心 Python 文件
    py_files = [f for f in changed_files if f.endswith(".py")]
    
    if py_files:
        print(f"📝 Python files ({len(py_files)}):")
        for f in py_files[:20]:
            print(f"   - {f}")
        
        if len(py_files) > 20:
            print(f"   ... and {len(py_files) - 20} more")
    else:
        print("   No Python files changed")


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


def cmd_report(args):
    """生成详细报告"""
    if not HAS_CORE:
        print("❌ Error: Core modules not available")
        sys.exit(1)
    
    config = load_config(args.root)
    rp = Path(args.root)
    
    # 获取数据
    all_symbols = _list_all_symbols(rp)
    anchored_data = list_anchors(root=args.root)
    
    # 生成报告
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "project": config["project_root"],
        "statistics": {
            "total_symbols": len(all_symbols),
            "anchored": len(anchored_data["anchors"]),
            "coverage_rate": len(anchored_data["anchors"]) / len(all_symbols) if all_symbols else 0
        },
        "anchors": anchored_data["anchors"],
    }
    
    if args.format == "json":
        output = args.output or "anchor_report.json"
        Path(output).write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        print(f"📄 JSON report saved to {output}")
    
    elif args.format == "markdown":
        cmd_coverage(args)  # 复用 coverage 命令


# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────

def generate_report(all_symbols, anchored, unanchored, core_unanchored, config, root) -> str:
    """生成 Markdown 报告"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = Path(root) / f"anchor_patrol_{timestamp}.md"
    
    lines = [
        "# CodeAnchor Patrol Report",
        f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n",
        "",
        "## Summary",
        "",
        f"- Total Symbols: {len(all_symbols)}",
        f"- Anchored: {len(anchored)}",
        f"- Unanchored: {len(unanchored)}",
        f"  - Core: {len(core_unanchored)}",
        f"  - Other: {len(unanchored) - len(core_unanchored)}",
        f"- Coverage: {len(anchored)/len(all_symbols)*100:.1f}%",
        "",
    ]
    
    if core_unanchored:
        lines.append("## Critical: Unanchored Core APIs")
        lines.append("")
        for s in core_unanchored[:20]:
            lines.append(f"- `{s['file']}::{s['symbol']}` ({s['type']}, line {s['line']})")
        lines.append("")
    
    lines.append("---")
    lines.append("*Report generated by CodeAnchor Auto-Patrol*")
    
    report_text = "\n".join(lines)
    report_path.write_text(report_text, encoding="utf-8")
    return str(report_path)


# ─────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────

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
