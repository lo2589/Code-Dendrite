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


@dataclass
class FuncInfo:
    """函数信息"""
    id: str                    # 唯一 ID: module.func 或 module.Class.method
    name: str                  # 函数名
    qualified: str             # 限定名：Class.method
    file: str                  # 文件路径
    line_start: int            # 起始行
    line_end: int              # 结束行
    
    # 签名信息
    signature: str             # 完整签名文本
    args: List[Dict]           # [{name, type, default}]
    returns: str               # 返回类型
    
    # 调用关系
    calls: List[str]           # 调用的其他函数 ID
    called_by: List[str]       # 被谁调用（后填充）
    
    # 是否是入口点
    is_entry_point: bool = False


@dataclass
class DataFlowEdge:
    """数据流边：从一个函数的输出到另一个函数的输入"""
    from_func: str             # 源函数 ID
    to_func: str               # 目标函数 ID
    var_name: str              # 传递的变量名
    var_type: str              # 变量类型
    transform: str = ""        # 变换操作（可选）


@dataclass
class DataFlowPath:
    """一条完整的数据流路径"""
    entry_point: str           # 入口函数 ID
    steps: List[str]           # 函数 ID 序列 [func_a, func_b, ...]
    edges: List[DataFlowEdge]  # 边（数据传递）


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


def generate_pipeline_html(result: Dict, output_path: str):
    """生成管线流程图 HTML"""
    
    flows = result['data_flows']
    
    html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CodeTree 数据流管线图</title>
<style>
:root {{
  --bg: #0f1117; --bg2: #161b22; --bg3: #1c2128;
  --border: #30363d; --border2: #4a5057;
  --text: #e6edf3; --text2: #848d97; --text3: #6e7681;
  --accent: #58a6ff; --green: #3fb950; --purple: #bc8cff; --amber: #d29922;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ 
  background: var(--bg); color: var(--text); 
  font-family: 'SF Mono', 'Cascadia Code', Consolas, monospace; 
  padding: 30px; overflow-x: auto;
}}
h1 {{ font-size: 20px; margin-bottom: 10px; color: var(--accent); }}
p {{ color: var(--text3); font-size: 12px; margin-bottom: 20px; }}
.flowchart-container {{ display: flex; flex-direction: column; gap: 60px; padding: 20px; min-width: max-content; }}
.flow-row {{ display: flex; align-items: flex-start; gap: 0; position: relative; padding-left: 20px; }}
.step-indicator {{ position: absolute; left: -60px; top: 50%; transform: translateY(-50%); font-size: 11px; color: var(--text3); background: var(--bg2); padding: 6px 10px; border-radius: 4px; white-space: nowrap; border: 1px solid var(--border); }}
.func-box {{ background: var(--bg2); border: 2px solid var(--border); border-radius: 6px; min-width: 220px; max-width: 280px; position: relative; transition: all 0.2s; cursor: pointer; z-index: 1; }}
.func-box:hover {{ border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(88, 166, 255, 0.2); }}
.func-box.entry-point {{ border-color: var(--green); background: rgba(63, 185, 80, 0.05); }}
.func-header {{ padding: 10px 12px; border-bottom: 1px solid var(--border); background: var(--bg3); }}
.func-title {{ font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 4px; }}
.func-file {{ font-size: 9px; color: var(--text3); }}
.io-section {{ padding: 8px 12px; }}
.io-title {{ font-size: 9px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
.input-port, .output-port {{ display: flex; align-items: center; gap: 6px; padding: 4px 0; position: relative; }}
.port-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }}
.output-port .port-dot {{ background: var(--green); }}
.port-label {{ font-size: 10px; color: var(--text); }}
.port-type {{ font-size: 9px; color: var(--purple); margin-left: 4px; }}
.connection-area {{ width: 80px; position: relative; flex-shrink: 0; }}
.single-line {{ position: absolute; height: 2px; background: var(--border2); left: 0; right: 0; }}
.single-line::after {{ content: ''; position: absolute; right: 0; top: 50%; transform: translateY(-50%); border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 8px solid var(--border2); }}
.line-label {{ position: absolute; top: -16px; left: 50%; transform: translateX(-50%); font-size: 9px; color: var(--text2); background: var(--bg); padding: 2px 5px; border-radius: 3px; white-space: nowrap; border: 1px solid var(--border); }}
.stat {{ background: var(--bg2); padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: inline-block; }}
.stat-label {{ font-size: 11px; color: var(--text3); margin-right: 12px; }}
.stat-value {{ font-size: 14px; color: var(--accent); font-weight: 600; }}
.legend {{ display: flex; gap: 24px; padding: 12px 16px; background: var(--bg2); border-radius: 8px; font-size: 11px; margin-bottom: 20px; flex-wrap: wrap; }}
.legend-item {{ display: flex; align-items: center; gap: 8px; }}
.legend-box {{ width: 24px; height: 24px; border-radius: 4px; border: 2px solid; }}
.legend-box.normal {{ border-color: var(--border); background: var(--bg2); }}
.legend-box.entry {{ border-color: var(--green); background: rgba(63, 185, 80, 0.05); }}
.legend-line-wrapper {{ position: relative; width: 40px; height: 20px; }}
.legend-line {{ position: absolute; top: 50%; left: 0; right: 0; height: 2px; background: var(--border2); }}
.legend-line::after {{ content: ''; position: absolute; right: 0; top: 50%; transform: translateY(-50%); border-top: 4px solid transparent; border-bottom: 4px solid transparent; border-left: 6px solid var(--border2); }}
.empty-state {{ text-align: center; padding: 60px; color: var(--text3); font-size: 13px; }}
</style>
</head>
<body>
<h1>🔗 CodeTree 数据流管线图</h1>
<p>函数 = 方块 | 数据 = 独立连线 | 一输入一线 | 一输出一线</p>

