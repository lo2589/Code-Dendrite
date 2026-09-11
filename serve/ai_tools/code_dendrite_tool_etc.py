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

def _refresh_all_anchors(*args, **kwargs):
    from index.codeTree.anchor_engine_v2 import refresh_all_anchors
    return refresh_all_anchors(*args, **kwargs)

def _load_anchor_db():
    from index.codeTree.anchor_engine_v2 import load_anchor_db
    return load_anchor_db()

def _compute_hash_v2(*args, **kwargs):
    from index.codeTree.anchor_engine_v2 import compute_hash_v2
    return compute_hash_v2(*args, **kwargs)

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

def _get_analyzer(*args, **kwargs):
    from parse.codeAnalysis.analyzer import get_analyzer
    return get_analyzer(*args, **kwargs)

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

def _analyze_dataflow(*args, **kwargs):
    from relate.codeTree.dataflow_analyzer import DataFlowAnalyzer
    analyzer = DataFlowAnalyzer(args[0] if args else ".")
    return analyzer

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
