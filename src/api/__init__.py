"""
CodeDendrite 公开 API 层
=====================
对外的查询面：扫描、分析、继承、数据流、锚点、关系图、导航链。

分层是单向的：scanner → analyzer → api → usage / view。api 只导出它自己和它下面两层
的东西，**不转发上层**。以前这里还转发了 usage 的项目扫描、调试工作流、模块树，以及
view 的 mermaid 画图——下层替上层转发，分层就成了网状（README 只好写「主方向 + 反向
引用」），usage/__init__.py 里还专门躲着 api → view → usage → api 的环。这些转发在
仓库里没有一个调用方。要用它们，直接去上层拿：

    from usage.analyze.smart_analyzer.orchestrator import scan_project, on_files_changed, ...
    from usage.workflow import debug_workflow, locate_bug, diagnose_bug, plan_fix, verify_fix, run_debug_loop
    from usage.structure.module_tree import generate_module_tree, load_module_tree, get_module, ...
    from view.html.graph import generate_mermaid_for_project

使用方式:
    from api import analyze_code, search_symbol, generate_all_anchors
"""

# ─── 代码分析 (14 个) ───
from api.analysis import (
    analyze_code,
    search_symbol,
    get_analyzer,
    analyze_project_structure,
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
from api.inheritance import (
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
from api.dataflow import (
    analyze_dataflow,
    analyze_call_chain,
    trace_variable,
    get_function_inputs,
    get_function_outputs,
    get_transformations,
    generate_dataflow_html,
)

# ─── 智能分析 (1 个) ───
from api.smart import smart_analyze

# ─── 锚点管理 (9 个) ───
from analyzer.anchors import (
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
from api.relations import (
    generate_relations,
    load_relations,
    get_node_edges,
    expand_node,
    filter_edges_by_keyword,
    count_edge_types,
)

# ─── 导航链 (7 个，小模型接口) ────────
from api.navigator import (
    Step,
    Target,
    start,
    jump,
    get_target,
    done,
    escalate,
)


__all__ = [
    # 代码分析 (14)
    'analyze_code', 'search_symbol', 'get_analyzer', 'analyze_project_structure',
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
    # 锚点管理 (9)
    'list_all_symbols', 'list_anchors', 'create_anchor',
    'check_all_anchors', 'generate_all_anchors', 'update_anchors_for_files',
    'load_anchors', 'get_anchor', 'filter_anchors_by_file',
    # 关系图 (6)
    'generate_relations', 'load_relations', 'get_node_edges', 'expand_node',
    'filter_edges_by_keyword', 'count_edge_types',
    # 导航链 (7)
    'Step', 'Target', 'start', 'jump', 'get_target', 'done', 'escalate',
]
