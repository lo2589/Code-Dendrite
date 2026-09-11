#!/usr/bin/env python3
"""
代码可视化工具 - 主入口
功能：
1. 函数调用图分析 - 生成 Mermaid 甘特图
2. 项目结构分析 - 扫描目录结构并统计
"""
import argparse
import sys
import os
from pathlib import Path
from typing import Optional

# 导入工具包内的模块
from tools.codeAnalysis.analyzer import PythonAnalyzer, CppAnalyzer, JavaAnalyzer
from tools.codeAnalysis.analyzer.structure_analyzer import ProjectStructureAnalyzer, analyze_project_structure
from tools.codeAnalysis.graph import MermaidGenerator, generate_mermaid_for_project


def detect_language(project_path: str) -> str:
    """自动检测项目语言"""
    extensions = {}
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv', '.venv', 'build', 'dist']]
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in ['.py', '.c', '.cpp', '.h', '.hpp', '.cc', '.java', '.js', '.ts']:
                extensions[ext] = extensions.get(ext, 0) + 1
    if not extensions:
        return "unknown"
    most_common = max(extensions.items(), key=lambda x: x[1])
    ext_to_lang = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.c': 'cpp', '.cpp': 'cpp', '.h': 'cpp', '.hpp': 'cpp', '.cc': 'cpp', '.java': 'java'}
    return ext_to_lang.get(most_common[0], 'unknown')


def analyze_project(project_path: str, language: Optional[str] = None):
    """分析项目"""
    if not os.path.exists(project_path):
        print(f"[ERROR] Path not found: {project_path}")
        sys.exit(1)

    if not language:
        language = detect_language(project_path)
        print(f"[INFO] Detected language: {language}")

    analyzers = {'python': PythonAnalyzer, 'javascript': PythonAnalyzer, 'typescript': PythonAnalyzer, 'cpp': CppAnalyzer, 'java': JavaAnalyzer}
    analyzer_class = analyzers.get(language)
    if not analyzer_class:
        print(f"[ERROR] Unsupported language: {language}")
        sys.exit(1)

    print(f"[INFO] Analyzing: {project_path}")
    analyzer = analyzer_class(project_path)
    return analyzer.analyze()


def print_statistics(project_info):
    """打印统计信息"""
    print("\n" + "="*60)
    print("[STATISTICS]")
    print(f"  Language: {project_info.language}")
    print(f"  Files: {len(project_info.files)}")
    print(f"  Functions: {len(project_info.functions)}")
    print(f"  Modules: {len(project_info.modules)}")
    print(f"  Calls: {len(project_info.call_graph)}")
    print("="*60)

    if project_info.functions:
        print("\n[FUNCTIONS]")
        for func in project_info.functions[:10]:
            print(f"  - {func.full_name}")
            print(f"    @ {func.file_path}:{func.line_number}")
            if func.parameters:
                print(f"    Params: {', '.join(func.parameters)}")
            if func.calls:
                print(f"    Calls: {', '.join(func.calls[:5])}")


def main():
    parser = argparse.ArgumentParser(description='Code to Flowchart - Convert code to Mermaid diagrams')
    parser.add_argument('path', nargs='?', help='Project path')
    parser.add_argument('--language', '-l', choices=['python', 'cpp', 'java', 'javascript', 'typescript'], help='Specify language')
    parser.add_argument('--output', '-o', help='Output file')
    parser.add_argument('--stats', '-s', action='store_true', help='Show statistics only')
    parser.add_argument('--format', '-f', choices=['full', 'gantt', 'callgraph', 'sequence', 'flow', 'structure', 'tree', 'json'], default='full', help='Output format')
    parser.add_argument('--entry', '-e', help='Entry function')
    parser.add_argument('--depth', '-d', type=int, default=8, help='Max depth for structure analysis')

    args = parser.parse_args()

    if not args.path:
        parser.print_help()
        sys.exit(1)

    # 如果是结构分析格式，使用新的分析器
    if args.format in ['structure', 'tree', 'json']:
        print(f"\n[INFO] Analyzing project structure...")
        result = analyze_project_structure(args.path, output_format=args.format, max_depth=args.depth)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"[OK] Saved to: {args.output}")
        else:
            print("\n" + "="*60)
            print("[OUTPUT]")
            print("="*60)
            print(result)
        return

    # 原有的函数调用图分析逻辑
    project_info = analyze_project(args.path, args.language)
    print_statistics(project_info)

    if args.stats:
        return

    print(f"\n[INFO] Generating {args.format} format...")
    report = generate_mermaid_for_project(project_info, output_format=args.format, entry_func=args.entry)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"[OK] Saved to: {args.output}")
    else:
        print("\n" + "="*60)
        print("[OUTPUT]")
        print("="*60)
        print(report)


if __name__ == "__main__":
    main()
