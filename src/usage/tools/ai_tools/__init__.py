"""
CodeDendrite AI 工具接口层
提供统一的 API 接口供各种 AI 调用（Copilot、Cursor、Continue 等）

支持的工具类型：
1. code_analysis - 代码结构分析
2. code_search - 代码搜索
3. anchor_check - 锚点检查
4. inheritance_trace - 继承追踪
5. dataflow_analyze - 数据流分析
6. smart_analyze - 智能分层分析
"""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime


# ============ 导入各层分析器 ============
import sys
from pathlib import Path

# 添加当前目录到 Python 路径
CURRENT_DIR = Path(__file__).parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# 延迟导入，避免循环依赖

from usage.tools.ai_tools.code_dendrite_tool_etc import CodeDendriteTool, _refresh_all_anchors, _load_anchor_db, _compute_hash_v2, AnchorCheckTool, _get_analyzer, CodeAnalysisTool, _analyze_dataflow, DataflowAnalyzeTool, CodeSearchTool
from usage.tools.ai_tools.smart_analyze_tool_etc import _SmartCodeAnalyzer, SmartAnalyzeTool, _InheritanceTracker, InheritanceTraceTool, CodeDendriteAPI

__all__ = ['CodeDendriteTool', '_refresh_all_anchors', '_load_anchor_db', '_compute_hash_v2', 'AnchorCheckTool', '_get_analyzer', 'CodeAnalysisTool', '_analyze_dataflow', 'DataflowAnalyzeTool', 'CodeSearchTool', '_SmartCodeAnalyzer', 'SmartAnalyzeTool', '_InheritanceTracker', 'InheritanceTraceTool', 'CodeDendriteAPI']
