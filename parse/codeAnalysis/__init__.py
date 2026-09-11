# tools/codeAnalysis - 代码可视化工具包
# 
# 功能：
# 1. 函数调用图分析 - 生成 Mermaid 甘特图
# 2. 项目结构分析 - 扫描目录结构并统计
#
# 使用方式：
#   from tools.codeAnalysis import analyze_project, generate_mermaid_for_project
#   from tools.codeAnalysis.analyzer.structure_analyzer import analyze_project_structure

# 导出所有公共 API
from parse.codeAnalysis.analyzer.structure_analyzer import analyze_project_structure, ProjectStructureAnalyzer

__all__ = [
    'analyze_project_structure',
    'ProjectStructureAnalyzer',
]
