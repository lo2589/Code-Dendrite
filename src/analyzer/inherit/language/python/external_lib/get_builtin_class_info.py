"""
external_lib.py - 外部库解析 (Medium L3-005, Hard L3-006, Easy L3-007)
========================================================================
解析外部库和内置类。

对应TS: externalLibResolver.ts
"""

from pathlib import Path
from typing import List, Optional, Dict
import sys

from analyzer.shared.legacy.inheritance.types import ExternalClassEntry, MethodInfo
from scanner.language.python.ast_parser import parse_python_file


# 缓存
_site_packages_cache: List[str] = []
_external_class_cache: Dict[str, ExternalClassEntry] = {}

def clear_cache():
    """清除缓存"""
    global _site_packages_cache, _external_class_cache
    _site_packages_cache = []
    _external_class_cache = {}

def get_builtin_class_info(class_name: str) -> Optional[ExternalClassEntry]:
    """
    获取内置类信息 (Easy L3-007)
    
    参数:
        class_name: 类名
    
    返回:
        ExternalClassEntry对象，不是内置类返回None
    
    对应TS: externalLibResolver.ts 的 getBuiltinClassInfo()
    """
    # 内置类定义
    builtins = {
        # 基础类型
        "object": {"module": "builtins", "bases": []},
        "type": {"module": "builtins", "bases": ["object"]},
        
        # 异常
        "BaseException": {"module": "builtins", "bases": ["object"]},
        "Exception": {"module": "builtins", "bases": ["BaseException"]},
        "ValueError": {"module": "builtins", "bases": ["Exception"]},
        "TypeError": {"module": "builtins", "bases": ["Exception"]},
        "KeyError": {"module": "builtins", "bases": ["LookupError"]},
        "IndexError": {"module": "builtins", "bases": ["LookupError"]},
        "AttributeError": {"module": "builtins", "bases": ["Exception"]},
        "LookupError": {"module": "builtins", "bases": ["Exception"]},
        "RuntimeError": {"module": "builtins", "bases": ["Exception"]},
        "StopIteration": {"module": "builtins", "bases": ["Exception"]},
        "OSError": {"module": "builtins", "bases": ["Exception"]},
        "IOError": {"module": "builtins", "bases": ["OSError"]},
        
        # 容器类型
        "dict": {"module": "builtins", "bases": ["object"]},
        "list": {"module": "builtins", "bases": ["object"]},
        "tuple": {"module": "builtins", "bases": ["object"]},
        "set": {"module": "builtins", "bases": ["object"]},
        "frozenset": {"module": "builtins", "bases": ["object"]},
        
        # 数值类型
        "int": {"module": "builtins", "bases": ["object"]},
        "float": {"module": "builtins", "bases": ["object"]},
        "complex": {"module": "builtins", "bases": ["object"]},
        "bool": {"module": "builtins", "bases": ["int"]},
        
        # 字符串和字节
        "str": {"module": "builtins", "bases": ["object"]},
        "bytes": {"module": "builtins", "bases": ["object"]},
        "bytearray": {"module": "builtins", "bases": ["object"]},
        
        # ABC相关
        "ABC": {"module": "abc", "bases": ["object"]},
        "ABCMeta": {"module": "abc", "bases": ["type"]},
        
        # 其他常用
        "property": {"module": "builtins", "bases": ["object"]},
        "staticmethod": {"module": "builtins", "bases": ["object"]},
        "classmethod": {"module": "builtins", "bases": ["object"]},
        "super": {"module": "builtins", "bases": ["object"]},
        
        # typing模块
        "Generic": {"module": "typing", "bases": ["object"]},
        "Protocol": {"module": "typing", "bases": ["object"]},
        
        # collections.abc
        "Iterable": {"module": "collections.abc", "bases": ["object"]},
        "Iterator": {"module": "collections.abc", "bases": ["Iterable"]},
        "Generator": {"module": "collections.abc", "bases": ["Iterator"]},
        "Callable": {"module": "collections.abc", "bases": ["object"]},
        "Mapping": {"module": "collections.abc", "bases": ["object"]},
        "MutableMapping": {"module": "collections.abc", "bases": ["Mapping"]},
        "Sequence": {"module": "collections.abc", "bases": ["object"]},
        "MutableSequence": {"module": "collections.abc", "bases": ["Sequence"]},
        
        # dataclasses
        "dataclass": {"module": "dataclasses", "bases": []},
        
        # enum
        "Enum": {"module": "enum", "bases": ["object"]},
        "IntEnum": {"module": "enum", "bases": ["int", "Enum"]},
        "Flag": {"module": "enum", "bases": ["Enum"]},
    }
    
    if class_name in builtins:
        info = builtins[class_name]
        return ExternalClassEntry(
            name=class_name,
            file="[builtin]",
            line=0,
            bases=info["bases"],
            module=info["module"]
        )
    
    return None

