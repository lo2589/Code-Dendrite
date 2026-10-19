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

from usage.tools.ai_tools.code_dendrite_tool_etc import AnchorCheckTool, CodeAnalysisTool, CodeDendriteTool, CodeSearchTool, DataflowAnalyzeTool

def _SmartCodeAnalyzer(*args, **kwargs):
    from usage.analyze.smart_analyzer.smart_analyzer import SmartCodeAnalyzer
    return SmartCodeAnalyzer(*args, **kwargs)

class SmartAnalyzeTool(CodeDendriteTool):
    """智能分层分析工具"""
    
    name = "smart_analyze"
    description = "根据错误严重程度自动选择分析深度"
    
    def execute(
        self,
        error_message: str = None,
        file_path: str = None,
        severity: str = "auto"  # "auto" | "low" | "medium" | "high" | "critical"
    ) -> Dict[str, Any]:
        """
        智能分析
        
        Args:
            error_message: 错误信息
            file_path: 相关文件
            severity: 严重程度（auto 则根据错误信息判断）
            
        Returns:
            {
                "severity": "detected severity",
                "layers_used": ["L1", "L2", ...],
                "analysis": {...},
                "recommendation": "..."
            }
        """
        try:
            analyzer = _SmartCodeAnalyzer(str(self.project_root))
            
            # 自动判断严重程度
            if severity == "auto":
                severity = analyzer._detect_severity(error_message or "")
            
            # 执行分层分析
            analysis = analyzer.analyze_error(
                error_message or "",
                file_path,
                severity
            )
            
            result = {
                "severity": severity,
                "layers_used": analysis.get("layers_used", []),
                "analysis": analysis,
                "recommendation": analyzer._generate_recommendation(analysis)
            }
            
            return self._make_result(True, result)
            
        except Exception as e:
            return self._make_result(False, error=str(e))

def _InheritanceTracker(*args, **kwargs):
    from analyzer.inherit.language.python.inheritance_tracker import InheritanceTracker
    return InheritanceTracker(*args, **kwargs)

class InheritanceTraceTool(CodeDendriteTool):
    """继承追踪工具"""
    
    name = "inheritance_trace"
    description = "追踪类的继承链路和方法来源"
    
    def execute(
        self,
        class_name: str,
        method_name: str = None,
        show_mro: bool = True
    ) -> Dict[str, Any]:
        """
        追踪继承关系
        
        Args:
            class_name: 类名
            method_name: 方法名（可选）
            show_mro: 是否显示 MRO 列表
            
        Returns:
            {
                "class": "ClassName",
                "mro": ["ClassA", "ClassB", ...],
                "method_origin": {
                    "method": "methodName",
                    "defined_in": "ParentClass",
                    "file": "...",
                    "line": 10
                }
            }
        """
        try:
            tracker = _InheritanceTracker(str(self.project_root))
            
            result = {
                "class": class_name,
                "file": tracker.find_class_definition(class_name)
            }
            
            if show_mro:
                mro = tracker.compute_mro(class_name)
                result["mro"] = mro
            
            if method_name:
                origin = tracker.find_method_origin(class_name, method_name)
                if origin:
                    result["method_origin"] = origin
            
            return self._make_result(True, result)
            
        except Exception as e:
            return self._make_result(False, error=str(e))

class CodeDendriteAPI:
    """
    CodeDendrite 统一 API 入口
    供 AI 助手直接调用
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        
        # 初始化所有工具
        self.tools = {
            "code_analysis": CodeAnalysisTool(project_root),
            "code_search": CodeSearchTool(project_root),
            "anchor_check": AnchorCheckTool(project_root),
            "inheritance_trace": InheritanceTraceTool(project_root),
            "dataflow_analyze": DataflowAnalyzeTool(project_root),
            "smart_analyze": SmartAnalyzeTool(project_root),
        }
    
    def list_tools(self) -> List[Dict]:
        """列出所有可用工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in self.tools.values()
        ]
    
    def call_tool(
        self, 
        tool_name: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用指定工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"未知工具：{tool_name}",
                "available_tools": list(self.tools.keys())
            }
        
        tool = self.tools[tool_name]
        return tool.execute(**kwargs)
    
    # ============ 便捷方法 ============
    
    def analyze_code(self, file_path: str, language: str = None) -> Dict:
        """快捷方法：分析代码结构"""
        return self.call_tool("code_analysis", file_path=file_path, language=language)
    
    def search_symbol(self, symbol: str, pattern: str = None) -> Dict:
        """快捷方法：搜索符号"""
        return self.call_tool("code_search", symbol_name=symbol, file_pattern=pattern)
    
    def check_anchors(self, batch: bool = True) -> Dict:
        """快捷方法：检查锚点"""
        return self.call_tool("anchor_check", batch_mode=batch)
    
    def trace_inheritance(self, class_name: str, method: str = None) -> Dict:
        """快捷方法：追踪继承"""
        return self.call_tool("inheritance_trace", class_name=class_name, method_name=method)
    
    def analyze_dataflow(self, func: str, file: str) -> Dict:
        """快捷方法：数据流分析"""
        return self.call_tool("dataflow_analyze", function_name=func, file_path=file)
    
    def smart_analyze(self, error: str, file: str = None) -> Dict:
        """快捷方法：智能分析"""
        return self.call_tool("smart_analyze", error_message=error, file_path=file)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ai_tools.py <project_root> [tool_name] [args...]")
        sys.exit(1)
    
    project_root = sys.argv[1]
    api = CodeDendriteAPI(project_root)
    
    print("Available tools:")
    for tool in api.list_tools():
        print(f"  - {tool['name']}: {tool['description']}")
