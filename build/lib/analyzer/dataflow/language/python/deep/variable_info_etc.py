"""
dataflow_analyzer.py - 深度数据流分析器
========================================
分析函数间的详细数据流：
  - 每个函数的输入参数 (a, b, v)
  - 每个函数的返回值 (c, d)
  - 返回值如何变换后传递给下一个函数
  - 完整的变量级调用链

输出格式:
{
  "flows": [
    {
      "entry": "function_A",
      "steps": [
        {
          "func": "A",
          "inputs": [{"name": "a", "type": "str", "source": "user_input"}, ...],
          "outputs": [{"name": "c", "type": "User"}, {"name": "d", "type": "str"}],
          "transformations": [
            {"from": "c", "to": "B.user", "transform": "User.validate()"},
            {"from": "d", "to": "E.token", "transform": "base64.encode()"}
          ]
        },
        {
          "func": "B",
          "inputs": [...],
          "outputs": [...],
          ...
        }
      ]
    }
  ]
}
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from analyzer.dataflow.language.python.deep.data_flow_step import DataFlowStep

@dataclass
class VariableInfo:
    """变量信息"""
    name: str
    var_type: str           # 推断的类型
    source: str             # 来源：参数/返回值/字面量
    line: int
    transformed_by: Optional[str] = None  # 经过了什么变换

@dataclass
class FunctionDataFlow:
    """单个函数的数据流"""
    func_id: str
    file: str
    line_start: int
    line_end: int
    
    # 输入
    inputs: List[VariableInfo] = field(default_factory=list)
    
    # 输出（返回值）
    outputs: List[VariableInfo] = field(default_factory=list)
    
    # 内部变量变换
    transformations: List[Dict] = field(default_factory=list)
    # 格式：{"from_var": "c", "to_var": "result", "operation": "User.validate()", "line": 45}
    
    # 调用的其他函数
    calls: List[Dict] = field(default_factory=list)

class DataFlowAnalyzer:
    """深度数据流分析器"""
    
    def __init__(self, project_index_path: str):
        self.index = json.loads(Path(project_index_path).read_text())
        self.all_funcs = {}  # func_id -> func_info
        self.project_root = Path(self.index['meta']['root'])
        
        # 构建函数索引
        for mod in self.index['modules']:
            for feat in mod['features']:
                for fn in feat['functions']:
                    self.all_funcs[fn['id']] = fn
    
    def analyze_all_flows(self) -> Dict:
        """分析所有数据流"""
        flows = []
        
        # 从每个入口点开始追踪
        for entry_point in self.index['entry_points']:
            flow = self.trace_flow_from(entry_point)
            if flow and len(flow['steps']) > 1:
                flows.append(flow)
        
        return {
            "meta": {
                "total_flows": len(flows),
                "entry_points": len(self.index['entry_points']),
            },
            "flows": flows
        }
    
    def generate_pipeline_html(self, output_path: str):
        """生成管线流程图 HTML"""
        result = self.analyze_all_flows()
        
        html = '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>数据流管线图</title>
<style>
:root {
  --bg: #0f1117;
  --bg2: #161b22;
  --bg3: #1c2128;
  --border: #30363d;
  --border2: #4a5057;
  --text: #e6edf3;
  --text2: #848d97;
  --text3: #6e7681;
  --accent: #58a6ff;
  --green: #3fb950;
  --purple: #bc8cff;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { 
  background: var(--bg); 
  color: var(--text); 
  font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace; 
  padding: 30px;
  overflow-x: auto;
}
h1 { font-size: 20px; margin-bottom: 10px; color: var(--accent); }
p { color: var(--text3); font-size: 12px; margin-bottom: 20px; }
.flowchart-container { display: flex; flex-direction: column; gap: 60px; padding: 20px; min-width: max-content; }
.flow-row { display: flex; align-items: flex-start; gap: 0; position: relative; padding-left: 20px; }
.step-indicator { position: absolute; left: -60px; top: 50%; transform: translateY(-50%); font-size: 11px; color: var(--text3); background: var(--bg2); padding: 6px 10px; border-radius: 4px; white-space: nowrap; border: 1px solid var(--border); }
.func-box { background: var(--bg2); border: 2px solid var(--border); border-radius: 6px; min-width: 220px; max-width: 280px; position: relative; transition: all 0.2s; cursor: pointer; z-index: 1; }
.func-box:hover { border-color: var(--accent); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(88, 166, 255, 0.2); }
.func-box.entry-point { border-color: var(--green); background: rgba(63, 185, 80, 0.05); }
.func-header { padding: 10px 12px; border-bottom: 1px solid var(--border); background: var(--bg3); }
.func-title { font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 4px; }
.func-file { font-size: 9px; color: var(--text3); }
.io-section { padding: 8px 12px; }
.io-title { font-size: 9px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
.input-port, .output-port { display: flex; align-items: center; gap: 6px; padding: 4px 0; position: relative; }
.port-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
.output-port .port-dot { background: var(--green); }
.port-label { font-size: 10px; color: var(--text); }
.port-type { font-size: 9px; color: var(--purple); margin-left: 4px; }
.connection-area { width: 80px; position: relative; flex-shrink: 0; }
.single-line { position: absolute; height: 2px; background: var(--border2); left: 0; right: 0; }
.single-line::after { content: ''; position: absolute; right: 0; top: 50%; transform: translateY(-50%); border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 8px solid var(--border2); }
.line-label { position: absolute; top: -16px; left: 50%; transform: translateX(-50%); font-size: 9px; color: var(--text2); background: var(--bg); padding: 2px 5px; border-radius: 3px; white-space: nowrap; border: 1px solid var(--border); }
.transform-annotation { position: absolute; top: -25px; left: 50%; transform: translateX(-50%); font-size: 9px; color: var(--amber); background: var(--bg2); padding: 3px 8px; border-radius: 4px; border: 1px solid var(--border); white-space: nowrap; z-index: 2; }
.legend { display: flex; gap: 24px; padding: 12px 16px; background: var(--bg2); border-radius: 8px; font-size: 11px; margin-bottom: 20px; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 8px; }
.legend-box { width: 24px; height: 24px; border-radius: 4px; border: 2px solid; }
.legend-box.normal { border-color: var(--border); background: var(--bg2); }
.legend-box.entry { border-color: var(--green); background: rgba(63, 185, 80, 0.05); }
.legend-line-wrapper { position: relative; width: 40px; height: 20px; }
.legend-line { position: absolute; top: 50%; left: 0; right: 0; height: 2px; background: var(--border2); }
.legend-line::after { content: ''; position: absolute; right: 0; top: 50%; transform: translateY(-50%); border-top: 4px solid transparent; border-bottom: 4px solid transparent; border-left: 6px solid var(--border2); }
.empty-state { text-align: center; padding: 60px; color: var(--text3); font-size: 13px; }
.stat { background: var(--bg2); padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: inline-block; }
.stat-label { font-size: 11px; color: var(--text3); margin-right: 12px; }
.stat-value { font-size: 14px; color: var(--accent); font-weight: 600; }
</style>
</head>
<body>
<h1>🔗 数据流管线图</h1>
<p>函数 = 方块 | 数据 = 独立连线 | 一输入一线 | 一输出一线</p>
<div class="stat">
  <span class="stat-label">数据流总数:</span><span class="stat-value">''' + str(len(result['flows'])) + '''</span>
</div>
<div class="legend">
  <div class="legend-item"><div class="legend-box entry"></div><span>入口点</span></div>
  <div class="legend-item"><div class="legend-box normal"></div><span>普通函数</span></div>
  <div class="legend-item"><div class="legend-line-wrapper"><div class="legend-line"></div></div><span>数据流动</span></div>
</div>
<div id="flowchart-container" class="flowchart-container"></div>
<script>
const data = ''' + json.dumps(result, ensure_ascii=False) + ''';
const container = document.getElementById('flowchart-container');
if (!data.flows || data.flows.length === 0) {
  container.innerHTML = '<div class="empty-state">暂无数据流</div>';
} else {
  data.flows.slice(0, 5).forEach((flow, idx) => {
    const title = document.createElement('div');
    title.style.cssText = 'font-size: 16px; color: var(--accent); font-weight: 600; margin: 20px 0 10px;';
    title.textContent = `数据流 #${idx + 1}: ${flow.entry_name} (深度：${flow.depth})`;
    container.appendChild(title);
    const flowRow = document.createElement('div');
    flowRow.className = 'flow-row';
    flow.steps.forEach((step, stepIdx) => {
      const funcName = step.function.split('.').pop();
      const filePath = step.function.replace(/\\./g, '/').replace(/\\.py$/, '');
      if (stepIdx > 0) {
        const connArea = document.createElement('div');
        connArea.className = 'connection-area';
        const maxPorts = Math.max(
          (flow.steps[stepIdx - 1].outputs || []).length,
          (step.inputs || []).length
        );
        const portSpacing = 28;
        const totalHeight = maxPorts * portSpacing;
        connArea.style.height = `${Math.max(totalHeight, 60)}px`;
        (step.inputs || []).forEach((inp, i) => {
          const line = document.createElement('div');
          line.className = 'single-line';
          line.style.top = `${i * portSpacing + 10}px`;
          const label = document.createElement('div');
          label.className = 'line-label';
          label.textContent = inp.name;
          line.appendChild(label);
          connArea.appendChild(line);
        });
        flowRow.appendChild(connArea);
      }
      const funcBox = document.createElement('div');
      funcBox.className = 'func-box' + (stepIdx === 0 ? ' entry-point' : '');
      let inputsHtml = '';
      if (step.inputs && step.inputs.length > 0) {
        inputsHtml = `<div class="io-section"><div class="io-title">⬇️ 输入</div>` +
          step.inputs.map(inp => `
            <div class="input-port" style="top: ${(step.inputs.indexOf(inp)) * 28}px">
              <div class="port-dot"></div>
              <span class="port-label">${inp.name}</span>
              <span class="port-type">${inp.type}</span>
            </div>
          `).join('') + '</div>';
      }
      let outputsHtml = '';
      if (step.outputs && step.outputs.length > 0) {
        outputsHtml = `<div class="io-section"><div class="io-title">⬆️ 输出</div>` +
          step.outputs.map(out => `
            <div class="output-port">
              <div class="port-dot"></div>
              <span class="port-label">${out.name}</span>
              <span class="port-type">${out.type}</span>
            </div>
          `).join('') + '</div>';
      }
      let transformHtml = '';
      if (step.transformations && step.transformations.length > 0) {
        const t = step.transformations[0];
        transformHtml = `<div class="transform-annotation">🔄 ${t.from_var} → ${t.to_var}</div>`;
      }
      funcBox.innerHTML = `
        ${transformHtml}
        <div class="step-indicator">Step ${stepIdx}</div>
        <div class="func-header">
          <div class="func-title">${funcName}</div>
          <div class="func-file">${filePath}.py</div>
        </div>
        ${inputsHtml}
        ${outputsHtml}
      `;
      flowRow.appendChild(funcBox);
    });
    container.appendChild(flowRow);
    const separator = document.createElement('hr');
    separator.style.cssText = 'border: none; border-top: 1px solid var(--border); margin: 40px 0; width: 100%;';
    container.appendChild(separator);
  });
}
</script>
</body>
</html>'''
        
        Path(output_path).write_text(html, encoding='utf-8')
        print(f"✅ 生成管线图：{output_path}")
    
    def trace_flow_from(self, entry_func_id: str, max_depth: int = 10) -> Optional[Dict]:
        """从入口函数开始追踪数据流"""
        
        if entry_func_id not in self.all_funcs:
            return None
        
        steps = []
        visited = set()
        current_func_id = entry_func_id
        step_index = 0
        
        while current_func_id and step_index < max_depth:
            if current_func_id in visited:
                break  # 避免循环
            visited.add(current_func_id)
            
            # 解析这个函数的详细数据流
            func_info = self.all_funcs[current_func_id]
            flow_data = self.analyze_function_dataflow(func_info)
            
            if not flow_data:
                break
            
            step = DataFlowStep(
                step_index=step_index,
                function=current_func_id,
                inputs=[{'name': i.name, 'type': i.var_type, 'source': i.source} 
                        for i in flow_data.inputs],
                outputs=[{'name': o.name, 'type': o.var_type} 
                         for o in flow_data.outputs],
                transformations=flow_data.transformations
            )
            
            steps.append(step)
            
            # 找到下一个函数（通过调用关系）
            next_func = self.find_next_function(flow_data)
            if next_func:
                step.next_step = next_func
                current_func_id = next_func
                step_index += 1
            else:
                break
        
        if not steps:
            return None
        
        entry_func = self.all_funcs[entry_func_id]
        return {
            "entry": entry_func_id,
            "entry_name": entry_func['name'],
            "depth": len(steps),
            "steps": [self._step_to_dict(s) for s in steps]
        }
    
    def analyze_function_dataflow(self, func_info: Dict) -> Optional[FunctionDataFlow]:
        """分析单个函数的详细数据流"""
        
        file_path = self.project_root / func_info['file']
        if not file_path.exists():
            return None
        
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source)
            
            # 找到目标函数
            func_node = self.find_function_node(tree, func_info)
            if not func_node:
                return None
            
            return self.extract_dataflow(func_node, func_info, source)
            
        except Exception as e:
            print(f"❌ 分析失败 {func_info['file']}:{func_info['name']} - {e}")
            return None
    
    def find_function_node(self, tree: ast.AST, func_info: Dict):
        """在 AST 中找到函数节点"""
        parts = func_info['qualified'].split('.')
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == parts[-1]:
                    # 检查行号是否匹配
                    if node.lineno >= func_info['source_lines'][0] and \
                       node.lineno <= func_info['source_lines'][1]:
                        return node
            
            # 如果是类方法
            elif isinstance(node, ast.ClassDef):
                if node.name == parts[0] and len(parts) > 1:
                    for child in ast.walk(node):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if child.name == parts[-1]:
                                if child.lineno >= func_info['source_lines'][0]:
                                    return child
        
        return None
    
    def extract_dataflow(self, func_node: ast.FunctionDef, 
                         func_info: Dict, source: str) -> FunctionDataFlow:
        """从 AST 提取数据流信息"""
        
        result = FunctionDataFlow(
            func_id=func_info['id'],
            file=func_info['file'],
            line_start=func_node.lineno,
            line_end=func_node.end_lineno or func_node.lineno + 10
        )
        
        # 1. 提取输入参数
        for arg in func_node.args.args:
            arg_type = self._get_annotation_type(arg.annotation)
            result.inputs.append(VariableInfo(
                name=arg.arg,
                var_type=arg_type,
                source="parameter",
                line=func_node.lineno
            ))
        
        # 2. 提取返回值类型
        if func_node.returns:
            return_type = self._get_annotation_type(func_node.returns)
            # 可能有多个返回值 (tuple)
            if return_type.startswith('Tuple') or return_type.startswith('tuple'):
                # 解析 Tuple[type1, type2, ...]
                inner = return_type[6:-1]  # 去掉 "Tuple[" 和 "]"
                types = [t.strip() for t in inner.split(',')]
                for i, t in enumerate(types):
                    result.outputs.append(VariableInfo(
                        name=f"ret_{i}",
                        var_type=t,
                        source="return",
                        line=func_node.lineno
                    ))
            else:
                result.outputs.append(VariableInfo(
                    name="ret_0",
                    var_type=return_type,
                    source="return",
                    line=func_node.lineno
                ))
        
        # 3. 遍历函数体，找变量赋值和调用
        self._extract_body_dataflow(func_node, result, source)
        
        return result
    
    def _extract_body_dataflow(self, func_node: ast.FunctionDef, 
                                result: FunctionDataFlow, source: str):
        """提取函数体内的数据流"""
        
        lines = source.split('\n')
        
        for node in ast.walk(func_node):
            # 变量赋值
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_type = self._infer_type(node.value)
                        result.transformations.append({
                            "from_var": self._get_value_source(node.value),
                            "to_var": target.id,
                            "operation": "assignment",
                            "line": node.lineno
                        })
            
            # 函数调用
            elif isinstance(node, ast.Call):
                call_info = self._extract_call_info(node, lines)
                if call_info:
                    result.calls.append(call_info)
                    
                    # 记录返回值的使用
                    if isinstance(node.parent if hasattr(node, 'parent') else node, ast.Assign):
                        assign_node = node.parent
                        if isinstance(assign_node.targets[0], ast.Name):
                            result.transformations.append({
                                "from_var": f"{call_info['target']}()",
                                "to_var": assign_node.targets[0].id,
                                "operation": "call_return",
                                "line": node.lineno
                            })
    
    def _extract_call_info(self, node: ast.Call, lines: List[str]) -> Optional[Dict]:
        """提取函数调用信息"""
        
        # 获取被调用函数名
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        else:
            return None
        
        # 获取参数
        args = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                args.append(arg.id)
            elif isinstance(arg, ast.Constant):
                args.append(str(arg.value)[:20])  # 限制长度
        
        return {
            "target": func_name,
            "args": args,
            "line": node.lineno,
            "code_snippet": lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        }
    
    def _get_annotation_type(self, annotation) -> str:
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
                    params = ', '.join(self._get_annotation_type(e) 
                                      for e in annotation.slice.elts)
                else:
                    params = self._get_annotation_type(annotation.slice)
                return f"{base}[{params}]"
        
        return "Any"
    
    def _infer_type(self, node) -> str:
        """推断表达式的类型"""
        if isinstance(node, ast.Constant):
            return type(node.value).__name__
        elif isinstance(node, ast.List):
            return "list"
        elif isinstance(node, ast.Dict):
            return "dict"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return f"{node.func.id}()"
        elif isinstance(node, ast.Name):
            return f"var:{node.id}"
        
        return "Any"
    
    def _get_value_source(self, node) -> str:
        """获取值的来源"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return f"literal:{node.value}"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                return f"{node.func.attr}()"
            elif isinstance(node.func, ast.Name):
                return f"{node.func.id}()"
        
        return "unknown"
    
    def find_next_function(self, flow_data: FunctionDataFlow) -> Optional[str]:
        """根据调用关系找到下一个函数"""
        
        if not flow_data.calls:
            return None
        
        # 找第一个在项目内的调用
        for call in flow_data.calls:
            target = call['target']
            
            # 尝试在已知函数中查找
            for func_id, func_info in self.all_funcs.items():
                if func_info['name'] == target:
                    return func_id
        
        # 如果找不到精确匹配，使用 call_graph
        if flow_data.func_id in self.index.get('call_graph', {}):
            calls = self.index['call_graph'][flow_data.func_id].get('calls', [])
            for call_id in calls:
                if call_id in self.all_funcs:
                    return call_id
        
        return None
    
    def _step_to_dict(self, step: DataFlowStep) -> Dict:
        """将步骤转换为字典"""
        return {
            "step": step.step_index,
            "function": step.function,
            "inputs": step.inputs,
            "outputs": step.outputs,
            "transformations": step.transformations,
            "next": step.next_step
        }
