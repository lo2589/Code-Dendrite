"""
visualizer.py - 数据流可视化 (Easy L4-007)
===========================================
生成HTML可视化。
"""

import json
from pathlib import Path
from typing import List, Dict, Optional

from base.dataFlow.types import FunctionDataFlow, CallChain
from relate.dataFlow.analyzer import analyze_function_flow


def generate_dataflow_html(
    project_index_path: str,
    output_path: str,
    max_flows: int = 10
):
    """
    生成数据流HTML可视化 (Easy L4-007)
    
    参数:
        project_index_path: 项目索引JSON路径
        output_path: 输出HTML路径
        max_flows: 最大显示流数量
    """
    # 读取项目索引
    try:
        index_data = json.loads(Path(project_index_path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        index_data = {"modules": [], "entry_points": []}
    
    # 分析数据流
    flows = []
    for entry_point in index_data.get('entry_points', [])[:max_flows]:
        if ':' in entry_point:
            file_path, func_name = entry_point.rsplit(':', 1)
            flow = analyze_function_flow(file_path, func_name)
            if flow:
                flows.append({
                    "entry": entry_point,
                    "entry_name": func_name,
                    "depth": 1,
                    "steps": [{
                        "step": 0,
                        "function": entry_point,
                        "inputs": [i.to_dict() for i in flow.inputs],
                        "outputs": [o.to_dict() for o in flow.outputs],
                        "transformations": [t.to_dict() for t in flow.transformations]
                    }]
                })
    
    result = {
        "meta": {
            "total_flows": len(flows),
            "entry_points": len(index_data.get('entry_points', []))
        },
        "flows": flows
    }
    
    html = _generate_html_template(result)
    Path(output_path).write_text(html, encoding='utf-8')
    print(f"✅ 生成数据流图：{output_path}")


def generate_function_flow_html(
    file_path: str,
    function_name: str,
    output_path: str
):
    """
    生成单个函数的数据流HTML
    
    参数:
        file_path: 文件路径
        function_name: 函数名
        output_path: 输出路径
    """
    flow = analyze_function_flow(file_path, function_name)
    if not flow:
        html = "<html><body><p>无法分析函数</p></body></html>"
        Path(output_path).write_text(html, encoding='utf-8')
        return
    
    result = {
        "meta": {"total_flows": 1},
        "flows": [{
            "entry": flow.func_id,
            "entry_name": function_name,
            "depth": 1,
            "steps": [{
                "step": 0,
                "function": flow.func_id,
                "inputs": [i.to_dict() for i in flow.inputs],
                "outputs": [o.to_dict() for o in flow.outputs],
                "transformations": [t.to_dict() for t in flow.transformations]
            }]
        }]
    }
    
    html = _generate_html_template(result)
    Path(output_path).write_text(html, encoding='utf-8')


def _generate_html_template(data: Dict) -> str:
    """生成HTML模板"""
    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>数据流分析</title>
<style>
:root {{
  --bg: #0f1117;
  --bg2: #161b22;
  --bg3: #1c2128;
  --border: #30363d;
  --text: #e6edf3;
  --text2: #848d97;
  --accent: #58a6ff;
  --green: #3fb950;
  --purple: #bc8cff;
  --yellow: #d29922;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ 
  background: var(--bg); 
  color: var(--text); 
  font-family: 'SF Mono', 'Cascadia Code', monospace; 
  padding: 30px;
}}
h1 {{ font-size: 20px; margin-bottom: 10px; color: var(--accent); }}
.stats {{ 
  background: var(--bg2); 
  padding: 12px 16px; 
  border-radius: 8px; 
  margin-bottom: 20px;
  display: inline-block;
}}
.flow-card {{
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 20px;
  overflow: hidden;
}}
.flow-header {{
  padding: 12px 16px;
  background: var(--bg3);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  color: var(--accent);
}}
.flow-body {{ padding: 16px; }}
.section {{
  margin-bottom: 16px;
}}
.section-title {{
  font-size: 12px;
  color: var(--text2);
  text-transform: uppercase;
  margin-bottom: 8px;
}}
.var-list {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}
.var-item {{
  background: var(--bg3);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}}
.var-name {{ color: var(--accent); }}
.var-type {{ color: var(--purple); margin-left: 4px; }}
.transform {{
  background: var(--bg3);
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 8px;
  font-size: 12px;
}}
.transform .arrow {{ color: var(--yellow); }}
.empty {{ color: var(--text2); font-style: italic; }}
</style>
</head>
<body>
<h1>🔍 数据流分析</h1>
<div class="stats">
  <span>分析了 <strong style="color: var(--accent)">{data["meta"]["total_flows"]}</strong> 个数据流</span>
</div>

<div id="flows">
''' + _generate_flow_cards(data["flows"]) + '''
</div>
</body>
</html>'''


def _generate_flow_cards(flows: List[Dict]) -> str:
    """生成流程卡片HTML"""
    if not flows:
        return '<p class="empty">暂无数据流</p>'
    
    cards = []
    for flow in flows:
        step = flow["steps"][0] if flow.get("steps") else {}
        
        # 输入
        inputs_html = ""
        if step.get("inputs"):
            inputs_html = "".join([
                f'<span class="var-item"><span class="var-name">{i["name"]}</span>'
                f'<span class="var-type">: {i.get("type", "Any")}</span></span>'
                for i in step["inputs"]
            ])
        else:
            inputs_html = '<span class="empty">无参数</span>'
        
        # 输出
        outputs_html = ""
        if step.get("outputs"):
            outputs_html = "".join([
                f'<span class="var-item"><span class="var-name">{o["name"]}</span>'
                f'<span class="var-type">: {o.get("type", "Any")}</span></span>'
                for o in step["outputs"]
            ])
        else:
            outputs_html = '<span class="empty">无返回值</span>'
        
        # 变换
        transforms_html = ""
        if step.get("transformations"):
            transforms_html = "".join([
                f'<div class="transform">'
                f'<span class="var-name">{t["from_var"]}</span>'
                f' <span class="arrow">→</span> '
                f'<span class="var-name">{t["to_var"]}</span>'
                f' <span style="color: var(--text2)">({t.get("operation", "?")})</span>'
                f'</div>'
                for t in step["transformations"][:5]
            ])
        else:
            transforms_html = '<span class="empty">无变换</span>'
        
        card = f'''
<div class="flow-card">
  <div class="flow-header">{flow.get("entry_name", "unknown")}</div>
  <div class="flow-body">
    <div class="section">
      <div class="section-title">⬇️ 输入</div>
      <div class="var-list">{inputs_html}</div>
    </div>
    <div class="section">
      <div class="section-title">⬆️ 输出</div>
      <div class="var-list">{outputs_html}</div>
    </div>
    <div class="section">
      <div class="section-title">🔄 变换</div>
      {transforms_html}
    </div>
  </div>
</div>
'''
        cards.append(card)
    
    return "\n".join(cards)
