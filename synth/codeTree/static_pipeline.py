"""
static_pipeline.py - 生成静态 HTML（不依赖 JavaScript）
"""

import json
from pathlib import Path


def generate_static_pipeline(result, output_path):
    """生成静态 HTML，所有内容在服务器端生成"""
    
    flows = result['data_flows']
    functions = result['functions']
    meta = result['meta']
    
    html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>精确数据流管线图（静态版）</title>
<style>
:root {{ --bg: #0f1117; --bg2: #161b22; --bg3: #1c2128; --border: #30363d; --text: #e6edf3; --text2: #848d97; --text3: #6e7681; --accent: #58a6ff; --green: #3fb950; --purple: #bc8cff; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: 'SF Mono', monospace; padding: 30px; overflow-x: auto; }}
h1 {{ font-size: 20px; margin-bottom: 10px; color: var(--accent); }}
p {{ color: var(--text3); font-size: 12px; margin-bottom: 20px; }}
.stat {{ background: var(--bg2); padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: inline-block; }}
.stat-label {{ font-size: 11px; color: var(--text3); margin-right: 12px; }}
.stat-value {{ font-size: 14px; color: var(--accent); font-weight: 600; }}
.flowchart-container {{ display: flex; flex-direction: column; gap: 60px; padding: 20px; min-width: max-content; }}
.flow-row {{ display: flex; align-items: flex-start; gap: 0; position: relative; padding-left: 20px; }}
.step-indicator {{ position: absolute; left: -60px; top: 50%; transform: translateY(-50%); font-size: 11px; color: var(--text3); background: var(--bg2); padding: 6px 10px; border-radius: 4px; white-space: nowrap; border: 1px solid var(--border); }}
.func-box {{ background: var(--bg2); border: 2px solid var(--border); border-radius: 6px; min-width: 220px; max-width: 280px; position: relative; z-index: 1; }}
.func-box.entry-point {{ border-color: var(--green); background: rgba(63, 185, 80, 0.05); }}
.func-header {{ padding: 10px 12px; border-bottom: 1px solid var(--border); background: var(--bg3); }}
.func-title {{ font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 4px; }}
.func-file {{ font-size: 9px; color: var(--text3); }}
.io-section {{ padding: 8px 12px; }}
.io-title {{ font-size: 9px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
.input-port, .output-port {{ display: flex; align-items: center; gap: 6px; padding: 6px 0; }}
.port-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }}
.output-port .port-dot {{ background: var(--green); }}
.port-label {{ font-size: 10px; color: var(--text); }}
.port-type {{ font-size: 9px; color: var(--purple); margin-left: 4px; }}
.connection-area {{ width: 80px; position: relative; flex-shrink: 0; }}
.single-line {{ position: absolute; height: 2px; background: var(--border); left: 0; right: 0; }}
.line-label {{ position: absolute; top: -16px; left: 50%; transform: translateX(-50%); font-size: 9px; color: var(--text2); background: var(--bg); padding: 2px 5px; border-radius: 3px; white-space: nowrap; border: 1px solid var(--border); }}
.same-file-badge {{ display: inline-block; padding: 2px 6px; background: rgba(210, 153, 34, 0.2); color: #d29922; border-radius: 3px; font-size: 9px; margin-left: 6px; }}
</style>
</head>
<body>
<h1>🔗 精确数据流管线图（静态版）</h1>
<p>同文件内追踪 | 一参数一线 | 端口精确对齐</p>

<div class="stat">
  <span class="stat-label">文件数:</span><span class="stat-value">{meta['total_files']}</span>
  <span class="stat-label" style="margin-left: 16px;">函数数:</span><span class="stat-value">{meta['total_functions']}</span>
  <span class="stat-label" style="margin-left: 16px;">入口点:</span><span class="stat-value">{meta['entry_points']}</span>
  <span class="stat-label" style="margin-left: 16px;">数据流:</span><span class="stat-value">{len(flows)}</span>
</div>

<div class="flowchart-container">
'''
    
    # Generate ALL flows statically (not just first 5)
    for idx, flow in enumerate(flows):
        html += f'<div style="font-size: 16px; color: var(--accent); font-weight: 600; margin: 20px 0 10px;">数据流 #{idx + 1}: {flow["entry_point"]} ({len(flow["steps"])} 步)</div>\n'
        html += '<div class="flow-row">\n'
        
        for step_idx, step_id in enumerate(flow['steps']):
            func = functions.get(step_id)
            if not func:
                continue
            
            # Connection area
            if step_idx > 0:
                port_spacing = 32
                input_count = len(func.get('args', []))
                total_height = max(input_count * port_spacing, 60)
                
                html += f'<div class="connection-area" style="height: {total_height}px;">\n'
                
                # Create lines for each input
                for i, arg in enumerate(func.get('args', [])):
                    top_pos = i * port_spacing + 10
                    html += f'  <div class="single-line" style="top: {top_pos}px;"><div class="line-label">{arg["name"]}</div></div>\n'
                
                html += '</div>\n'
            
            # Function box
            is_entry = func.get('is_entry_point', False)
            same_file_badge = ''
            if step_idx > 0:
                prev_id = flow['steps'][step_idx - 1]
                prev_func = functions.get(prev_id)
                if prev_func and prev_func.get('file') == func.get('file'):
                    same_file_badge = '<span class="same-file-badge">📄 同文件</span>'
            
            entry_class = 'entry-point' if is_entry else ''
            
            html += f'<div class="func-box {entry_class}">\n'
            html += f'  <div class="step-indicator">Step {step_idx}</div>\n'
            html += f'  <div class="func-header">\n'
            html += f'    <div class="func-title">{func["name"]}{same_file_badge}</div>\n'
            html += f'    <div class="func-file">{func["file"]}:{func["line_start"]}</div>\n'
            html += f'  </div>\n'
            
            # Input ports
            if func.get('args'):
                html += '  <div class="io-section"><div class="io-title">⬇️ 输入</div>\n'
                for arg in func['args']:
                    html += f'    <div class="input-port"><div class="port-dot"></div><span class="port-label">{arg["name"]}</span><span class="port-type">{arg["type"]}</span></div>\n'
                html += '  </div>\n'
            
            # Output port
            if func.get('returns') and func['returns'] != 'Any':
                html += '  <div class="io-section"><div class="io-title">⬆️ 输出</div>\n'
                html += f'    <div class="output-port"><div class="port-dot"></div><span class="port-label">return</span><span class="port-type">{func["returns"]}</span></div>\n'
                html += '  </div>\n'
            
            html += '</div>\n'
        
        html += '</div>\n'
        html += '<hr style="border: none; border-top: 1px solid var(--border); margin: 40px 0;">\n'
    
    html += '''</div>
</body>
</html>'''
    
    Path(output_path).write_text(html, encoding='utf-8')
    print(f"✅ 生成静态管线图：{output_path}")


if __name__ == '__main__':
    import sys
    json_path = sys.argv[1] if len(sys.argv) > 1 else "deep_analysis.json"
    html_path = sys.argv[2] if len(sys.argv) > 2 else "static_pipeline.html"
    
    result = json.loads(Path(json_path).read_text())
    generate_static_pipeline(result, html_path)
