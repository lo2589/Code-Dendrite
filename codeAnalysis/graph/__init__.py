"""
Mermaid 图表生成器
"""
from typing import Dict, List, Set, Optional
# 使用相对导入，支持包内调用
try:
    from analyzer.base import ProjectInfo, FunctionInfo
except ImportError:
    # 如果作为独立脚本运行
    from ..analyzer.base import ProjectInfo, FunctionInfo


MERMAID_INIT = """%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '20px', 'primaryColor': '#4CAF50', 'edgeLabelBackground': '#fff'}}}%%

"""


class MermaidGenerator:
    def __init__(self, project_info: ProjectInfo):
        self.project_info = project_info
        self.generated_functions: Set[str] = set()

    def generate_gantt(self, max_depth: int = 5, max_functions: int = 100) -> str:
        """
        生成详细甘特图（支持两种模式）
        
        Args:
            max_depth: 最大深度
            max_functions: 最大函数数
        """
        # 如果函数数量超过阈值，使用简化模式
        if len(self.project_info.functions) > max_functions * 2:
            return self._generate_gantt_simple(max_depth, max_functions)
        else:
            # 否则生成完整详细甘特图
            return self._generate_gantt_full(max_depth)
    
    def _generate_gantt_simple(self, max_depth: int = 5, max_functions: int = 100) -> str:
        """
        简化版甘特图 - 按模块分组展示核心函数
        """
        lines = ["```mermaid", "gantt",
                 f'    title {self.project_info.language} Project Overview',
                 "    dateFormat X", "    axisFormat %s", "",
                 "    %% 核心模块与关键路径"]
        modules = self._group_by_module()
        time_counter = 0
        for module_name, functions in sorted(modules.items()):
            lines.append(f"    section {self._escape_string(module_name)}")
            # 每个模块只展示最重要的前几个函数（按调用其他函数的多少排序）
            top_funcs = sorted(functions, key=lambda f: len(f.calls), reverse=True)[:3]
            for func in top_funcs:
                duration = self._calculate_duration(func, max_depth)
                start = time_counter
                end = start + duration
                time_counter = end + 5
                callee_count = len(self.project_info.get_callees(func.full_name))
                label = f"{func.name} ({callee_count} calls)"
                lines.append(f"    {label:<50} :active, {start}, {end}")
        lines.append("```")
        return "\n".join(lines)
    
    def _generate_gantt_full(self, max_depth: int = 10, max_functions: int = 500) -> str:
        """
        完整版甘特图 - 包含所有函数、调用关系、执行时间估算
        
        特性：
        1. 完整的函数调用链
        2. 执行时间估算（基于代码复杂度）
        3. 关键路径高亮
        4. 模块间依赖标注
        5. 参数信息展示
        
        **适用于任意项目：Python/TypeScript/C++/Java**
        """
        lines = ["```mermaid", "gantt",
                 f'    title {self.project_info.language} Project - Full Execution Flow',
                 "    dateFormat X", "    axisFormat %H:%M:%S", "",
                 "    %% 图例说明：",
                 "    %% - active: 核心函数 (被调用次数多)",
                 "    %% - done: 普通函数",
                 "    %% - crit: 入口函数/关键路径",
                 ""]
        
        # 分析函数重要度
        call_counts = {}
        for func in self.project_info.functions:
            call_counts[func.full_name] = len(func.calls)
        
        # 找入口函数（调用别人但自己不被调用的）
        entry_points = []
        all_called = set()
        for func in self.project_info.functions:
            all_called.update(func.calls)
        
        for func in self.project_info.functions:
            if func.full_name not in all_called and len(func.calls) > 0:
                entry_points.append(func)
        
        # 按模块组织
        modules = self._group_by_module()
        time_counter = 0
        
        for module_name, functions in sorted(modules.items()):
            lines.append(f"    section {self._escape_string(module_name)}")
            
            # 排序：入口函数优先，然后按调用次数
            sorted_funcs = sorted(
                functions,
                key=lambda f: (
                    f.full_name in [e.full_name for e in entry_points],
                    len(f.calls)
                ),
                reverse=True
            )
            
            funcs_per_module = max_functions // len(modules) if modules else max_functions
            for func in sorted_funcs[:funcs_per_module]:
                duration = self._calculate_duration(func, max_depth)
                start = time_counter
                end = start + duration
                
                # 判定函数类型
                is_entry = func in entry_points
                is_core = len(func.calls) > 5 or any(f.full_name in func.calls for f in self.project_info.functions if len(f.calls) > 3)
                
                if is_entry:
                    status = "crit"  # 关键路径/入口
                    time_counter = end + 10
                elif is_core:
                    status = "active"  # 核心函数
                    time_counter = end + 5
                else:
                    status = "done"  # 普通函数
                    time_counter = end + 2
                
                # 构建标签：函数名 + 参数 + 调用统计
                params_str = ", ".join(func.parameters[:3])
                if len(func.parameters) > 3:
                    params_str += "..."
                
                label = f"{func.name}({params_str}) [{len(func.calls)} calls]"
                
                lines.append(f"    {label:<60} :{status}, {start}, {end}")
                
                # 如果有依赖关系，添加注释
                if func.calls and len(func.calls) <= 3:
                    callee_names = [c.split('.')[-1] for c in func.calls]
                    lines.append(f"        note right of {label}: Calls: {', '.join(callee_names)}")
        
        lines.append("```")
        return "\n".join(lines)

    def generate_call_graph(self, max_calls: int = 100) -> str:
        lines = ["```mermaid", MERMAID_INIT, "graph LR"]
        count = 0
        for func_name, callees in self.project_info.call_graph.items():
            if not callees:
                continue
            if count >= max_calls:
                break
            short_name = self._shorten_name(func_name)
            for callee in callees[:10]:
                if count >= max_calls:
                    break
                short_callee = self._shorten_name(callee)
                lines.append(f"    {short_name} --> {short_callee}")
                count += 1
        lines.append("```")
        return "\n".join(lines)

    def generate_call_graph_detailed(self, max_calls: int = 200) -> str:
        lines = ["```mermaid", MERMAID_INIT, "graph TD"]
        count = 0
        all_names = self._get_all_function_names()
        for func_name, callees in self.project_info.call_graph.items():
            if not callees:
                continue
            short_name = self._shorten_name(func_name)
            lines.append(f"    {short_name}(({func_name}))")
            for callee in callees[:10]:
                if count >= max_calls:
                    break
                short_callee = self._shorten_name(callee)
                if callee in all_names:
                    lines.append(f"    {short_callee}(({callee}))")
                lines.append(f"    {short_name} --> {short_callee}")
                count += 1
        lines.append("```")
        return "\n".join(lines)

    def generate_sequence(self, entry_func: Optional[str] = None) -> str:
        lines = ["```mermaid", MERMAID_INIT, "sequenceDiagram"]
        if not entry_func and self.project_info.functions:
            entry_func = self.project_info.functions[0].full_name
        if entry_func:
            visited = set()
            self._generate_sequence_recursive(entry_func, lines, visited, depth=0)
        lines.append("```")
        return "\n".join(lines)

    def _generate_sequence_recursive(self, func_name: str, lines: List[str], visited: Set[str], depth: int = 0, max_depth: int = 10):
        if func_name in visited or depth > max_depth:
            return
        visited.add(func_name)
        indent = "    " * (depth + 1)
        func = self.project_info.get_function(func_name)
        if not func:
            func = self._find_function_by_name(func_name)
        if func:
            lines.append(f"{indent}participant {self._shorten_name(func_name)} as {func_name}")
        callees = self.project_info.get_callees(func_name)
        for callee in callees[:5]:
            if callee not in visited:
                lines.append(f"{indent}{self._shorten_name(func_name)}->>+{self._shorten_name(callee)}: call")
                self._generate_sequence_recursive(callee, lines, visited, depth + 1, max_depth)
                lines.append(f"{indent}{self._shorten_name(callee)}-->>-{self._shorten_name(func_name)}: return")

    def generate_execution_flow(self, entry_func: Optional[str] = None) -> str:
        lines = ["```mermaid", MERMAID_INIT, "flowchart TD"]
        visited = set()
        nodes = set()
        edges = []
        if not entry_func and self.project_info.functions:
            entry_func = self.project_info.functions[0].full_name
        if entry_func:
            self._build_flow_graph(entry_func, nodes, edges, visited)
        for node in sorted(nodes):
            short_name = self._shorten_name(node)
            lines.append(f"    {short_name}([{node}])")
        for src, dst in edges:
            lines.append(f"    {self._shorten_name(src)} --> {self._shorten_name(dst)}")
        lines.append("```")
        return "\n".join(lines)

    def _build_flow_graph(self, func_name: str, nodes: Set[str], edges: List[tuple], visited: Set[str], max_depth: int = 10):
        if func_name in visited or len(nodes) > 50:
            return
        visited.add(func_name)
        nodes.add(func_name)
        callees = self.project_info.get_callees(func_name)
        for callee in callees[:10]:
            if callee not in visited:
                edges.append((func_name, callee))
                self._build_flow_graph(callee, nodes, edges, visited, max_depth - 1)

    def _group_by_module(self) -> Dict[str, List[FunctionInfo]]:
        modules = {}
        for func in self.project_info.functions:
            module_name = func.file_path.split('/')[-1].split('\\')[-1]
            if module_name not in modules:
                modules[module_name] = []
            modules[module_name].append(func)
        return modules

    def _calculate_duration(self, func: FunctionInfo, max_depth: int) -> int:
        callees = self.project_info.get_callees(func.full_name)
        if not callees:
            return 3
        return min(3 + len(callees) * 2, max_depth * 3)

    def _escape_string(self, text: str) -> str:
        return text.replace('"', "'").replace('[', '(').replace(']', ')')

    def _shorten_name(self, name: str) -> str:
        parts = name.split('.')
        if len(parts) > 2:
            return parts[-1]
        return name

    def _find_function_by_name(self, name: str) -> Optional[FunctionInfo]:
        for func in self.project_info.functions:
            if func.full_name.endswith(name) or func.name == name:
                return func
        return None

    def _get_all_function_names(self) -> Set[str]:
        names = set()
        for func in self.project_info.functions:
            names.add(func.full_name)
            names.add(func.name)
        return names

    def generate_summary(self) -> str:
        lines = ["## Project Summary", "", f"**Path**: `{self.project_info.root_path}`", f"**Language**: {self.project_info.language}", f"**Files**: {len(self.project_info.files)}", f"**Functions**: {len(self.project_info.functions)}", f"**Modules**: {len(self.project_info.modules)}", f"**Calls**: {len(self.project_info.call_graph)}", ""]
        entry_funcs = self._find_entry_functions()
        if entry_funcs:
            lines.append("### Entry Functions")
            for func in entry_funcs[:10]:
                lines.append(f"- `{func.full_name}` @ {func.file_path}:{func.line_number}")
        return "\n".join(lines)

    def _find_entry_functions(self) -> List[FunctionInfo]:
        called_funcs = set()
        for callees in self.project_info.call_graph.values():
            called_funcs.update(callees)
        entry_funcs = []
        for func in self.project_info.functions:
            if func.full_name not in called_funcs:
                entry_funcs.append(func)
        return entry_funcs

    def generate_full_report(self, entry_func: Optional[str] = None) -> str:
        report = ["# Code Flow Analysis Report", "", self.generate_summary(), "", "## Execution Flow", "", self.generate_execution_flow(entry_func), "", "## Call Graph", "", self.generate_call_graph(), "", "## Gantt Chart", "", self.generate_gantt()]
        return "\n".join(report)


def generate_mermaid_for_project(project_info: ProjectInfo, output_format: str = "full", entry_func: Optional[str] = None) -> str:
    generator = MermaidGenerator(project_info)
    if output_format == "full":
        return generator.generate_full_report(entry_func)
    elif output_format == "gantt":
        return generator.generate_gantt()
    elif output_format == "callgraph":
        return generator.generate_call_graph()
    elif output_format == "sequence":
        return generator.generate_sequence(entry_func)
    elif output_format == "flow":
        return generator.generate_execution_flow(entry_func)
    else:
        return generator.generate_summary()
