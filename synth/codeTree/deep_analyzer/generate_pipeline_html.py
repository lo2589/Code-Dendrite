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

from synth.codeTree.deep_analyzer.core import DeepAnalyzer

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
