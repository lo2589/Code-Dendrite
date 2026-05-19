"""
代码分析器包
支持 10 种编程语言的静态代码分析
"""
from .base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo
from .python_analyzer import PythonAnalyzer
from .typescript_analyzer import TypeScriptAnalyzer
from .cpp_analyzer import CppAnalyzer
from .java_analyzer import JavaAnalyzer
from .php_analyzer import PhpAnalyzer
from .ruby_analyzer import RubyAnalyzer
from .go_analyzer import GoAnalyzer
from .rust_analyzer import RustAnalyzer
from .swift_analyzer import SwiftAnalyzer
from .kotlin_analyzer import KotlinAnalyzer
from .html_analyzer import HtmlAnalyzer
from .structure_analyzer import ProjectStructureAnalyzer, analyze_project_structure

__all__ = [
    'BaseAnalyzer',
    'FunctionInfo',
    'ModuleInfo',
    'ProjectInfo',
    'PythonAnalyzer',
    'TypeScriptAnalyzer',
    'CppAnalyzer',
    'JavaAnalyzer',
    'PhpAnalyzer',
    'RubyAnalyzer',
    'GoAnalyzer',
    'RustAnalyzer',
    'SwiftAnalyzer',
    'KotlinAnalyzer',
    'HtmlAnalyzer',
    'ProjectStructureAnalyzer',
    'analyze_project_structure',
    'get_analyzer',
]

# 语言映射表
LANGUAGE_MAP = {
    # Python
    'python': PythonAnalyzer, 'py': PythonAnalyzer,
    # JavaScript/TypeScript
    'typescript': TypeScriptAnalyzer, 'javascript': TypeScriptAnalyzer,
    'ts': TypeScriptAnalyzer, 'js': TypeScriptAnalyzer,
    'tsx': TypeScriptAnalyzer, 'jsx': TypeScriptAnalyzer,
    # C/C++
    'cpp': CppAnalyzer, 'c++': CppAnalyzer, 'c': CppAnalyzer,
    'h': CppAnalyzer, 'hpp': CppAnalyzer,
    # Java
    'java': JavaAnalyzer,
    # PHP
    'php': PhpAnalyzer,
    # Ruby
    'ruby': RubyAnalyzer, 'rb': RubyAnalyzer,
    # Go
    'go': GoAnalyzer, 'golang': GoAnalyzer,
    # Rust
    'rust': RustAnalyzer, 'rs': RustAnalyzer,
    # Swift
    'swift': SwiftAnalyzer,
    # Kotlin
    'kotlin': KotlinAnalyzer, 'kt': KotlinAnalyzer,
    # HTML
    'html': HtmlAnalyzer, 'htm': HtmlAnalyzer,
}

# 文件扩展名映射
EXTENSION_MAP = {
    '.py': PythonAnalyzer,
    '.ts': TypeScriptAnalyzer, '.tsx': TypeScriptAnalyzer,
    '.js': TypeScriptAnalyzer, '.jsx': TypeScriptAnalyzer, '.mjs': TypeScriptAnalyzer,
    '.cpp': CppAnalyzer, '.c': CppAnalyzer, '.h': CppAnalyzer,
    '.hpp': CppAnalyzer, '.cc': CppAnalyzer, '.cxx': CppAnalyzer,
    '.java': JavaAnalyzer,
    '.php': PhpAnalyzer, '.phtml': PhpAnalyzer,
    '.rb': RubyAnalyzer, '.rake': RubyAnalyzer,
    '.go': GoAnalyzer,
    '.rs': RustAnalyzer,
    '.swift': SwiftAnalyzer,
    '.kt': KotlinAnalyzer, '.kts': KotlinAnalyzer,
    '.html': HtmlAnalyzer, '.htm': HtmlAnalyzer, '.xhtml': HtmlAnalyzer,
}


def get_analyzer(root_path: str, language: str = None) -> BaseAnalyzer:
    """
    根据语言或路径自动选择合适的分析器
    
    支持的语言:
    - Python (.py)
    - TypeScript/JavaScript (.ts, .tsx, .js, .jsx, .mjs)
    - C/C++ (.c, .cpp, .h, .hpp, .cc, .cxx)
    - Java (.java)
    - PHP (.php, .phtml)
    - Ruby (.rb, .rake)
    - Go (.go)
    - Rust (.rs)
    - Swift (.swift)
    - Kotlin (.kt, .kts)
    - HTML (.html, .htm, .xhtml)
    """
    # 通过语言名指定
    if language:
        lang = language.lower()
        analyzer_class = LANGUAGE_MAP.get(lang)
        if analyzer_class:
            return analyzer_class(root_path)

    # 自动检测：扫描文件扩展名
    import os
    for root, dirs, files in os.walk(root_path):
        # 排除隐藏目录和常见忽略目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'vendor', 'target', 'build', 'dist', '__pycache__')]
        
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            analyzer_class = EXTENSION_MAP.get(ext)
            if analyzer_class:
                return analyzer_class(root_path)

    # 默认返回 Python 分析器
    return PythonAnalyzer(root_path)
