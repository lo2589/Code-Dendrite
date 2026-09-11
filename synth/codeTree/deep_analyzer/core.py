"""
deep_analyzer.py - 深度 AST 数据流分析器
========================================
使用 Python AST 模块深度分析代码：
  - 精确的函数签名提取
  - 完整的调用关系图
  - 变量级数据流追踪
  - 自动生成管线流程图
"""

import ast
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from synth.codeTree.deep_analyzer.data_flow import DataFlowEdge, DataFlowPath, FuncInfo

class DeepAnalyzer(ast.NodeVisitor):
    """深度 AST 分析器"""
    
    def __init__(self, root_path: str):
        self.root = Path(root_path)
        self.functions: Dict[str, FuncInfo] = {}
        self.current_module = ""
        self.current_class: Optional[str] = None
        
    def analyze_all(self) -> Dict:
        """分析所有 Python 文件"""
        
        py_files = []
        _skip = {'__pycache__', '.git', 'node_modules', '.codedendrite'}
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in _skip]
            for fname in filenames:
                if fname.endswith(".py"):
                    py_files.append(Path(dirpath) / fname)
        print(f"📂 找到 {len(py_files)} 个 Python 文件")

        # Step 1: 解析所有文件，提取函数信息
        for py_file in py_files:
            if py_file.name.startswith('__'):
                continue
            self._parse_file(py_file)
        
        print(f"✅ 提取了 {len(self.functions)} 个函数")
        
        # Step 2: 构建调用图
        self._build_call_graph()
        
        # Step 3: 识别入口点
        self._identify_entry_points()
        
        # Step 4: 追踪数据流
        flows = self._trace_data_flows()
        
        return {
            "meta": {
                "root": str(self.root),
                "total_files": len(py_files),
                "total_functions": len(self.functions),
                "entry_points": sum(1 for f in self.functions.values() if f.is_entry_point),
            },
            "functions": {fid: asdict(f) for fid, f in self.functions.items()},
            "call_graph": {
                fid: {
                    "calls": f.calls,
                    "called_by": f.called_by
                }
                for fid, f in self.functions.items()
            },
            "data_flows": [asdict(flow) for flow in flows]
        }
    
    def _parse_file(self, file_path: Path):
        """解析单个文件"""
        
        rel_path = str(file_path.relative_to(self.root))
        self.current_module = file_path.stem
        
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(file_path))
            
            # 遍历顶层节点
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._extract_function(node, rel_path)
                elif isinstance(node, ast.ClassDef):
                    self._extract_class_methods(node, rel_path)
                    
        except Exception as e:
            print(f"⚠️  解析失败 {file_path}: {e}")
    
    def _extract_function(self, node: ast.FunctionDef, file_path: str, 
                          class_name: Optional[str] = None):
        """提取函数信息"""
        
        # 跳过私有函数
        if node.name.startswith('_'):
            return
        
        # 构建函数 ID
        if class_name:
            func_id = f"{self.current_module}.{class_name}.{node.name}"
            qualified = f"{class_name}.{node.name}"
        else:
            func_id = f"{self.current_module}.{node.name}"
            qualified = node.name
        
        # 提取参数
        args = []
        for arg in node.args.args:
            arg_type = self._get_annotation(arg.annotation)
            default = None
            args.append({
                "name": arg.arg,
                "type": arg_type,
                "default": default
            })
        
        # 提取返回值类型
        returns = self._get_annotation(node.returns)
        
        # 构建签名字符串
        sig_args = ", ".join([f"{a['name']}: {a['type']}" for a in args])
        signature = f"def {node.name}({sig_args}) -> {returns}"
        
        # 创建函数信息
        func_info = FuncInfo(
            id=func_id,
            name=node.name,
            qualified=qualified,
            file=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or (node.lineno + 10),
            signature=signature,
            args=args,
            returns=returns,
            calls=[],
            called_by=[]
        )
        
        # 提取这个函数调用了谁
        func_info.calls = self._extract_calls_in_body(node)
        
        self.functions[func_id] = func_info
    
    def _extract_class_methods(self, node: ast.ClassDef, file_path: str):
        """提取类的方法"""
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_function(child, file_path, node.name)
    
    def _extract_calls_in_body(self, func_node: ast.AST) -> List[str]:
        """提取函数体内调用的其他函数"""
        
        calls = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                # 获取被调用的函数名
                if isinstance(node.func, ast.Name):
                    # 直接调用：func()
                    target = node.func.id
                    # 尝试在当前模块中查找
                    possible_id = f"{self.current_module}.{target}"
                    if possible_id in self.functions:
                        calls.append(possible_id)
                
                elif isinstance(node.func, ast.Attribute):
                    # 方法调用：obj.method()
                    method_name = node.func.attr
                    # 尝试推断类型（简化版）
                    if isinstance(node.func.value, ast.Name):
                        obj_type = node.func.value.id
                        # 查找可能的类
                        for fid, finfo in self.functions.items():
                            if fid.endswith(f".{method_name}"):
                                calls.append(fid)
        
        return list(set(calls))
    
    def _get_annotation(self, annotation) -> str:
        """从类型注解获取类型字符串"""
        
        if annotation is None:
            return "Any"
        
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        elif isinstance(annotation, ast.Subscript):
            # 处理 List[str], Dict[str, int] 等
            if isinstance(annotation.value, ast.Name):
                base = annotation.value.id
                if isinstance(annotation.slice, ast.Tuple):
                    params = ', '.join(self._get_annotation(e) 
                                      for e in annotation.slice.elts)
                else:
                    params = self._get_annotation(annotation.slice)
                return f"{base}[{params}]"
        
        return "Any"
    
    def _build_call_graph(self):
        """构建完整的调用图（填充 called_by）"""
        
        for func_id, func_info in self.functions.items():
            for called_id in func_info.calls:
                if called_id in self.functions:
                    self.functions[called_id].called_by.append(func_id)
    
    def _identify_entry_points(self):
        """识别入口点"""
        
        entry_patterns = ['main', 'cmd_', 'handle_', 'run_', 'start_']
        
        for func_id, func_info in self.functions.items():
            # 模式匹配
            for pattern in entry_patterns:
                if func_info.name.startswith(pattern):
                    func_info.is_entry_point = True
                    break
            
            # 没有被任何函数调用，可能是入口
            if not func_info.called_by and func_info.name not in ['__init__']:
                # func_info.is_entry_point = True
                pass
    
    def _trace_data_flows(self) -> List[DataFlowPath]:
        """追踪数据流（从每个入口点开始）"""
        
        flows = []
        entry_points = [fid for fid, f in self.functions.items() if f.is_entry_point]
        
        print(f"🎯 找到 {len(entry_points)} 个入口点")
        
        for entry_id in entry_points:
            flow = self._trace_single_flow(entry_id)
            if flow and len(flow.steps) > 1:
                flows.append(flow)
        
        return flows
    
    def _trace_single_flow(self, entry_id: str, max_depth: int = 8) -> Optional[DataFlowPath]:
        """追踪单个数据流（只在同一文件内追踪）"""
        
        if entry_id not in self.functions:
            return None
        
        entry_func = self.functions[entry_id]
        steps = [entry_id]
        edges = []
        visited = {entry_id}
        current = entry_id
        
        while len(steps) < max_depth:
            func = self.functions.get(current)
            if not func or not func.calls:
                break
            
            # 找下一个函数：必须在同一个文件内
            next_func = None
            for call_id in func.calls:
                if (call_id in self.functions and 
                    call_id not in visited and
                    self.functions[call_id].file == func.file):  # ✅ 同文件检查
                    next_func = call_id
                    break
            
            if not next_func:
                break
            
            # 创建边：精确的变量传递
            target_func = self.functions[next_func]
            edge = DataFlowEdge(
                from_func=current,
                to_func=next_func,
                var_name=target_func.args[0]['name'] if target_func.args else 'arg0',  # ✅ 使用目标函数的第一个参数名
                var_type=target_func.args[0]['type'] if target_func.args else 'Any'
            )
            
            edges.append(edge)
            steps.append(next_func)
            visited.add(next_func)
            current = next_func
        
        return DataFlowPath(
            entry_point=entry_id,
            steps=steps,
            edges=edges
        )
