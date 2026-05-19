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
def _get_analyzer(*args, **kwargs):
    from codeAnalysis.analyzer import get_analyzer
    return get_analyzer(*args, **kwargs)

def _compute_hash_v2(*args, **kwargs):
    from codeTree.anchor_engine_v2 import compute_hash_v2
    return compute_hash_v2(*args, **kwargs)

def _load_anchor_db():
    from codeTree.anchor_engine_v2 import load_anchor_db
    return load_anchor_db()

def _refresh_all_anchors(*args, **kwargs):
    from codeTree.anchor_engine_v2 import refresh_all_anchors
    return refresh_all_anchors(*args, **kwargs)

def _analyze_dataflow(*args, **kwargs):
    from codeTree.dataflow_analyzer import DataFlowAnalyzer
    analyzer = DataFlowAnalyzer(args[0] if args else ".")
    return analyzer

def _InheritanceTracker(*args, **kwargs):
    from inheritance.inheritance_tracker import InheritanceTracker
    return InheritanceTracker(*args, **kwargs)

def _SmartCodeAnalyzer(*args, **kwargs):
    from smartAnalyzer.smart_analyzer import SmartCodeAnalyzer
    return SmartCodeAnalyzer(*args, **kwargs)


class CodeDendriteTool:
    """CodeDendrite 工具基类"""
    
    name = "codedendrite_tool"
    description = "代码理解与分析工具"
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        if not self.project_root.exists():
            raise ValueError(f"项目根目录不存在：{project_root}")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具，返回标准格式结果"""
        raise NotImplementedError
    
    def _make_result(self, success: bool, data: Any = None, error: str = None) -> Dict:
        """标准化返回格式"""
        result = {
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "tool": self.name
        }
        if success:
            result["data"] = data
        else:
            result["error"] = error or "Unknown error"
        return result


class CodeAnalysisTool(CodeDendriteTool):
    """代码结构分析工具"""
    
    name = "code_analysis"
    description = "分析代码文件结构，提取函数、类、导入等信息"
    
    def execute(
        self, 
        file_path: str = None,
        language: str = None,
        include_body: bool = False
    ) -> Dict[str, Any]:
        """
        分析代码结构
        
        Args:
            file_path: 要分析的文件路径（相对或绝对）
            language: 指定语言（如 'python', 'typescript'），None 则自动检测
            include_body: 是否包含函数体内容
            
        Returns:
            {
                "functions": [...],
                "classes": [...],
                "imports": [...],
                "metrics": {...}
            }
        """
        try:
            # 处理路径
            if not os.path.isabs(file_path):
                file_path = str(self.project_root / file_path)
            
            analyzer = _get_analyzer(str(self.project_root), language)
            module_info = analyzer.analyze_file(file_path)
            
            result = {
                "file": file_path,
                "language": analyzer.language_name,
                "functions": [f.to_dict() for f in module_info.functions],
                "classes": module_info.classes,
                "imports": module_info.imports,
                "metrics": {
                    "function_count": len(module_info.functions),
                    "class_count": len(module_info.classes),
                    "line_count": len(open(file_path).readlines())
                }
            }
            
            return self._make_result(True, result)
            
        except Exception as e:
            return self._make_result(False, error=str(e))


class CodeSearchTool(CodeDendriteTool):
    """代码搜索工具"""
    
    name = "code_search"
    description = "在项目中搜索符号定义、引用或使用位置"
    
    def execute(
        self,
        symbol_name: str,
        search_type: str = "definition",  # "definition" | "references" | "usage"
        file_pattern: str = None
    ) -> Dict[str, Any]:
        """
        搜索代码符号
        
        Args:
            symbol_name: 要搜索的符号名（函数名、类名等）
            search_type: 搜索类型
            file_pattern: 文件匹配模式（如 "*.py"）
            
        Returns:
            {
                "matches": [
                    {"file": "...", "line": 10, "type": "definition"},
                    ...
                ]
            }
        """
        try:
            matches = []
            
            # 遍历项目文件
            for root, dirs, files in os.walk(self.project_root):
                # 过滤文件
                if file_pattern:
                    import fnmatch
                    files = [f for f in files if fnmatch.fnmatch(f, file_pattern)]
                
                for filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines, 1):
                                if symbol_name in line:
                                    matches.append({
                                        "file": str(filepath),
                                        "line": i,
                                        "content": line.strip()[:100]
                                    })
                    except:
                        continue
            
            result = {
                "symbol": symbol_name,
                "search_type": search_type,
                "total_matches": len(matches),
                "matches": matches[:50]  # 限制返回数量
            }
            
            return self._make_result(True, result)
            
        except Exception as e:
            return self._make_result(False, error=str(e))


class AnchorCheckTool(CodeDendriteTool):
    """锚点检查工具"""
    
    name = "anchor_check"
    description = "检查代码锚点的有效性，检测漂移和变更"
    
    def execute(
        self,
        anchor_id: str = None,
        file_path: str = None,
        batch_mode: bool = False
    ) -> Dict[str, Any]:
        """
        检查锚点状态
        
        Args:
            anchor_id: 单个锚点 ID
            file_path: 检查某文件的所有锚点
            batch_mode: 批量检查所有锚点
            
        Returns:
            {
                "anchors": [
                    {
                        "id": "...",
                        "status": "ok|stale|missing",
                        "severity": "low|medium|high|critical"
                    }
                ]
            }
        """
        try:
            if not load_anchor_db():
                return self._make_result(False, error="锚点数据库为空")
            
            results = []
            
            if batch_mode or (not anchor_id and not file_path):
                # 批量检查
                report = _refresh_all_anchors(self.project_root)
                results = [r.to_dict() for r in report]
                
            elif anchor_id:
                # 检查单个锚点
                db = _load_anchor_db()
                if not db:
                    return self._make_result(False, error="锚点数据库为空")
                
                anchor = next((a for a in db if a.id == anchor_id), None)
                if not anchor:
                    return self._make_result(False, error=f"锚点 {anchor_id} 不存在")
                
                hash, status, struct_hash = _compute_hash_v2(
                    anchor.file, 
                    anchor.symbol,
                    anchor.line_start,
                    anchor.line_end,
                    anchor.hash_mode,
                    self.project_root
                )
                
                results.append({
                    "id": anchor.id,
                    "status": status,
                    "stored_hash": anchor.hash,
                    "current_hash": hash
                })
                
            elif file_path:
                # 检查文件的所有锚点
                db = _load_anchor_db()
                file_anchors = [a for a in db if a.file == file_path]
                for anchor in file_anchors:
                    hash, status, _ = _compute_hash_v2(
                        anchor.file,
                        anchor.symbol,
                        self.project_root
                    )
                    results.append({
                        "id": anchor.id,
                        "status": status
                    })
            
            return self._make_result(True, {"anchors": results})
            
        except Exception as e:
            return self._make_result(False, error=str(e))


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


class DataflowAnalyzeTool(CodeDendriteTool):
    """数据流分析工具"""
    
    name = "dataflow_analyze"
    description = "分析函数/模块的数据流动和变量变换"
    
    def execute(
        self,
        function_name: str,
        file_path: str,
        track_params: bool = True,
        depth: int = 3
    ) -> Dict[str, Any]:
        """
        分析数据流
        
        Args:
            function_name: 函数名
            file_path: 文件路径
            track_params: 是否追踪参数
            depth: 分析深度层级
            
        Returns:
            {
                "function": "...",
                "inputs": [...],
                "outputs": [...],
                "transformations": [...],
                "call_chain": [...]
            }
        """
        try:
            if not os.path.isabs(file_path):
                file_path = str(self.project_root / file_path)
            
            analysis = _analyze_dataflow(
                file_path,
                function_name,
                track_params=track_params,
                max_depth=depth
            )
            
            result = {
                "function": function_name,
                "file": file_path,
                "analysis": analysis
            }
            
            return self._make_result(True, result)
            
        except Exception as e:
            return self._make_result(False, error=str(e))


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


# ============ 统一入口 ============

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


# ============ CLI 入口 ============

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
