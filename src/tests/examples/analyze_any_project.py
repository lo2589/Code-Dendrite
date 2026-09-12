#!/usr/bin/env python3
"""
任意目录使用 CodeDendrite 示例
==========================

这个脚本可以在 ANY 目录下运行，不需要 cd 到特定位置！

运行方式：
    # 在任意目录运行
    cd /tmp
    python /path/to/this_script.py
    
    # 或者直接指定 Python 路径
    python3 analyze_any_project.py
"""

import sys
from pathlib import Path

# ═══════════════════════════════════════════════════════════
# 第 1 步：添加 CodeDendrite 到 sys.path
# ═══════════════════════════════════════════════════════════

# 方法 1：如果 CodeDendrite 在你的项目里
codedendrite_path = Path("/path/to/CodeDendrite")
if codedendrite_path.exists():
    sys.path.insert(0, str(codedendrite_path))
else:
    # 方法 2：通过环境变量指定
    import os
    if "CODEDENDRITE_PATH" in os.environ:
        sys.path.insert(0, os.environ["CODEDENDRITE_PATH"])
    else:
        print("❌ 错误：找不到 CodeDendrite！")
        print("请设置环境变量 CODEDENDRITE_PATH 或修改脚本中的 codedendrite_path")
        sys.exit(1)

# ═══════════════════════════════════════════════════════════
# 第 2 步：导入功能
# ═══════════════════════════════════════════════════════════

from analyzer.anchors import create_anchor, list_all_symbols, list_anchors
from api.analysis import analyze_code, search_symbol
from api.dataflow import analyze_dataflow
from api.inheritance import trace_inheritance
from usage.analyze.smart_analyzer.orchestrator import scan_project

# ═══════════════════════════════════════════════════════════
# 第 3 步：指定要分析的项目（关键！）
# ═══════════════════════════════════════════════════════════

# ✅ 场景 1：分析绝对路径的项目
TARGET_PROJECT = "."

# ✅ 场景 2：分析相对路径的项目（相对于当前工作目录）
# import os
# TARGET_PROJECT = os.path.join(os.getcwd(), "my_project")

# ✅ 场景 3：分析 CodeDendrite 自身（演示用）
# TARGET_PROJECT = str(codedendrite_path / "tools" / "CodeDendrite")

print("=" * 70)
print(f"📂 当前工作目录: {Path.cwd()}")
print(f"🎯 要分析的项目: {TARGET_PROJECT}")
print("=" * 70)

# ═══════════════════════════════════════════════════════════
# 第 4 步：使用各种功能（注意 root 参数！）
# ═══════════════════════════════════════════════════════════

# 功能 1：扫描项目
print("\n🔍 扫描项目...")
result = scan_project(root=TARGET_PROJECT)

print(f"  总文件数: {result.total_files}")
print(f"  扫描文件: {result.scanned_files}")
print(f"  跳过文件: {result.skipped_files}")
print(f"  语言分布: {result.languages}")
print(f"  类数量: {result.classes_count}")
print(f"  函数数量: {result.functions_count}")
print(f"  锚点数: {result.anchors_count}")

# 功能 2：分析单个文件
print("\n📄 分析单个文件...")
sample_file = Path(TARGET_PROJECT) / "smartAnalyzer" / "orchestrator.py"
if sample_file.exists():
    analysis = analyze_code(str(sample_file))
    
    if hasattr(analysis, 'functions'):
        print(f"  文件: {sample_file.name}")
        print(f"  函数: {[f.name for f in analysis.functions[:5]]}")
    
    if hasattr(analysis, 'classes'):
        print(f"  类: {[c.name for c in analysis.classes]}")

# 功能 3：搜索符号
print("\n🔎 搜索符号...")
matches = search_symbol("scan_project", root=TARGET_PROJECT)
print(f"  找到 {len(matches) if matches else 0} 个 'scan_project' 的定义")

# 功能 4：列出所有符号
print("\n📋 列出所有符号...")
try:
    all_symbols = list_all_symbols(Path(TARGET_PROJECT))
    print(f"  找到 {len(all_symbols)} 个符号")
    
    # 显示前 5 个
    for sym in all_symbols[:5]:
        print(f"    - {sym['file']}::{sym['symbol']} ({sym['type']}, line {sym['line']})")
except Exception as e:
    print(f"  ⚠️  列出符号失败: {e}")

# 功能 5：查看锚点
print("\n⚓ 查看锚点...")
try:
    anchors = list_anchors(root=TARGET_PROJECT)
    print(f"  已绑定 {len(anchors.get('anchors', []))} 个锚点")
except Exception as e:
    print(f"  ⚠️  查看锚点失败: {e}")

# ═══════════════════════════════════════════════════════════
# 完成！
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("✅ 分析完成！")
print("=" * 70)
print("\n💡 提示：")
print("  - 这个脚本可以在 ANY 目录运行")
print("  - 只需修改 TARGET_PROJECT 变量即可分析不同项目")
print("  - 所有函数都接受 root 参数，指定要分析的项目路径")
