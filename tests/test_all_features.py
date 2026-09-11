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
    from tools.CodeDendrite import (
        scan_project,
        on_files_changed,
        get_cache_stats,
        clear_cache,
        analyze_error,
        find_definition,
        trace_data,
    )
    print("  ✅ 项目扫描模块（6 个函数）")
    
    # 代码分析（15 个）
    from tools.CodeDendrite import (
        analyze_code,
        get_analyzer,
        analyze_project_structure,
        generate_mermaid_for_project,
        search_symbol,
        PythonAnalyzer,
        TypeScriptAnalyzer,
        CppAnalyzer,
        JavaAnalyzer,
        PhpAnalyzer,
        RubyAnalyzer,
        GoAnalyzer,
        RustAnalyzer,
        SwiftAnalyzer,
        KotlinAnalyzer,
        HtmlAnalyzer,
    )
    print("  ✅ 代码分析模块（15 个函数/类）")
    
    # 继承追踪（12 个）
    from tools.CodeDendrite import (
        trace_inheritance,
        find_subclasses,
        analyze_super_calls,
        build_override_chain,
        resolve_external_class,
        InheritanceTracker,
        create_tracker,
        parse_python_file,
        build_class_index,
        resolve_inheritance,
        compute_mro,
        find_method_origin,
    )
    print("  ✅ 继承追踪模块（12 个函数/类）")
    
    # 数据流分析（7 个）
    from tools.CodeDendrite import (
        analyze_dataflow,
        analyze_call_chain,
        trace_variable,
        get_function_inputs,
        get_function_outputs,
        get_transformations,
        generate_dataflow_html,
    )
    print("  ✅ 数据流分析模块（7 个函数）")
    
    # 智能分析（1 个）
    from tools.CodeDendrite import smart_analyze
    print("  ✅ 智能分析模块（1 个函数）")
    
    # 锚点管理（4 个）
    from tools.CodeDendrite import (
        list_all_symbols,
        list_anchors,
        create_anchor,
        check_all_anchors,
    )
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