<div class="stat">
  <span class="stat-label">文件数:</span><span class="stat-value">{result['meta']['total_files']}</span>
  <span class="stat-label" style="margin-left: 16px;">函数数:</span><span class="stat-value">{result['meta']['total_functions']}</span>
  <span class="stat-label" style="margin-left: 16px;">入口点:</span><span class="stat-value">{result['meta']['entry_points']}</span>
  <span class="stat-label" style="margin-left: 16px;">数据流:</span><span class="stat-value">{len(flows)}</span>
</div>

<div class="legend">
  <div class="legend-item"><div class="legend-box entry"></div><span>入口点</span></div>
  <div class="legend-item"><div class="legend-box normal"></div><span>普通函数</span></div>
  <div class="legend-item"><div class="legend-line-wrapper"><div class="legend-line"></div></div><span>数据流动</span></div>
</div>

<div id="flowchart-container" class="flowchart-container"></div>

<script>
const data = {json.dumps(result, ensure_ascii=False)};
const container = document.getElementById('flowchart-container');

if (!data.data_flows || data.data_flows.length === 0) {{
  container.innerHTML = '<div class="empty-state">暂无数据流</div>';
}} else {{
  data.data_flows.slice(0, 5).forEach((flow, idx) => {{
    const title = document.createElement('div');
    title.style.cssText = 'font-size: 16px; color: var(--accent); font-weight: 600; margin: 20px 0 10px;';
    title.textContent = `数据流 #${{idx + 1}}: ${{flow.entry_point}} (${{flow.steps.length}} 步)`;
    container.appendChild(title);
    
    const flowRow = document.createElement('div');
    flowRow.className = 'flow-row';
    
    flow.steps.forEach((stepId, stepIdx) => {{
      const func = data.functions[stepId];
      if (!func) return;
      
      const funcName = func.name;
      const filePath = func.file;
      
      // Connection area
      if (stepIdx > 0) {{
        const connArea = document.createElement('div');
        connArea.className = 'connection-area';
        connArea.style.height = '60px';
        
        const line = document.createElement('div');
        line.className = 'single-line';
        line.style.top = '10px';
        
        const label = document.createElement('div');
        label.className = 'line-label';
        label.textContent = 'result';
        line.appendChild(label);
        
        connArea.appendChild(line);
        flowRow.appendChild(connArea);
      }}
      
      // Function box
      const funcBox = document.createElement('div');
      funcBox.className = 'func-box' + (func.is_entry_point ? ' entry-point' : '');
      
      let inputsHtml = '';
      if (func.args && func.args.length > 0) {{
        inputsHtml = `<div class="io-section"><div class="io-title">⬇️ 输入</div>` +
          func.args.map(arg => `
            <div class="input-port">
              <div class="port-dot"></div>
              <span class="port-label">${{arg.name}}</span>
              <span class="port-type">${{arg.type}}</span>
            </div>
          `).join('') + '</div>';
      }}
      
      let outputsHtml = '';
      if (func.returns && func.returns !== 'Any') {{
        outputsHtml = `<div class="io-section"><div class="io-title">⬆️ 输出</div>
          <div class="output-port">
            <div class="port-dot"></div>
            <span class="port-label">return</span>
            <span class="port-type">${{func.returns}}</span>
          </div>
        </div>`;
      }}
      
      const stepIndicator = document.createElement('div');
      stepIndicator.className = 'step-indicator';
      stepIndicator.textContent = `Step ${{stepIdx}}`;
      
      const funcHeader = document.createElement('div');
      funcHeader.className = 'func-header';
      funcHeader.innerHTML = `
        <div class="func-title">${{funcName}}</div>
        <div class="func-file">${{filePath}}:${{func.line_start}}</div>
      `;
      
      funcBox.appendChild(stepIndicator);
      funcBox.appendChild(funcHeader);
      if (inputsHtml) funcBox.insertAdjacentHTML('beforeend', inputsHtml);
      if (outputsHtml) funcBox.insertAdjacentHTML('beforeend', outputsHtml);
      
      flowRow.appendChild(funcBox);
    }});
    
    container.appendChild(flowRow);
    
    const separator = document.createElement('hr');
    separator.style.cssText = 'border: none; border-top: 1px solid var(--border); margin: 40px 0; width: 100%;';
    container.appendChild(separator);
  }});
}}
</script>
</body>
</html>'''
    
    Path(output_path).write_text(html, encoding='utf-8')
    print(f"✅ 生成管线图：{output_path}")


def main():
    """主函数"""
    import sys
    
    root_path = sys.argv[1] if len(sys.argv) > 1 else "."
    out_json = sys.argv[2] if len(sys.argv) > 2 else "deep_analysis.json"
    out_html = sys.argv[3] if len(sys.argv) > 3 else "deep_pipeline.html"
    
    print(f"🔍 开始深度 AST 分析...")
    print(f"   项目根目录：{root_path}")
    
    analyzer = DeepAnalyzer(root_path)
    result = analyzer.analyze_all()
    
    # 保存 JSON
    Path(out_json).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n✅ JSON: {out_json}")
    
    # 生成 HTML
    generate_pipeline_html(result, out_html)
    print(f"✅ HTML: {out_html}")
    
    # 显示统计
    print(f"\n📊 分析结果:")
    print(f"   文件数：{result['meta']['total_files']}")
    print(f"   函数数：{result['meta']['total_functions']}")
    print(f"   入口点：{result['meta']['entry_points']}")
    print(f"   数据流：{len(result['data_flows'])} 条")


if __name__ == '__main__':
    main()
