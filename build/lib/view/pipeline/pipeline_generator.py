"""
pipeline_generator.py - 工程级安全版本（JSON 与 JS 分离）
"""

import json
from pathlib import Path


def generate_precise_pipeline(result, output_path):
    """生成精确对齐的管线图 - 工业级安全方案"""
    
    flows = result['data_flows']
    
    # CSS 模板
    css_content = '''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>精确数据流管线图</title>
<style>
:root { --bg: #0f1117; --bg2: #161b22; --bg3: #1c2128; --border: #30363d; --border2: #4a5057; --text: #e6edf3; --text2: #848d97; --text3: #6e7681; --accent: #58a6ff; --green: #3fb950; --purple: #bc8cff; --amber: #d29922; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: 'SF Mono', monospace; padding: 30px; overflow-x: auto; }
h1 { font-size: 20px; margin-bottom: 10px; color: var(--accent); }
p { color: var(--text3); font-size: 12px; margin-bottom: 20px; }
.flowchart-container { display: flex; flex-direction: column; gap: 60px; padding: 20px; min-width: max-content; }
.flow-row { display: flex; align-items: flex-start; gap: 0; position: relative; padding-left: 20px; }
.step-indicator { position: absolute; left: -60px; top: 50%; transform: translateY(-50%); font-size: 11px; color: var(--text3); background: var(--bg2); padding: 6px 10px; border-radius: 4px; white-space: nowrap; border: 1px solid var(--border); }
.func-box { background: var(--bg2); border: 2px solid var(--border); border-radius: 6px; min-width: 220px; max-width: 280px; position: relative; z-index: 1; }
.func-box.entry-point { border-color: var(--green); background: rgba(63, 185, 80, 0.05); }
.func-header { padding: 10px 12px; border-bottom: 1px solid var(--border); background: var(--bg3); }
.func-title { font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 4px; }
.func-file { font-size: 9px; color: var(--text3); }
.io-section { padding: 8px 12px; }
.io-title { font-size: 9px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
.input-port, .output-port { display: flex; align-items: center; gap: 6px; padding: 6px 0; }
.port-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
.output-port .port-dot { background: var(--green); }
.port-label { font-size: 10px; color: var(--text); }
.port-type { font-size: 9px; color: var(--purple); margin-left: 4px; }
.connection-area { width: 80px; position: relative; flex-shrink: 0; }
.single-line { position: absolute; height: 2px; background: var(--border2); left: 0; right: 0; }
.line-label { position: absolute; top: -16px; left: 50%; transform: translateX(-50%); font-size: 9px; color: var(--text2); background: var(--bg); padding: 2px 5px; border-radius: 3px; white-space: nowrap; border: 1px solid var(--border); }
.stat { background: var(--bg2); padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; display: inline-block; }
.stat-label { font-size: 11px; color: var(--text3); margin-right: 12px; }
.stat-value { font-size: 14px; color: var(--accent); font-weight: 600; }
.same-file-badge { display: inline-block; padding: 2px 6px; background: rgba(210, 153, 34, 0.2); color: var(--amber); border-radius: 3px; font-size: 9px; margin-left: 6px; }
</style>
</head>
<body>
<h1>🔗 精确数据流管线图（工程级安全版）</h1>
<p>同文件内追踪 | 一参数一线 | 端口精确对齐 | JSON 与 JS 分离</p>

<div class="stat">
  <span class="stat-label">文件数:</span><span class="stat-value" id="stat-files"></span>
  <span class="stat-label" style="margin-left: 16px;">函数数:</span><span class="stat-value" id="stat-funcs"></span>
  <span class="stat-label" style="margin-left: 16px;">入口点:</span><span class="stat-value" id="stat-entry"></span>
  <span class="stat-label" style="margin-left: 16px;">数据流:</span><span class="stat-value" id="stat-flows"></span>
</div>

<div id="flowchart-container" class="flowchart-container"></div>

<!-- ✅ 工程级安全：JSON 单独存放 -->
<script id="data-json" type="application/json">
'''
    
    # JavaScript 模板
    js_content = '''</script>

<script>
const container = document.getElementById('flowchart-container');

try {
  const raw = document.getElementById('data-json').textContent;
  const data = JSON.parse(raw);
  
  console.log('✅ Pipeline loaded');
  console.log('Data:', data);
  
  // Update stats
  document.getElementById('stat-files').textContent = data.meta.total_files;
  document.getElementById('stat-funcs').textContent = data.meta.total_functions;
  document.getElementById('stat-entry').textContent = data.meta.entry_points;
  document.getElementById('stat-flows').textContent = data.data_flows.length;
  
  // ✅ Global state
  let selectedFuncId = null;
  let sidebar = null;
  
  if (!data.data_flows || data.data_flows.length === 0) {
    container.innerHTML = '<div class="empty-state">暂无数据流</div>';
  } else {
    // ✅ 显示所有数据流
    data.data_flows.forEach((flow, idx) => {
      const title = document.createElement('div');
      title.style.cssText = 'font-size: 16px; color: var(--accent); font-weight: 600; margin: 20px 0 10px;';
      title.textContent = '数据流 #' + (idx + 1) + ': ' + flow.entry_point + ' (' + flow.steps.length + ' 步)';
      container.appendChild(title);
      
      const flowRow = document.createElement('div');
      flowRow.className = 'flow-row';
      
      flow.steps.forEach((stepId, stepIdx) => {
        const func = data.functions[stepId];
        if (!func) return;
        
        if (stepIdx > 0) {
          const connArea = document.createElement('div');
          connArea.className = 'connection-area';
          
          const prevFunc = data.functions[flow.steps[stepIdx - 1]];
          const hasReturn = prevFunc && prevFunc.returns && prevFunc.returns !== 'Any';
          const inputCount = func.args ? func.args.length : 0;
          const maxPorts = Math.max(hasReturn ? 1 : 0, inputCount, 1);
          const portSpacing = 32;
          const totalHeight = maxPorts * portSpacing;
          
          connArea.style.height = Math.max(totalHeight, 60) + 'px';
          
          if (func.args && func.args.length > 0) {
            func.args.forEach((arg, i) => {
              const line = document.createElement('div');
              line.className = 'single-line';
              line.style.top = (i * portSpacing + 10) + 'px';
              
              const label = document.createElement('div');
              label.className = 'line-label';
              label.textContent = arg.name;
              line.appendChild(label);
              
              connArea.appendChild(line);
            });
          }
          
          flowRow.appendChild(connArea);
        }
        
        const funcBox = document.createElement('div');
        funcBox.className = 'func-box' + (func.is_entry_point ? ' entry-point' : '');
        funcBox.onclick = function(e) {
          e.stopPropagation();
          console.log('🔍 点击了函数:', func.name);
          selectFunc(func.id || stepId);
        };
        
        let inputsHtml = '';
        if (func.args && func.args.length > 0) {
          inputsHtml = '<div class="io-section"><div class="io-title">⬇️ 输入</div>';
          func.args.forEach((arg, i) => {
            inputsHtml += '<div class="input-port"><div class="port-dot"></div><span class="port-label">' + arg.name + '</span><span class="port-type">' + arg.type + '</span></div>';
          });
          inputsHtml += '</div>';
        }
        
        let outputsHtml = '';
        if (func.returns && func.returns !== 'Any') {
          outputsHtml = '<div class="io-section"><div class="io-title">⬆️ 输出</div><div class="output-port"><div class="port-dot"></div><span class="port-label">return</span><span class="port-type">' + func.returns + '</span></div></div>';
        }
        
        let sameFileHtml = '';
        if (stepIdx > 0) {
          const prevFunc = data.functions[flow.steps[stepIdx - 1]];
          if (prevFunc && prevFunc.file === func.file) {
            sameFileHtml = '<span class="same-file-badge">📄 同文件</span>';
          }
        }
        
        const stepIndicator = document.createElement('div');
        stepIndicator.className = 'step-indicator';
        stepIndicator.textContent = 'Step ' + stepIdx;
        
        const funcHeader = document.createElement('div');
        funcHeader.className = 'func-header';
        funcHeader.innerHTML = '<div class="func-title">' + func.name + sameFileHtml + '</div><div class="func-file">' + func.file + ':' + func.line_start + '</div>';
        
        funcBox.appendChild(stepIndicator);
        funcBox.appendChild(funcHeader);
        if (inputsHtml) funcBox.insertAdjacentHTML('beforeend', inputsHtml);
        if (outputsHtml) funcBox.insertAdjacentHTML('beforeend', outputsHtml);
        
        flowRow.appendChild(funcBox);
      });
      
      container.appendChild(flowRow);
      
      const separator = document.createElement('hr');
      separator.style.cssText = 'border: none; border-top: 1px solid var(--border); margin: 40px 0; width: 100%;';
      container.appendChild(separator);
    });
  }
} catch (e) {
  console.error('💥 JS crashed:', e);
  container.innerHTML = '<div class="empty-state">解析失败：' + e.message + '</div>';
}

// ✅ Select function - reference implementation
function selectFunc(funcId) {
  console.log('📋 选择函数:', funcId);
  selectedFuncId = funcId;
  
  const func = data.functions[funcId];
  if (!func) return;
  
  // Create or show sidebar
  let sidebar = document.getElementById('sidebar');
  if (!sidebar) {
    console.log('🔨 创建侧边栏');
    sidebar = document.createElement('div');
    sidebar.id = 'sidebar';
    sidebar.style.cssText = 'position: fixed; right: 0; top: 0; bottom: 0; width: 400px; background: var(--bg2); border-left: 1px solid var(--border); transform: translateX(100%); transition: transform 0.3s; z-index: 100; overflow-y: auto; box-shadow: -4px 0 12px rgba(0,0,0,0.3);';
    
    const header = document.createElement('div');
    header.style.cssText = 'padding: 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; background: var(--bg2); z-index: 10;';
    header.innerHTML = '<h3 style="font-size: 14px; color: var(--accent); margin: 0;">函数详情</h3><span style="cursor: pointer; color: var(--text3); font-size: 20px; line-height: 1;" onclick="closeSidebar()">×</span>';
    
    const content = document.createElement('div');
    content.id = 'sidebar-content';
    content.style.cssText = 'padding: 16px;';
    
    sidebar.appendChild(header);
    sidebar.appendChild(content);
    document.body.appendChild(sidebar);
  }
  
  // Render content
  const content = document.getElementById('sidebar-content');
  renderSidebarContent(content, func);
  
  // Animate in
  setTimeout(function() {
    sidebar.style.transform = 'translateX(0)';
  }, 10);
}

function renderSidebarContent(container, func) {
  // Args HTML
  let argsHtml = '<div style="font-size: 12px; color: var(--text2);">无参数</div>';
  if (func.args && func.args.length > 0) {
    argsHtml = '<div style="display: flex; flex-direction: column; gap: 4px;">';
    for (let i = 0; i < func.args.length; i++) {
      const arg = func.args[i];
      argsHtml += '<div style="font-size: 11px; background: var(--bg3); padding: 6px 10px; border-radius: 4px;">';
      argsHtml += '<span style="color: var(--accent); font-weight: 600;">' + arg.name + '</span>';
      if (arg.type) {
        argsHtml += '<span style="color: var(--purple); margin-left: 6px;">' + arg.type + '</span>';
      }
      argsHtml += '</div>';
    }
    argsHtml += '</div>';
  }
  
  // Returns HTML
  const returnsHtml = (func.returns && func.returns !== 'Any') 
    ? '<div style="font-size: 12px; color: var(--green);">' + func.returns + '</div>'
    : '<div style="font-size: 12px; color: var(--text2);">无返回值 / void</div>';
  
  // Call counts
  const calledByCount = func.called_by ? func.called_by.length : 0;
  const callsCount = func.calls ? func.calls.length : 0;
  
  container.innerHTML = '' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">函数名</div>' +
      '<div style="font-size: 14px; font-weight: 600; color: var(--text);">' + func.name + '</div>' +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">文件路径</div>' +
      '<div style="font-size: 12px; color: var(--text);">' + func.file + ':' + func.line_start + '</div>' +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">签名</div>' +
      '<div style="font-family: monospace; font-size: 11px; color: var(--accent); background: var(--bg3); padding: 12px; border-radius: 4px; border-left: 3px solid var(--accent); word-break: break-all;">' + (func.signature || 'def ' + func.name + '()') + '</div>' +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">输入参数</div>' +
      argsHtml +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">返回值</div>' +
      returnsHtml +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">调用关系</div>' +
      '<div style="font-size: 11px;">' +
        '<div style="margin-bottom: 8px;">' +
          '<span style="color: var(--text3);">被调用:</span>' +
          '<span style="color: var(--text2); margin-left: 6px;">' + calledByCount + ' 个函数</span>' +
        '</div>' +
        '<div>' +
          '<span style="color: var(--text3);">调用:</span>' +
          '<span style="color: var(--text2); margin-left: 6px;">' + callsCount + ' 个函数</span>' +
        '</div>' +
      '</div>' +
    '</div>';
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (sidebar) {
    sidebar.style.transform = 'translateX(100%)';
  }
}

// Close sidebar when clicking outside
document.addEventListener('click', function(e) {
  const sidebar = document.getElementById('sidebar');
  if (sidebar && !sidebar.contains(e.target)) {
    closeSidebar();
  }
});
</script>
    sidebar = document.createElement('div');
    sidebar.id = 'sidebar';
    sidebar.className = 'sidebar';
    sidebar.style.cssText = 'position: fixed; right: 0; top: 0; bottom: 0; width: 400px; background: var(--bg2); border-left: 1px solid var(--border); transform: translateX(100%); transition: transform 0.3s; z-index: 100; overflow-y: auto;';
    
    const header = document.createElement('div');
    header.className = 'sidebar-header';
    header.style.cssText = 'padding: 16px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;';
    header.innerHTML = '<h3 style="font-size: 14px; color: var(--accent); margin: 0;">函数详情</h3><span style="cursor: pointer; color: var(--text3); font-size: 20px;" onclick="closeSidebar()">×</span>';
    
    const content = document.createElement('div');
    content.id = 'sidebar-content';
    content.className = 'sidebar-content';
    content.style.cssText = 'padding: 16px;';
    
    sidebar.appendChild(header);
    sidebar.appendChild(content);
    document.body.appendChild(sidebar);
  }
  
  const content = document.getElementById('sidebar-content');
  
  // 构建参数 HTML
  let argsHtml = '<div style="font-size: 12px; color: var(--text2);">无参数</div>';
  if (func.args && func.args.length > 0) {
    argsHtml = '<div style="display: flex; flex-direction: column; gap: 4px;">';
    for (let i = 0; i < func.args.length; i++) {
      const arg = func.args[i];
      argsHtml += '<div style="font-size: 11px; background: var(--bg3); padding: 6px 10px; border-radius: 4px;">';
      argsHtml += '<span style="color: var(--accent); font-weight: 600;">' + arg.name + '</span>';
      argsHtml += '<span style="color: var(--purple); margin-left: 6px;">' + (arg.type || 'Any') + '</span>';
      argsHtml += '</div>';
    }
    argsHtml += '</div>';
  }
  
  // 返回值 HTML
  const returnsHtml = (func.returns && func.returns !== 'Any') 
    ? '<div style="font-size: 12px; color: var(--green);">' + func.returns + '</div>'
    : '<div style="font-size: 12px; color: var(--text2);">无返回值 / void</div>';
  
  // 调用关系
  const calledByCount = func.called_by ? func.called_by.length : 0;
  const callsCount = func.calls ? func.calls.length : 0;
  
  content.innerHTML = '' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">函数名</div>' +
      '<div style="font-size: 14px; font-weight: 600; color: var(--text);">' + func.name + '</div>' +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">文件路径</div>' +
      '<div style="font-size: 12px; color: var(--text);">' + func.file + ':' + func.line_start + '</div>' +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">签名</div>' +
      '<div style="font-family: monospace; font-size: 11px; color: var(--accent); background: var(--bg3); padding: 12px; border-radius: 4px; border-left: 3px solid var(--accent);">' + (func.signature || 'def ' + func.name + '()') + '</div>' +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">输入参数</div>' +
      argsHtml +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">返回值</div>' +
      returnsHtml +
    '</div>' +
    '<div style="margin-bottom: 20px;">' +
      '<div style="font-size: 10px; color: var(--text3); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;">调用关系</div>' +
      '<div style="font-size: 11px;">' +
        '<div style="margin-bottom: 8px;">' +
          '<span style="color: var(--text3);">被调用:</span>' +
          '<span style="color: var(--text2); margin-left: 6px;">' + calledByCount + ' 个函数</span>' +
        '</div>' +
        '<div>' +
          '<span style="color: var(--text3);">调用:</span>' +
          '<span style="color: var(--text2); margin-left: 6px;">' + callsCount + ' 个函数</span>' +
        '</div>' +
      '</div>' +
    '</div>';
  
  setTimeout(function() {
    sidebar.style.transform = 'translateX(0)';
  }, 10);
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (sidebar) {
    sidebar.style.transform = 'translateX(100%)';
  }
}
</script>
</body>
</html>'''
    
    # 拼接完整 HTML
    html_content = css_content + json.dumps(result, ensure_ascii=False, indent=2) + js_content
    
    Path(output_path).write_text(html_content, encoding='utf-8')
    print(f"✅ 生成精确管线图：{output_path}")


if __name__ == '__main__':
    import sys
    json_path = sys.argv[1] if len(sys.argv) > 1 else "deep_analysis.json"
    html_path = sys.argv[2] if len(sys.argv) > 2 else "precise_pipeline.html"
    
    result = json.loads(Path(json_path).read_text())
    generate_precise_pipeline(result, html_path)
