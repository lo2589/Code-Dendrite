"""
ast_parser.py - Python AST解析器 (Easy L3-002)
================================================
解析Python文件，提取类和导入信息。

对应TS: pythonAST.ts
"""

import ast
from pathlib import Path
from typing import List, Optional

from scanner.shared.inheritance_types import ClassInfo, MethodInfo, ImportInfo, PythonFileInfo

def _check_has_super(func_node) -> bool:
    """检查函数是否调用了super()"""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "super":
                return True
    return False

def _parse_method(node) -> MethodInfo:
    """解析方法定义"""
    # 检查是否调用super()
    has_super = _check_has_super(node)
    
    # 获取装饰器
    decorators = []
    for dec in node.decorator_list:
        try:
            decorators.append(ast.unparse(dec))
        except:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
    
    return MethodInfo(
        name=node.name,
        start_line=node.lineno,
        end_line=node.end_lineno or node.lineno,
        has_super=has_super,
        decorators=decorators
    )

def _parse_class(node: ast.ClassDef, file_path: str) -> ClassInfo:
    """解析类定义"""
    # 获取基类
    bases = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            # 处理 module.ClassName 形式
            try:
                bases.append(ast.unparse(base))
            except:
                bases.append(base.attr)
        elif isinstance(base, ast.Subscript):
            # 处理 Generic[T] 形式
            try:
                bases.append(ast.unparse(base))
            except:
                if isinstance(base.value, ast.Name):
                    bases.append(base.value.id)
    
    # 获取方法
    methods = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_info = _parse_method(item)
            methods.append(method_info)
    
    # 获取装饰器
    decorators = []
    for dec in node.decorator_list:
        try:
            decorators.append(ast.unparse(dec))
        except:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
    
    return ClassInfo(
        name=node.name,
        bases=bases,
        methods=methods,
        file=file_path,
        line=node.lineno,
        decorators=decorators
    )

def _parse_type_annotation(annotation) -> str:
    """
    解析类型注解
    
    参数:
        annotation: 类型注解 AST 节点
    
    返回:
        类型字符串
    """
    try:
        return ast.unparse(annotation)
    except:
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return f"{_parse_type_annotation(annotation.value)}.{annotation.attr}"
        elif isinstance(annotation, ast.Subscript):
            return f"{_parse_type_annotation(annotation.value)}[{_parse_type_annotation(annotation.slice)}]"
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        else:
            return str(annotation)

def extract_parameter_types(func_node) -> dict:
    """
    提取函数参数类型注解
    
    参数:
        func_node: 函数 AST 节点
    
    返回:
        参数名 -> 类型 的字典
    """
    types = {}
    
    for arg in func_node.args.args:
        if arg.annotation:
            types[arg.arg] = _parse_type_annotation(arg.annotation)
    
    if func_node.args.vararg:
        vararg = func_node.args.vararg
        if vararg.annotation:
            types[vararg.arg] = f"* {_parse_type_annotation(vararg.annotation)}"
    
    if func_node.args.kwarg:
        kwarg = func_node.args.kwarg
        if kwarg.annotation:
            types[kwarg.arg] = f"** {_parse_type_annotation(kwarg.annotation)}"
    
    return types

def extract_return_type(func_node) -> Optional[str]:
    """
    提取函数返回类型注解
    
    参数:
        func_node: 函数 AST 节点
    
    返回:
        返回类型字符串
    """
    if hasattr(func_node, 'returns') and func_node.returns:
        return _parse_type_annotation(func_node.returns)
    return None

def get_decorators(node) -> List[str]:
    """
    获取节点的装饰器列表
    
    参数:
        node: AST节点（类或函数）
    
    返回:
        装饰器名称列表
    """
    decorators = []
    for dec in getattr(node, 'decorator_list', []):
        try:
            decorators.append(ast.unparse(dec))
        except:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(dec.attr)
    return decorators

def parse_python_file(file_path: str) -> PythonFileInfo:
    """
    解析Python文件，提取类和导入信息
    
    参数:
        file_path: 文件路径
    
    返回:
        PythonFileInfo对象
    
    对应TS: pythonAST.ts 的 parsePython()
    
    实现差异:
        - TS使用tree-sitter，Python使用内置ast模块
        - ast模块原生支持，无需额外依赖
    """
    path = Path(file_path)
    if not path.exists():
        return PythonFileInfo(classes=[], imports=[])
    
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=file_path)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return PythonFileInfo(classes=[], imports=[])
    
    classes = []
    imports = []
    
    # 遍历顶层节点
    for node in tree.body:
        # 解析类定义
        if isinstance(node, ast.ClassDef):
            class_info = _parse_class(node, file_path)
            classes.append(class_info)
        
        # 解析import语句
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportInfo(
                    module=alias.name,
                    aliases={alias.name.split('.')[0]: alias.asname or alias.name.split('.')[0]},
                    from_path=None,
                    line=node.lineno
                ))
        
        elif isinstance(node, ast.ImportFrom):
            aliases = {}
            for alias in node.names:
                original_name = alias.name
                as_name = alias.asname or alias.name
                aliases[original_name] = as_name
            
            imports.append(ImportInfo(
                module="",
                aliases=aliases,
                from_path=node.module or "",
                line=node.lineno
            ))
    
    return PythonFileInfo(classes=classes, imports=imports)

def parse_symbol(file_path: str, symbol: str) -> Optional[ClassInfo]:
    """
    解析特定类
    
    参数:
        file_path: 文件路径
        symbol: 类名
    
    返回:
        ClassInfo对象，未找到返回None
    """
    file_info = parse_python_file(file_path)
    for cls in file_info.classes:
        if cls.name == symbol:
            return cls
    return None

def get_method_info(file_path: str, class_name: str, method_name: str) -> Optional[MethodInfo]:
    """
    获取特定方法信息
    
    参数:
        file_path: 文件路径
        class_name: 类名
        method_name: 方法名
    
    返回:
        MethodInfo对象，未找到返回None
    """
    cls = parse_symbol(file_path, class_name)
    if cls:
        for method in cls.methods:
            if method.name == method_name:
                return method
    return None

def has_abstract_decorator(method_node) -> bool:
    """
    检查方法是否有 @abstractmethod 装饰器
    
    参数:
        method_node: 方法 AST 节点
    
    返回:
        是否有 @abstractmethod 装饰器
    """
    decorators = get_decorators(method_node)
    return any('abstract' in d.lower() for d in decorators)

def has_override_decorator(method_node) -> bool:
    """
    检查方法是否有 @override 装饰器
    
    参数:
        method_node: 方法 AST 节点
    
    返回:
        是否有 @override 装饰器
    """
    decorators = get_decorators(method_node)
    return any('override' in d.lower() for d in decorators)
