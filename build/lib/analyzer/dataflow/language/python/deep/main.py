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

from analyzer.dataflow.language.python.deep.variable_info_etc import DataFlowAnalyzer

def main():
    """主函数"""
    import sys
    
    index_path = sys.argv[1] if len(sys.argv) > 1 else "project_index.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "dataflow_analysis.json"
    html_path = sys.argv[3] if len(sys.argv) > 3 else "pipeline_flowchart.html"
    
    print(f"🔍 开始深度数据流分析...")
    print(f"   输入：{index_path}")
    
    analyzer = DataFlowAnalyzer(index_path)
    result = analyzer.analyze_all_flows()
    
    # 写入 JSON 结果
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 生成 HTML 管线图
    analyzer.generate_pipeline_html(html_path)
    
    print(f"\n✅ 完成！")
    print(f"   JSON: {out_path}")
    print(f"   HTML: {html_path}")
    print(f"   分析了 {result['meta']['total_flows']} 条数据流")
    print(f"   覆盖 {result['meta']['entry_points']} 个入口点")
    
    # 显示示例
    if result['flows']:
        print(f"\n📊 示例数据流:")
        flow = result['flows'][0]
        print(f"   入口：{flow['entry_name']}")
        print(f"   深度：{flow['depth']}")
        
        for i, step in enumerate(flow['steps'][:3]):  # 只显示前 3 步
            print(f"\n   Step {i}: {step['function']}")
            print(f"      输入：{step['inputs']}")
            print(f"      输出：{step['outputs']}")
            if step['transformations']:
                print(f"      变换：{step['transformations'][:2]}")

if __name__ == '__main__':
    main()
