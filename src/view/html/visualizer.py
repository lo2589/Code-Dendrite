"""
可视化器 - 使用 Graphviz 生成流程图
"""

import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class GraphConfig:
    """图形配置"""
    title: str = "Code Flowchart"
    rankdir: str = "TB"  # TB=从上到下, LR=从左到右
    node_color: str = "#4A90D9"
    edge_color: str = "#666666"
    font_name: str = "Arial"
    font_size: int = 12
    dpi: int = 150


class Visualizer:
    """Graphviz 可视化生成器"""

    def __init__(self, config: GraphConfig = None):
        self.config = config or GraphConfig()

    def generate_dot(self, functions: List[Any], call_graph: Dict[str, List[str]]) -> str:
        """生成 DOT 格式图形描述"""
        lines = [
            'digraph G {',
            f'    label="{self.config.title}";',
            f'    labelloc="t";',
            f'    fontsize={self.config.font_size + 4};',
            f'    rankdir={self.config.rankdir};',
            '    node [shape=box style="rounded,filled" fillcolor="#E8F4FD" fontname="Arial" fontsize=10];',
            '    edge [color="#666666" fontname="Arial" fontsize=9];',
            ''
        ]

        node_ids = {}
        for i, func in enumerate(functions):
            node_id = f'node_{i}'
            node_ids[func.name] = node_id

            label_parts = [
                f'{func.name}',
                f'📁 {os.path.basename(func.file)}:{func.line}'
            ]
            if func.params:
                label_parts.append(f'📥 {", ".join(func.params)}')

            label = '\\n'.join(label_parts)
            lines.append(f'    {node_id} [label="{label}"];')

        lines.append('')

        added_edges = set()
        for func in functions:
            if func.name not in node_ids:
                continue

            source_id = node_ids[func.name]
            for called in func.calls:
                if called in node_ids and called != func.name:
                    edge_key = (source_id, node_ids[called])
                    if edge_key not in added_edges:
                        lines.append(f'    {source_id} -> {node_ids[called]};')
                        added_edges.add(edge_key)

        lines.append('}')

        return '\n'.join(lines)

    def generate_svg(self, functions: List[Any], call_graph: Dict[str, List[str]], output_path: str) -> str:
        """生成 SVG 文件"""
        try:
            import graphviz
        except ImportError:
            raise ImportError("请先安装 graphviz: pip install graphviz")

        dot_content = self.generate_dot(functions, call_graph)

        graph = graphviz.Source(dot_content)
        output_base = os.path.splitext(output_path)[0]

        if output_path.endswith('.svg'):
            graph.render(output_base, format='svg', cleanup=True)
        elif output_path.endswith('.png'):
            graph.render(output_base, format='png', cleanup=True)
        elif output_path.endswith('.pdf'):
            graph.render(output_base, format='pdf', cleanup=True)
        else:
            graph.render(output_base, format='svg', cleanup=True)

        result_path = f"{output_base}.svg"
        print(f"✅ 流程图已生成: {result_path}")
        return result_path

    def generate_mermaid(self, functions: List[Any], call_graph: Dict[str, List[str]]) -> str:
        """生成 Mermaid 格式（Markdown 友好）"""
        lines = [
            "```mermaid",
            f"flowchart {self.config.rankdir}",
            '    %% Nodes'
        ]

        node_ids = {}
        for i, func in enumerate(functions):
            node_id = f'F{i}'
            node_ids[func.name] = node_id

            params_str = f'({", ".join(func.params)})' if func.params else ''
            lines.append(f'    {node_id}["{func.name}{params_str}"]')

        lines.append('')
        lines.append('    %% Edges')

        added_edges = set()
        for func in functions:
            if func.name not in node_ids:
                continue

            source_id = node_ids[func.name]
            for called in func.calls:
                if called in node_ids and called != func.name:
                    edge_key = (source_id, node_ids[called])
                    if edge_key not in added_edges:
                        lines.append(f'    {source_id} --> {node_ids[called]}')
                        added_edges.add(edge_key)

        lines.append("```")

        return '\n'.join(lines)


def demo():
    """演示用法"""
    from code_flowchart.parsers.python_parser import PythonParser

    parser = PythonParser()
    parser.parse_directory("./backend")

    config = GraphConfig(
        title="Code Flowchart - Backend",
        rankdir="TB"
    )

    visualizer = Visualizer(config)

    output_path = "./backend_flowchart.svg"
    try:
        visualizer.generate_svg(parser.functions, parser.call_graph, output_path)
    except ImportError as e:
        print(f"⚠️ {e}")
        print("\n📝 替代方案 - 生成 DOT 格式:")
        dot_content = visualizer.generate_dot(parser.functions, parser.call_graph)
        dot_path = output_path.replace('.svg', '.dot')
        with open(dot_path, 'w') as f:
            f.write(dot_content)
        print(f"✅ DOT 已保存到: {dot_path}")

        print("\n📝 替代方案 - 生成 Mermaid 格式:")
        mermaid_content = visualizer.generate_mermaid(parser.functions, parser.call_graph)
        mermaid_path = output_path.replace('.svg', '_mermaid.md')
        with open(mermaid_path, 'w') as f:
            f.write(mermaid_content)
        print(f"✅ Mermaid 已保存到: {mermaid_path}")
        print("\n" + mermaid_content)


if __name__ == "__main__":
    demo()
