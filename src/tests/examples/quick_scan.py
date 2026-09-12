#!/usr/bin/env python3
"""
快速扫描项目示例
运行方式: python examples/quick_scan.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.CodeDendrite import scan_project, analyze_code


def main():
    # 扫描项目
    print("=" * 60)
    print("扫描项目...")
    print("=" * 60)
    
    target_project = "./tools/CodeDendrite"  # 替换成你的项目路径
    result = scan_project(target_project)
    
    print(f"总文件数: {result.total_files}")
    print(f"扫描文件: {result.scanned_files}")
    print(f"跳过文件: {result.skipped_files}")
    print(f"语言分布: {result.languages}")
    print(f"类数量: {result.classes_count}")
    print(f"函数数量: {result.functions_count}")
    print(f"锚点数: {result.anchors_count}")
    
    # 分析核心文件
    print("\n" + "=" * 60)
    print("分析核心文件...")
    print("=" * 60)
    
    core_files = [
        "smartAnalyzer/smart_analyzer.py",
        "smartAnalyzer/orchestrator.py",
    ]
    
    for file_path in core_files:
        full_path = Path(target_project) / file_path
        if full_path.exists():
            print(f"\n分析 {file_path}...")
            analysis = analyze_code(str(full_path))
            
            if hasattr(analysis, 'functions'):
                funcs = [f.name for f in analysis.functions[:5]]
                print(f"  函数 (前5个): {funcs}")
            
            if hasattr(analysis, 'classes'):
                classes = [c.name for c in analysis.classes]
                print(f"  类: {classes}")


if __name__ == "__main__":
    main()
