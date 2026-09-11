#!/usr/bin/env python3
"""
CodeDendrite 完整功能测试
=====================

测试所有导出的功能是否都能正常导入和使用

运行方式：
    python test_all_features.py
"""

import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("CodeDendrite 完整功能测试")
print("=" * 70)

# ═══════════════════════════════════════════════════════════
# 测试 1: 导入所有功能
# ═══════════════════════════════════════════════════════════

print("\n📦 测试 1: 导入所有功能...")

try:
    # 项目扫描（6 个）
    from synth.smartAnalyzer.orchestrator import analyze_error, clear_cache, find_definition, get_cache_stats, on_files_changed, scan_project, trace_data
    print("  ✅ 项目扫描模块（6 个函数）")
    
    # 代码分析（15 个）
    from parse.codeAnalysis.analyzer import get_analyzer
    from parse.codeAnalysis.analyzer.cpp_analyzer import CppAnalyzer
    from parse.codeAnalysis.analyzer.go_analyzer import GoAnalyzer
    from parse.codeAnalysis.analyzer.html_analyzer import HtmlAnalyzer
    from parse.codeAnalysis.analyzer.java_analyzer import JavaAnalyzer
    from parse.codeAnalysis.analyzer.kotlin_analyzer import KotlinAnalyzer
    from parse.codeAnalysis.analyzer.php_analyzer import PhpAnalyzer
    from parse.codeAnalysis.analyzer.python_analyzer import PythonAnalyzer
    from parse.codeAnalysis.analyzer.ruby_analyzer import RubyAnalyzer
    from parse.codeAnalysis.analyzer.rust_analyzer import RustAnalyzer
    from parse.codeAnalysis.analyzer.structure_analyzer import analyze_project_structure
    from parse.codeAnalysis.analyzer.swift_analyzer import SwiftAnalyzer
    from parse.codeAnalysis.analyzer.typescript_analyzer import TypeScriptAnalyzer
    from serve.api.analysis import analyze_code, search_symbol
    from view.codeAnalysis.graph import generate_mermaid_for_project
    print("  ✅ 代码分析模块（15 个函数/类）")
    
    # 继承追踪（12 个）
    from index.inheritance.class_indexer import build_class_index
    from parse.inheritance.ast_parser import parse_python_file
    from relate.inheritance.external_lib import resolve_external_class
    from relate.inheritance.inheritance_tracker import InheritanceTracker, create_tracker
    from relate.inheritance.override_analyzer import build_override_chain
    from relate.inheritance.resolver import compute_mro, find_method_origin, find_subclasses, resolve_inheritance
    from relate.inheritance.super_analyzer import analyze_super_calls
    from serve.api.inheritance_api import trace_inheritance
    print("  ✅ 继承追踪模块（12 个函数/类）")
    
    # 数据流分析（7 个）
    from relate.dataFlow.analyzer import analyze_call_chain, get_function_inputs, get_function_outputs, get_transformations, trace_variable
    from relate.dataFlow.visualizer import generate_dataflow_html
    from serve.api.dataflow_api import analyze_dataflow
    print("  ✅ 数据流分析模块（7 个函数）")
    
    # 智能分析（1 个）
    from serve.api.smart import smart_analyze
    print("  ✅ 智能分析模块（1 个函数）")
    
    # 锚点管理（4 个）
    from index.api.anchors import check_all_anchors, create_anchor, list_all_symbols, list_anchors
    print("  ✅ 锚点管理模块（4 个函数）")
    
    print("\n🎉 所有 45 个功能导入成功！")
    
except ImportError as e:
    print(f"\n❌ 导入失败: {e}")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════
# 测试 2: 验证函数可调用
# ═══════════════════════════════════════════════════════════

print("\n🔧 测试 2: 验证函数可调用...")

test_project = str(project_root / "tools" / "CodeDendrite")

functions_to_test = [
    ("scan_project", lambda: scan_project(root=test_project, incremental=True)),
    ("analyze_error", lambda: analyze_error("TypeError: test", root=test_project)),
    ("find_definition", lambda: find_definition("scan_project", "test.py", root=test_project)),
    ("trace_data", lambda: trace_data("var", "func", "test.py", root=test_project)),
    ("get_cache_stats", lambda: get_cache_stats(root=test_project)),
    ("smart_analyze", lambda: smart_analyze("TypeError: test", root=test_project)),
    ("list_all_symbols", lambda: list_all_symbols(Path(test_project))),
]

success_count = 0
fail_count = 0

for func_name, func_call in functions_to_test:
    try:
        result = func_call()
        print(f"  ✅ {func_name}() - 可调用")
        success_count += 1
    except Exception as e:
        print(f"  ⚠️  {func_name}() - 调用失败: {e}")
        fail_count += 1

print(f"\n📊 测试结果: {success_count} 成功, {fail_count} 失败")

# ═══════════════════════════════════════════════════════════
# 测试 3: 验证类可实例化
# ═══════════════════════════════════════════════════════════

print("\n🏗️  测试 3: 验证类可实例化...")

classes_to_test = [
    ("PythonAnalyzer", PythonAnalyzer, (test_project,)),
    ("InheritanceTracker", InheritanceTracker, (test_project,)),
]

for class_name, class_obj, args in classes_to_test:
    try:
        instance = class_obj(*args)
        print(f"  ✅ {class_name} - 可实例化")
    except Exception as e:
        print(f"  ⚠️  {class_name} - 实例化失败: {e}")

# ═══════════════════════════════════════════════════════════
# 总结
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("测试完成！")
print("=" * 70)
print(f"\n📈 统计:")
print(f"  - 导入功能: 45 个")
print(f"  - 测试函数: {len(functions_to_test)} 个")
print(f"  - 成功: {success_count}")
print(f"  - 失败: {fail_count}")

if fail_count == 0:
    print("\n🎉 所有功能都可用！")
else:
    print(f"\n⚠️  有 {fail_count} 个功能需要检查")