def get_common_frameworks_classes() -> Dict[str, Dict]:
    """
    获取常用框架的类信息
    
    返回一些无法通过AST解析获取的常用框架类信息。
    """
    return {
        # PyTorch
        "torch.nn.Module": {
            "name": "Module",
            "module": "torch.nn",
            "bases": ["object"],
            "methods": ["forward", "__init__", "parameters", "train", "eval"]
        },
        "torch.nn.Linear": {
            "name": "Linear",
            "module": "torch.nn",
            "bases": ["torch.nn.Module"],
        },
        "torch.optim.Optimizer": {
            "name": "Optimizer",
            "module": "torch.optim",
            "bases": ["object"],
        },
        
        # TensorFlow/Keras
        "tensorflow.keras.Model": {
            "name": "Model",
            "module": "tensorflow.keras",
            "bases": ["object"],
        },
        "tensorflow.keras.layers.Layer": {
            "name": "Layer",
            "module": "tensorflow.keras.layers",
            "bases": ["object"],
        },
        
        # Django
        "django.db.models.Model": {
            "name": "Model",
            "module": "django.db.models",
            "bases": ["object"],
        },
        "django.views.View": {
            "name": "View",
            "module": "django.views",
            "bases": ["object"],
        },
        
        # Flask
        "flask.Flask": {
            "name": "Flask",
            "module": "flask",
            "bases": ["object"],
        },
        
        # FastAPI
        "fastapi.FastAPI": {
            "name": "FastAPI",
            "module": "fastapi",
            "bases": ["object"],
        },
        
        # Pydantic
        "pydantic.BaseModel": {
            "name": "BaseModel",
            "module": "pydantic",
            "bases": ["object"],
        },
    }

def get_site_packages_paths() -> List[str]:
    """
    获取Python site-packages路径 (Medium L3-005)
    
    返回:
        site-packages路径列表
    
    对应TS: externalLibResolver.ts 的 getSitePackagesPath()
    
    来源:
        1. site.getsitepackages()
        2. site.getusersitepackages()
        3. sys.path中的site-packages
    """
    global _site_packages_cache
    if _site_packages_cache:
        return _site_packages_cache
    
    paths = set()
    
    # 从site模块获取
    try:
        import site
        site_packages = site.getsitepackages()
        for p in site_packages:
            if Path(p).exists():
                paths.add(p)
    except Exception:
        pass
    
    # 添加用户site-packages
    try:
        import site
        user_site = site.getusersitepackages()
        if user_site and Path(user_site).exists():
            paths.add(user_site)
    except Exception:
        pass
    
    # 从sys.path中查找
    for p in sys.path:
        if 'site-packages' in p or 'dist-packages' in p:
            if Path(p).exists():
                paths.add(p)
    
    _site_packages_cache = list(paths)
    return _site_packages_cache

def resolve_module_path(module_path: str) -> Optional[str]:
    """
    解析模块路径到文件路径
    
    参数:
        module_path: 模块路径（如 "torch.nn"）
    
    返回:
        文件路径，未找到返回None
    
    对应TS: externalLibResolver.ts 的 resolveModulePath()
    
    示例:
        - torch.nn.Module -> /path/to/torch/nn/__init__.py
        - os.path -> /usr/lib/python3.x/os/path.py
    """
    site_paths = get_site_packages_paths()
    parts = module_path.split(".")
    
    # 也检查标准库路径
    stdlib_path = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}"
    all_paths = site_paths + ([str(stdlib_path)] if stdlib_path.exists() else [])
    
    for base_path in all_paths:
        current_path = Path(base_path)
        
        for i, part in enumerate(parts):
            dir_path = current_path / part
            file_path = current_path / f"{part}.py"
            
            # 检查目录
            if dir_path.is_dir():
                current_path = dir_path
                if i == len(parts) - 1:
                    # 最后一部分，检查__init__.py
                    init_path = dir_path / "__init__.py"
                    if init_path.exists():
                        return str(init_path)
                    # 检查是否有.py文件
                    pyi_path = dir_path / "__init__.pyi"
                    if pyi_path.exists():
                        return str(pyi_path)
            # 检查文件
            elif file_path.exists():
                return str(file_path)
            else:
                break
    
    return None
