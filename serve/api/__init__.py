"""
CodeDendrite 公开 API 层
=====================
所有对外接口统一在此导出，与源码实现完全解耦。

使用方式:
    from serve.api import scan_project, analyze_code, search_symbol
"""

# ─── 项目扫描 (7 个) ───
from index.api.scanning import (
    scan_project,
    on_files_changed,
    analyze_error,
    find_definition,
    trace_data,
    get_cache_stats,
    clear_cache,
)

# ─── 代码分析 (15 个) ───
from serve.api.analysis import (
    analyze_code,
    search_symbol,
    get_analyzer,
    analyze_project_structure,
    generate_mermaid_for_project,
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

# ─── 继承追踪 (12 个) ───
from serve.api.inheritance_api import (
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

# ─── 数据流分析 (7 个) ───
from serve.api.dataflow_api import (
    analyze_dataflow,
    analyze_call_chain,
    trace_variable,
    get_function_inputs,
    get_function_outputs,
    get_transformations,
    generate_dataflow_html,
)

# ─── 智能分析 (1 个) ───
from serve.api.smart import smart_analyze

# ─── 工作流 (2 个) ───
from serve.api.workflow import (
    debug_workflow,
    locate_bug,
    diagnose_bug,
    plan_fix,
    verify_fix,
    run_debug_loop,
)

# ─── 锚点管理 (8 个) ───
from index.api.anchors import (
    list_all_symbols,
    list_anchors,
    create_anchor,
    check_all_anchors,
    generate_all_anchors,
    update_anchors_for_files,
    load_anchors,
    get_anchor,
    filter_anchors_by_file,
)

# ─── 关系图 (6 个) ───
from relate.api.relations import (
    generate_relations,
    load_relations,
    get_node_edges,
    expand_node,
    filter_edges_by_keyword,
    count_edge_types,
)

# ─── 导航链 (7 个，小模型接口) ────────
from serve.api.navigator import (
    Step,
    Target,
    start,
    jump,
    get_target,
    done,
    escalate,
)

# ─── 模块树 (2 个) ─────────────────
from synth.api.module_tree import (
    generate_module_tree,
    load_module_tree,
    get_module,
    find_module_for_symbol,
    query_modules,
    generate_module_summary,
    load_summary_cache,
)


__all__ = [
    # 项目扫描 (7)
    'scan_project', 'on_files_changed', 'analyze_error',
    'find_definition', 'trace_data', 'get_cache_stats', 'clear_cache',
    # 代码分析 (15)
    'analyze_code', 'search_symbol', 'get_analyzer',
    'analyze_project_structure', 'generate_mermaid_for_project',
    'PythonAnalyzer', 'TypeScriptAnalyzer', 'CppAnalyzer',
    'JavaAnalyzer', 'PhpAnalyzer', 'RubyAnalyzer',
    'GoAnalyzer', 'RustAnalyzer', 'SwiftAnalyzer',
    'KotlinAnalyzer', 'HtmlAnalyzer',
    # 继承追踪 (12)
    'trace_inheritance', 'find_subclasses', 'analyze_super_calls',
    'build_override_chain', 'resolve_external_class',
    'InheritanceTracker', 'create_tracker', 'parse_python_file',
    'build_class_index', 'resolve_inheritance', 'compute_mro', 'find_method_origin',
    # 数据流 (7)
    'analyze_dataflow', 'analyze_call_chain', 'trace_variable',
    'get_function_inputs', 'get_function_outputs', 'get_transformations',
    'generate_dataflow_html',
    # 智能分析 (1)
    'smart_analyze',
    # 工作流 (2)
    'debug_workflow', 'locate_bug', 'diagnose_bug', 'plan_fix', 'verify_fix', 'run_debug_loop',
    # 锚点管理 (8)
    'list_all_symbols', 'list_anchors', 'create_anchor',
    'check_all_anchors', 'generate_all_anchors', 'update_anchors_for_files',
    'load_anchors', 'get_anchor', 'filter_anchors_by_file',
    # 关系图 (6)
    'generate_relations', 'load_relations', 'get_node_edges', 'expand_node',
    'filter_edges_by_keyword', 'count_edge_types',
    # 模块树 (2)
    'generate_module_tree', 'load_module_tree', 'get_module', 'find_module_for_symbol',
    'query_modules', 'generate_module_summary', 'load_summary_cache',
    # 导航链 (7)
    'Step', 'Target', 'start', 'jump', 'get_target', 'done', 'escalate',
]
