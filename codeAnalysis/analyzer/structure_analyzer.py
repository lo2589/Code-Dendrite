"""
项目结构分析器 - 集成到 code_flowchart

功能：
1. 递归扫描项目目录结构
2. 统计文件数、代码行数、语言分布
3. 生成树形展示和 JSON 输出
4. 与函数调用图分析无缝集成
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base import ProjectInfo


class ProjectStructureAnalyzer:
    """项目结构分析器"""
    
    # 支持的语言及扩展名
    SUPPORTED_LANGUAGES = {
        'python': ['.py'],
        'javascript': ['.js', '.jsx'],
        'typescript': ['.ts', '.tsx'],
        'java': ['.java'],
        'go': ['.go'],
        'rust': ['.rs'],
        'cpp': ['.cpp', '.cc', '.cxx', '.h', '.hpp'],
        'c': ['.c', '.h'],
        'ruby': ['.rb'],
        'php': ['.php'],
        'swift': ['.swift'],
        'kotlin': ['.kt', '.kts'],
        'shell': ['.sh', '.bash'],
        'markdown': ['.md'],
        'json': ['.json'],
        'yaml': ['.yml', '.yaml'],
        'html': ['.html', '.htm'],
        'css': ['.css', '.scss', '.sass', '.less'],
    }
    
    # 忽略的目录
    IGNORE_DIRS = {
        '__pycache__', 'node_modules', '.git', '.svn', '.hg',
        'dist', 'build', 'out', 'target', 'venv', '.venv',
        'env', '.env', 'coverage', '.idea', '.vscode',
        '*.egg-info', '.tox', '.pytest_cache'
    }
    
    # 忽略的文件
    IGNORE_FILES = {
        '*.pyc', '*.pyo', '*.so', '*.dll', '*.dylib',
        '*.log', '*.lock', '*.bak', '*.swp', '*.swo',
        '.DS_Store', 'Thumbs.db', '*.min.js', '*.min.css'
    }
    
    def __init__(self, root_path: str, max_depth: int = 10):
        self.root_path = Path(root_path).resolve()
        self.max_depth = max_depth
        
        if not self.root_path.exists():
            raise FileNotFoundError(f"目录不存在：{root_path}")
        
        if not self.root_path.is_dir():
            raise NotADirectoryError(f"不是目录：{root_path}")
    
    def analyze(self) -> Dict[str, Any]:
        """
        分析项目结构
        
        Returns:
            包含项目结构的字典
        """
        print(f"[Structure] 开始解析项目：{self.root_path}")
        start_time = datetime.now()
        
        structure = {
            'name': self.root_path.name,
            'path': str(self.root_path),
            'type': 'directory',
            'children': [],
            'stats': {
                'total_files': 0,
                'total_dirs': 0,
                'total_lines': 0,
                'languages': {},
                'parse_time': ''
            }
        }
        
        self._scan_directory(self.root_path, structure, depth=0)
        
        end_time = datetime.now()
        structure['stats']['parse_time'] = str((end_time - start_time).total_seconds()) + 's'
        
        print(f"[Structure] 解析完成：{structure['stats']['total_files']} 个文件，"
              f"{structure['stats']['total_dirs']} 个目录，耗时 {structure['stats']['parse_time']}")
        
        return structure
    
    def _scan_directory(self, dir_path: Path, parent_node: Dict, depth: int):
        """递归扫描目录"""
        if depth >= self.max_depth:
            print(f"[Structure] 达到最大深度 {depth}，跳过：{dir_path}")
            return
        
        try:
            entries = list(dir_path.iterdir())
        except PermissionError:
            print(f"[Structure] 无权限访问：{dir_path}")
            return
        
        # 排序：目录在前，文件在后
        entries.sort(key=lambda x: (x.is_file(), x.name.lower()))
        
        for entry in entries:
            if self._should_ignore(entry):
                continue
            
            node = {
                'name': entry.name,
                'path': str(entry.relative_to(self.root_path)),
                'type': 'directory' if entry.is_dir() else 'file',
            }
            
            if entry.is_dir():
                node['children'] = []
                node['stats'] = {
                    'total_files': 0,
                    'total_dirs': 0,
                    'total_lines': 0,
                    'languages': {},
                    'parse_time': ''
                }
                parent_node['children'].append(node)
                parent_node['stats']['total_dirs'] += 1
                
                self._scan_directory(entry, node, depth + 1)
                
                for lang, info in node['stats'].get('languages', {}).items():
                    if lang not in parent_node['stats']['languages']:
                        parent_node['stats']['languages'][lang] = {'files': 0, 'lines': 0}
                    parent_node['stats']['languages'][lang]['files'] += info['files']
                    parent_node['stats']['languages'][lang]['lines'] += info['lines']
                parent_node['stats']['total_files'] += node['stats']['total_files']
                parent_node['stats']['total_dirs'] += node['stats']['total_dirs']
                parent_node['stats']['total_lines'] += node['stats']['total_lines']
            else:
                file_info = self._analyze_file(entry)
                node.update(file_info)
                parent_node['children'].append(node)
                parent_node['stats']['total_files'] += 1
                parent_node['stats']['total_lines'] += file_info.get('lines', 0)
                
                # 统计语言
                lang = file_info.get('language', 'unknown')
                if lang not in parent_node['stats']['languages']:
                    parent_node['stats']['languages'][lang] = {'files': 0, 'lines': 0}
                parent_node['stats']['languages'][lang]['files'] += 1
                parent_node['stats']['languages'][lang]['lines'] += file_info.get('lines', 0)
    
    def _should_ignore(self, path: Path) -> bool:
        """检查是否应该忽略"""
        import fnmatch
        name = path.name
        
        if path.is_dir():
            if name in self.IGNORE_DIRS:
                return True
            for pattern in self.IGNORE_DIRS:
                if fnmatch.fnmatch(name, pattern):
                    return True
        
        if path.is_file():
            if name in self.IGNORE_FILES:
                return True
            for pattern in self.IGNORE_FILES:
                if fnmatch.fnmatch(name, pattern):
                    return True
            if name.startswith('.'):
                return True
        
        return False
    
    def _analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """分析单个文件"""
        file_info = {
            'size': file_path.stat().st_size,
            'extension': file_path.suffix.lower(),
            'language': self._detect_language(file_path),
            'lines': 0,
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                file_info['lines'] = len(content.splitlines())
        except Exception as e:
            file_info['error'] = str(e)
        
        return file_info
    
    def _detect_language(self, file_path: Path) -> str:
        """检测文件语言"""
        suffix = file_path.suffix.lower()
        
        for lang, extensions in self.SUPPORTED_LANGUAGES.items():
            if suffix in extensions:
                return lang
        
        return 'unknown'
    
    def to_json(self, structure: Dict[str, Any], indent: int = 2) -> str:
        """转换为 JSON"""
        return json.dumps(structure, ensure_ascii=False, indent=indent)
    
    def to_tree_string(self, structure: Dict[str, Any], prefix: str = '', is_last: bool = True) -> str:
        """转换为树形字符串"""
        result = []
        
        connector = '└── ' if is_last else '├── '
        icon = '📁 ' if structure['type'] == 'directory' else '📄 '
        
        if structure['type'] == 'directory':
            result.append(f"{prefix}{connector}{icon}{structure['name']}/")
        else:
            extra = ''
            if 'lines' in structure:
                extra = f" ({structure['lines']} 行)"
            if 'size' in structure:
                size_kb = round(structure['size'] / 1024, 1)
                extra += f" {size_kb}KB"
            result.append(f"{prefix}{connector}{icon}{structure['name']}{extra}")
        
        if structure['type'] == 'directory' and 'children' in structure:
            children = structure['children']
            extension = '    ' if is_last else '│   '
            
            for i, child in enumerate(children):
                is_last_child = (i == len(children) - 1)
                result.append(
                    self.to_tree_string(child, prefix + extension, is_last_child)
                )
        
        return '\n'.join(result)
    
    def generate_summary(self, structure: Dict[str, Any]) -> str:
        """生成摘要报告"""
        stats = structure['stats']
        
        summary = [
            f"# 项目代码结构分析",
            f"",
            f"## 📊 基本统计",
            f"- **项目路径**: `{structure['path']}`",
            f"- **总文件数**: {stats['total_files']}",
            f"- **总目录数**: {stats['total_dirs']}",
            f"- **总代码行数**: {stats['total_lines']:,}",
            f"- **解析耗时**: {stats['parse_time']}",
            f"",
            f"## 🌍 语言分布",
        ]
        
        sorted_langs = sorted(
            stats['languages'].items(),
            key=lambda x: x[1]['files'],
            reverse=True
        )
        
        for lang, data in sorted_langs:
            files = data['files']
            lines = data['lines']
            percentage = round(files / stats['total_files'] * 100, 1) if stats['total_files'] > 0 else 0
            summary.append(f"- **{lang.title()}**: {files} 文件 ({percentage}%) · {lines:,} 行")
        
        summary.extend([
            f"",
            f"## 📁 目录结构",
            f"```",
            self.to_tree_string(structure),
            f"```",
        ])
        
        return '\n'.join(summary)


def analyze_project_structure(
    project_path: str,
    output_format: str = 'summary',
    max_depth: int = 8
) -> str:
    """
    分析项目结构的便捷函数
    
    Args:
        project_path: 项目路径
        output_format: 输出格式 ('json' | 'tree' | 'structure' | 'summary')
        max_depth: 最大深度
    
    Returns:
        分析结果字符串
    """
    analyzer = ProjectStructureAnalyzer(project_path, max_depth)
    structure = analyzer.analyze()
    
    # 映射 format 参数
    if output_format in ['structure', 'summary']:
        return analyzer.generate_summary(structure)
    elif output_format == 'json':
        return analyzer.to_json(structure)
    elif output_format == 'tree':
        return analyzer.to_tree_string(structure)
    else:
        raise ValueError(f"不支持的输出格式：{output_format}")


# 与原有 ProjectInfo 集成
def enrich_project_info_with_structure(project_info: ProjectInfo, structure: Dict[str, Any]) -> ProjectInfo:
    """
    将项目结构信息注入到原有的 ProjectInfo 中
    
    Args:
        project_info: 原有的项目信息（包含函数调用关系）
        structure: 项目结构分析结果
    
    Returns:
        增强后的 ProjectInfo
    """
    # 可以在这里添加逻辑，将结构信息添加到 project_info
    # 例如：project_info.structure = structure
    return project_info
