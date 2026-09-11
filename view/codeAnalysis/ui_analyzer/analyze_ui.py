"""
UI 交互分析器
通用工具：分析按钮事件、数据流、函数调用链
"""
import re
import os
import sys
from typing import Dict, List, Optional

from view.codeAnalysis.ui_analyzer.ui_interaction_analyzer import UIInteractionAnalyzer

def analyze_ui(source_file: str, output_file: str = None) -> UIInteractionAnalyzer:
    """分析 UI 交互"""
    analyzer = UIInteractionAnalyzer(source_file)

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(analyzer.generate_full_report())
        print(f'报告已保存: {output_file}')
    else:
        print(analyzer.generate_full_report())

    return analyzer

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python ui_analyzer.py <源文件> [输出文件]')
        print('示例: python ui_analyzer.py extension/src/sidebar_provider.ts docs/ui报告.md')
        sys.exit(1)

    source = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None
    analyze_ui(source, output)
