"""
HTML 代码分析器
提取 HTML 元素结构、ID、类名、表单、内联事件等
"""
import re
import os
from typing import List, Optional, Dict
from parse.codeAnalysis.analyzer.base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


class HtmlAnalyzer(BaseAnalyzer):
    """HTML 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.html', '.htm', '.xhtml']

    def __init__(self, root_path: str):
        super().__init__(root_path)

    @property
    def language_name(self) -> str:
        return "html"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source = f.read()

        module_name = os.path.basename(file_path)
        module_info = ModuleInfo(name=module_name, file_path=file_path, line_number=1)

        # 提取页面结构信息
        structure = self._extract_structure(source, file_path)
        
        # 将结构信息存储在 extra 字段
        module_info.extra = structure
        
        # 将内联事件处理器作为"函数"存储
        module_info.functions.extend(structure.get('inline_handlers', []))

        return module_info

    def _extract_structure(self, source: str, file_path: str) -> dict:
        """提取 HTML 文档结构"""
        structure = {
            'title': None,
            'ids': [],           # 所有 id 属性
            'classes': [],       # 所有 class 属性
            'forms': [],         # 表单元素
            'scripts': [],       # script 标签
            'styles': [],        # style/link 标签
            'inline_handlers': [],  # 内联事件处理器
            'links': [],         # a 标签
            'images': [],        # img 标签
            'meta': [],          # meta 标签
        }

        # 移除注释
        clean_source = re.sub(r'<!--.*?-->', '', source, flags=re.DOTALL)

        # 提取 title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', clean_source, re.DOTALL | re.IGNORECASE)
        if title_match:
            structure['title'] = title_match.group(1).strip()

        # 提取所有 id 属性
        id_pattern = r'id\s*=\s*["\']([^"\']+)["\']'
        for match in re.finditer(id_pattern, clean_source, re.IGNORECASE):
            structure['ids'].append({
                'id': match.group(1),
                'line': clean_source[:match.start()].count('\n') + 1
            })

        # 提取所有 class 属性
        class_pattern = r'class\s*=\s*["\']([^"\']+)["\']'
        for match in re.finditer(class_pattern, clean_source, re.IGNORECASE):
            classes = match.group(1).split()
            for cls in classes:
                structure['classes'].append(cls)

        # 提取表单
        form_pattern = r'<form[^>]*>(.*?)</form>'
        for match in re.finditer(form_pattern, clean_source, re.DOTALL | re.IGNORECASE):
            form_content = match.group(0)
            form_info = self._parse_form(form_content, clean_source[:match.start()].count('\n') + 1)
            structure['forms'].append(form_info)

        # 提取 script 标签
        script_pattern = r'<script[^>]*>(.*?)</script>'
        for match in re.finditer(script_pattern, clean_source, re.DOTALL | re.IGNORECASE):
            script_tag = match.group(0)
            src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', script_tag)
            script_info = {
                'line': clean_source[:match.start()].count('\n') + 1,
                'src': src_match.group(1) if src_match else None,
                'type': None,
                'inline': src_match is None
            }
            type_match = re.search(r'type\s*=\s*["\']([^"\']+)["\']', script_tag)
            if type_match:
                script_info['type'] = type_match.group(1)
            structure['scripts'].append(script_info)

        # 提取样式链接
        link_pattern = r'<link[^>]*rel\s*=\s*["\']?stylesheet["\']?[^>]*/?>'
        for match in re.finditer(link_pattern, clean_source, re.IGNORECASE):
            href_match = re.search(r'href\s*=\s*["\']([^"\']+)["\']', match.group(0))
            if href_match:
                structure['styles'].append({
                    'href': href_match.group(1),
                    'line': clean_source[:match.start()].count('\n') + 1
                })

        style_pattern = r'<style[^>]*>(.*?)</style>'
        for match in re.finditer(style_pattern, clean_source, re.DOTALL | re.IGNORECASE):
            structure['styles'].append({
                'inline': True,
                'line': clean_source[:match.start()].count('\n') + 1
            })

        # 提取内联事件处理器
        inline_events = [
            'onclick', 'ondblclick', 'onmousedown', 'onmouseup', 'onmouseover',
            'onmousemove', 'onmouseout', 'onmouseenter', 'onmouseleave',
            'onkeydown', 'onkeyup', 'onkeypress',
            'onfocus', 'onblur', 'onchange', 'oninput', 'onsubmit', 'onreset',
            'onload', 'onunload', 'onerror', 'onresize', 'onscroll',
            'ondrag', 'ondragstart', 'ondragend', 'ondragover', 'ondragenter',
            'ondragleave', 'ondrop',
            'ontouchstart', 'ontouchmove', 'ontouchend', 'ontouchcancel',
            'oncontextmenu', 'onwheel', 'oncopy', 'oncut', 'onpaste'
        ]
        
        for event in inline_events:
            pattern = rf'{event}\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(pattern, clean_source, re.IGNORECASE):
                handler_code = match.group(1).strip()
                # 提取函数名
                func_match = re.match(r'(\w+)\s*\(', handler_code)
                func_name = func_match.group(1) if func_match else handler_code[:30]
                
                func_info = FunctionInfo(
                    name=f"{event}:{func_name}",
                    file_path=file_path,
                    line_number=clean_source[:match.start()].count('\n') + 1,
                    docstring=handler_code[:100]
                )
                structure['inline_handlers'].append(func_info)

        # 提取链接
        link_pattern = r'<a[^>]*>(.*?)</a>'
        for match in re.finditer(link_pattern, clean_source, re.DOTALL | re.IGNORECASE):
            link_tag = match.group(0)
            href_match = re.search(r'href\s*=\s*["\']([^"\']+)["\']', link_tag)
            if href_match:
                text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                structure['links'].append({
                    'href': href_match.group(1),
                    'text': text[:50] if text else '',
                    'line': clean_source[:match.start()].count('\n') + 1
                })

        # 提取图片
        img_pattern = r'<img[^>]+>'
        for match in re.finditer(img_pattern, clean_source, re.IGNORECASE):
            img_tag = match.group(0)
            src_match = re.search(r'src\s*=\s*["\']([^"\']+)["\']', img_tag)
            alt_match = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', img_tag)
            if src_match:
                structure['images'].append({
                    'src': src_match.group(1),
                    'alt': alt_match.group(1) if alt_match else '',
                    'line': clean_source[:match.start()].count('\n') + 1
                })

        # 提取 meta 标签
        meta_pattern = r'<meta[^>]+>'
        for match in re.finditer(meta_pattern, clean_source, re.IGNORECASE):
            meta_tag = match.group(0)
            name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', meta_tag)
            property_match = re.search(r'property\s*=\s*["\']([^"\']+)["\']', meta_tag)
            content_match = re.search(r'content\s*=\s*["\']([^"\']*)["\']', meta_tag)
            
            structure['meta'].append({
                'name': name_match.group(1) if name_match else (property_match.group(1) if property_match else None),
                'content': content_match.group(1) if content_match else None,
                'line': clean_source[:match.start()].count('\n') + 1
            })

        return structure

    def _parse_form(self, form_content: str, start_line: int) -> dict:
        """解析表单元素"""
        form_info = {
            'action': None,
            'method': None,
            'inputs': [],
            'line': start_line
        }

        # 提取 action 和 method
        action_match = re.search(r'action\s*=\s*["\']([^"\']*)["\']', form_content, re.IGNORECASE)
        method_match = re.search(r'method\s*=\s*["\']([^"\']+)["\']', form_content, re.IGNORECASE)
        
        if action_match:
            form_info['action'] = action_match.group(1)
        if method_match:
            form_info['method'] = method_match.group(1).upper()

        # 提取输入元素
        input_pattern = r'<input[^>]*>'
        for match in re.finditer(input_pattern, form_content, re.IGNORECASE):
            input_tag = match.group(0)
            input_info = {
                'type': 'text',
                'name': None,
                'id': None,
                'placeholder': None
            }
            
            type_match = re.search(r'type\s*=\s*["\']([^"\']+)["\']', input_tag, re.IGNORECASE)
            name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', input_tag, re.IGNORECASE)
            id_match = re.search(r'id\s*=\s*["\']([^"\']+)["\']', input_tag, re.IGNORECASE)
            placeholder_match = re.search(r'placeholder\s*=\s*["\']([^"\']*)["\']', input_tag, re.IGNORECASE)
            
            if type_match:
                input_info['type'] = type_match.group(1)
            if name_match:
                input_info['name'] = name_match.group(1)
            if id_match:
                input_info['id'] = id_match.group(1)
            if placeholder_match:
                input_info['placeholder'] = placeholder_match.group(1)
            
            form_info['inputs'].append(input_info)

        # 提取 select 元素
        select_pattern = r'<select[^>]*name\s*=\s*["\']([^"\']+)["\'][^>]*>'
        for match in re.finditer(select_pattern, form_content, re.IGNORECASE):
            form_info['inputs'].append({
                'type': 'select',
                'name': match.group(1)
            })

        # 提取 textarea 元素
        textarea_pattern = r'<textarea[^>]*name\s*=\s*["\']([^"\']+)["\']'
        for match in re.finditer(textarea_pattern, form_content, re.IGNORECASE):
            form_info['inputs'].append({
                'type': 'textarea',
                'name': match.group(1)
            })

        # 提取 button 元素
        button_pattern = r'<button[^>]*type\s*=\s*["\']([^"\']+)["\']'
        for match in re.finditer(button_pattern, form_content, re.IGNORECASE):
            form_info['inputs'].append({
                'type': f'button:{match.group(1)}'
            })

        return form_info
