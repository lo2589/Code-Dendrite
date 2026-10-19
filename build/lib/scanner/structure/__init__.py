"""
项目结构分析器 - 集成到 code_flowchart

功能：
1. 递归扫描项目目录结构
2. 统计文件数、代码行数、语言分布
3. 生成树形展示和 JSON 输出
4. 与函数调用图分析无缝集成
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from scanner.language.base import ProjectInfo

from scanner.structure.project_structure_analyzer import ProjectStructureAnalyzer, analyze_project_structure
from scanner.structure.enrich_project_info_with_structure import enrich_project_info_with_structure

__all__ = ['ProjectStructureAnalyzer', 'analyze_project_structure', 'enrich_project_info_with_structure']
