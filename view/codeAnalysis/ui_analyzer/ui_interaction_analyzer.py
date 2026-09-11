"""
UI 交互分析器
通用工具：分析按钮事件、数据流、函数调用链
"""
import re
import os
import sys
from typing import Dict, List, Optional

class UIInteractionAnalyzer:
    """UI 交互分析器"""

    BUTTON_NAMES = {
        'sendChat': '发送聊天',
        'clearChat': '清空聊天',
        'uploadImage': '上传图片',
        'compressContext': '压缩上下文',
        'onModelChange': '切换模型',
        'refreshBalance': '刷新余额',
        'runNewTask': '运行新任务',
        'openSettings': '打开设置',
        'approveOperation': '审批通过',
        'rejectOperation': '审批拒绝',
        'configureNewModel': '配置新模型',
        'closeModal': '关闭弹窗',
        'saveSettings': '保存设置',
        'refreshStats': '刷新统计',
        'stopAll': '停止所有',
        'pauseAll': '暂停所有',
        'addAgent': '添加Agent',
        'deleteAgent': '删除Agent',
        'toggleAgent': '切换Agent',
        'executeNow': '立即执行',
        'resetForm': '重置表单',
    }

    def __init__(self, source_file: str):
        self.source_file = source_file
        self.source = self._read_source()
        self.handlers = {}
        self.commands = {}
        self._analyze()

    def _read_source(self) -> str:
        with open(self.source_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _get_line_number(self, pos: int) -> int:
        return self.source[:pos].count('\n') + 1

    def _analyze(self):
        self._extract_button_handlers()
        self._extract_postmessage_commands()

    def _extract_button_handlers(self):
        patterns = [
            (r'onclick\s*=\s*["\']?([\w]+)["\']?', 'onclick'),
            (r'onchange\s*=\s*["\']?([\w]+)["\']?', 'onchange'),
            (r'onsubmit\s*=\s*["\']?([\w]+)["\']?', 'onsubmit'),
            (r'oninput\s*=\s*["\']?([\w]+)["\']?', 'oninput'),
        ]

        for pattern, event_type in patterns:
            for match in re.finditer(pattern, self.source):
                name = match.group(1).replace('()', '')
                line_num = self._get_line_number(match.start())
                if name not in self.handlers:
                    self.handlers[name] = {
                        'event': event_type,
                        'line': line_num,
                        'calls': [],
                        'commands': []
                    }

    def _extract_postmessage_commands(self):
        pattern = r'postMessage\s*\(\s*\{[^}]*command\s*:\s*["\']?(\w+)'
        for match in re.finditer(pattern, self.source):
            cmd = match.group(1)
            self.commands[cmd] = self.commands.get(cmd, 0) + 1

    def get_function_body(self, func_name: str) -> Optional[str]:
        patterns = [
            rf'function\s+{re.escape(func_name)}\s*\(',
            rf'const\s+{re.escape(func_name)}\s*=\s*(?:async\s*)?\([^)]*\)\s*=>',
            rf'const\s+{re.escape(func_name)}\s*=\s*(?:async\s*)?function',
            rf'(?:let|var)\s+{re.escape(func_name)}\s*=\s*(?:async\s*)?function',
        ]

        for func_pattern in patterns:
            match = re.search(func_pattern, self.source)
            if match:
                start = match.end()
                brace_depth = 0
                started = False
                for i in range(start, len(self.source)):
                    c = self.source[i]
                    if c == '{':
                        brace_depth += 1
                        started = True
                    elif c == '}':
                        brace_depth -= 1
                        if started and brace_depth == 0:
                            return self.source[start:i]
                    elif c == ';' and not started:
                        return self.source[start:i]
        return None

    def extract_function_calls(self, body: str) -> List[str]:
        if not body:
            return []

        calls = []
        exclude = {
            'if', 'for', 'while', 'switch', 'catch', 'return', 'throw', 'new',
            'else', 'var', 'let', 'const', 'class', 'function', 'import', 'export',
            'try', 'finally', 'delete', 'typeof', 'void', 'in', 'of', 'await'
        }

        patterns = [
            r'(?:^|[^.\w"])(\w+)\s*\([^)]*\)\s*;',
            r'(?:^|[^.\w"])(\w+)\s*\([^)]*\)\s*[{,\n]',
            r'this\.(\w+)\s*\(',
        ]

        for pattern in patterns:
            for m in re.finditer(pattern, body):
                name = m.group(1)
                if name not in exclude:
                    prefix = 'this.' if 'this.' in pattern else ''
                    calls.append(f'{prefix}{name}()')

        seen = set()
        unique = []
        for c in calls:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return unique

    def extract_commands_from_body(self, body: str) -> List[str]:
        if not body:
            return []
        pattern = r'postMessage\s*\(\s*\{[^}]*command\s*:\s*["\']?(\w+)'
        return list(set(m.group(1) for m in re.finditer(pattern, body)))

    def extract_dom_operations(self, body: str) -> List[str]:
        if not body:
            return []
        ops = []
        patterns = [
            (r'getElementById\s*\(\s*["\']?(\w+)', 'getElementById'),
            (r'querySelector\s*\(\s*["\']?([^"\']+)', 'querySelector'),
            (r'createElement\s*\(\s*["\']?(\w+)', 'createElement'),
            (r'addEventListener\s*\(\s*["\']?(\w+)', 'addEventListener'),
        ]
        for pattern, op_type in patterns:
            for m in re.finditer(pattern, body):
                ops.append(f'{op_type}("{m.group(1)}")')
        return ops

    def analyze_handler(self, handler_name: str) -> Dict:
        result = {
            'name': handler_name,
            'display_name': self.BUTTON_NAMES.get(handler_name, handler_name),
            'event': self.handlers.get(handler_name, {}).get('event', 'unknown'),
            'line': self.handlers.get(handler_name, {}).get('line', 0),
            'calls': [],
            'commands': [],
            'dom_ops': []
        }

        body = self.get_function_body(handler_name)
        if body:
            result['calls'] = self.extract_function_calls(body)
            result['commands'] = self.extract_commands_from_body(body)
            result['dom_ops'] = self.extract_dom_operations(body)

        return result

    def generate_markdown_report(self) -> str:
        filename = os.path.basename(self.source_file)

        lines = ['# UI 交互分析报告\n']

        lines.append(f'**源文件**: `{self.source_file}`\n')
        lines.append(f'**按钮数**: {len(self.handlers)}\n')
        lines.append(f'**消息命令数**: {len(self.commands)}\n\n')

        lines.append('## 按钮事件对照表\n')
        lines.append('| 功能 | 事件 | 函数名 | 代码位置 |')
        lines.append('|------|------|--------|----------|')
        for name, info in sorted(self.handlers.items(), key=lambda x: x[1]['line']):
            display = self.BUTTON_NAMES.get(name, name)
            lines.append(f'| {display} | {info["event"]} | `{name}()` | {filename}:{info["line"]} |')

        lines.append('\n## 消息命令总表\n')
        lines.append('| 命令 | 说明 | 发送次数 |')
        lines.append('|------|------|----------|')

        cmd_descs = {
            'chat': '聊天请求',
            'getConfiguredModels': '获取已配置模型',
            'getBalance': '获取余额',
            'configureApiKey': '配置API密钥',
            'checkOllamaStatus': '检查Ollama状态',
            'getOllamaModels': '获取Ollama模型列表',
            'checkOllamaMemory': '检查Ollama内存',
            'stopOllamaService': '停止Ollama服务',
            'approveOperation': '审批通过',
            'rejectOperation': '审批拒绝',
            'openPanel': '打开面板',
            'openSettings': '打开设置',
            'webviewError': 'Webview错误上报',
            'ollamaStatus': 'Ollama状态通知',
            'ollamaModels': 'Ollama模型列表通知',
            'ollamaMemoryCheck': 'Ollama内存检查结果',
            'ollamaServiceStopped': 'Ollama服务已停止',
            'chatResponse': '聊天响应',
            'chatError': '聊天错误',
            'addChatMessage': '添加聊天消息',
            'updateConfiguredModels': '更新已配置模型',
            'balanceResult': '余额结果',
            'balanceError': '余额错误',
            'updateTasks': '更新任务列表',
            'updateApprovals': '更新审批列表',
        }

        for cmd, count in sorted(self.commands.items(), key=lambda x: -x[1]):
            desc = cmd_descs.get(cmd, '')
            lines.append(f'| `{cmd}` | {desc} | {count} |')

        lines.append('\n## 按钮数据流详情\n')

        for name, info in sorted(self.handlers.items(), key=lambda x: x[1]['line']):
            analysis = self.analyze_handler(name)

            lines.append(f'### {analysis["display_name"]}\n')
            lines.append(f'**触发方式**: `{analysis["event"]}` 事件\n')
            lines.append(f'**函数定义**: `{analysis["name"]}()` @ `{filename}:{analysis["line"]}`\n')

            if analysis['dom_ops']:
                lines.append('\n**DOM 操作**:\n')
                for op in analysis['dom_ops'][:5]:
                    lines.append(f'- `{op}`')
                lines.append('')

            if analysis['calls']:
                relevant_calls = [c for c in analysis['calls']
                                 if not c.startswith('console') and c != f'{name}()'
                                 and 'FileReader' not in c]
                if relevant_calls:
                    lines.append('\n**调用的函数**:\n')
                    for call in relevant_calls[:8]:
                        lines.append(f'- `{call}`')
                    lines.append('')

            if analysis['commands']:
                lines.append('\n**发送的消息**:\n')
                for cmd in analysis['commands']:
                    desc = cmd_descs.get(cmd, '')
                    lines.append(f'- `{cmd}` → {desc}')
                lines.append('')

            lines.append('---\n')

        return '\n'.join(lines)

    def generate_mermaid_flowchart(self) -> str:
        lines = ['## 按钮交互流程图\n']
        lines.append('```mermaid')
        lines.append("%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '16px'}}}%%")
        lines.append('flowchart TD')

        for name, info in sorted(self.handlers.items(), key=lambda x: x[1]['line'])[:15]:
            analysis = self.analyze_handler(name)
            display = analysis['display_name']

            lines.append(f'    subgraph {display}')
            lines.append(f'        B_{name}[点击按钮]')
            lines.append(f'        F_{name}[{name}()]')
            lines.append(f'        B_{name} --> F_{name}')
            lines.append(f'    end')

            if analysis['commands']:
                lines.append(f'    F_{name} --> C_{name}')
                lines.append(f'    C_{name}{{{", ".join(analysis["commands"][:3])}}}')
            else:
                lines.append(f'    F_{name} --> E_{name}')
                lines.append(f'    E_{name}((本地更新))')

        lines.append('```\n')
        return '\n'.join(lines)

    def generate_full_report(self) -> str:
        report = self.generate_markdown_report()
        report += '\n' + self.generate_mermaid_flowchart()
        return report
