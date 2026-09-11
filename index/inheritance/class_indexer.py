"""
class_indexer.py - 类索引构建器 (Medium L3-001)
=================================================
扫描项目构建类索引。

对应TS: workspaceIndexer.ts
"""

import os
from pathlib import Path
from typing import List, Set
from base.shared.codedendrite_ignore import CodeDendriteIgnore

from base.inheritance.types import ClassIndex, ClassEntry
from parse.inheritance.ast_parser import parse_python_file


# 默认排除的目录
DEFAULT_EXCLUDE_DIRS = {
    '__pycache__',
    '.git',
    '.svn',
    '.hg',
    'node_modules',
    'venv',
    '.venv',
    'env',
    '.env',
    'dist',
    'build',
    '.tox',
    '.nox',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    'htmlcov',
    '.coverage',
    '*.egg-info',
}


def build_class_index(
    root: str,
    exclude_dirs: Set[str] = None,
    include_patterns: List[str] = None
) -> ClassIndex:
    """
    构建项目类索引 (Medium L3-001)
    
    参数:
        root: 项目根目录
        exclude_dirs: 要排除的目录名（默认排除常见缓存目录）
        include_patterns: 要包含的文件模式（默认 *.py）
    
    返回:
        ClassIndex对象
    
    对应TS: workspaceIndexer.ts 的 buildWorkspaceIndex()
    
    流程:
        1. 递归扫描所有.py文件
        2. 解析每个文件的类和导入
        3. 存入ClassIndex
    """
    index = ClassIndex()
    root_path = Path(root)
    ignore = CodeDendriteIgnore(str(root_path))
    
    if exclude_dirs is None:
        exclude_dirs = DEFAULT_EXCLUDE_DIRS
    
    # 递归扫描（目录级剪枝，跳过 ignore 目录）
    def _iter_py_files(root_p: Path):
        for dirpath, dirnames, filenames in os.walk(root_p):
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.py")]
            for fname in filenames:
                if fname.endswith(".py"):
                    yield dp / fname

    for py_file in _iter_py_files(root_path):
        if not ignore.should_scan(py_file):
            continue
        # 检查是否在排除目录中
        if _should_exclude(py_file, exclude_dirs):
            continue
        
        try:
            file_info = parse_python_file(str(py_file))
            
            # 计算相对路径
            try:
                rel_path = str(py_file.relative_to(root_path))
            except ValueError:
                rel_path = str(py_file)
            
            # 存储文件导入
            index.file_imports[rel_path] = file_info.imports
            
            # 存储类信息
            for cls in file_info.classes:
                entry = ClassEntry(
                    name=cls.name,
                    file=rel_path,
                    line=cls.line,
                    bases=cls.bases,
                    methods=cls.methods,
                    imports=file_info.imports,
                    depth=0,
                    is_external=False
                )
                index.add_class(entry)
        
        except Exception as e:
            # 解析失败，跳过
            print(f"[Warning] 解析失败 {py_file}: {e}")
            continue
    
    print(f"[ClassIndex] 索引了 {len(index)} 个类")
    return index


def _should_exclude(path: Path, exclude_dirs: Set[str]) -> bool:
    """检查路径是否应该排除"""
    for part in path.parts:
        # 隐藏目录
        if part.startswith('.') and part not in ('.', '..'):
            if part not in ('.git', '.svn', '.hg'):  # 这些在exclude_dirs中处理
                return True
        # 在排除列表中
        if part in exclude_dirs:
            return True
    return False


def rebuild_class_index(
    index: ClassIndex,
    changed_files: List[str],
    root: str
) -> ClassIndex:
    """
    增量重建类索引
    
    参数:
        index: 现有索引
        changed_files: 变更的文件列表
        root: 项目根目录
    
    返回:
        更新后的ClassIndex
    """
    root_path = Path(root)
    
    for file_path in changed_files:
        # 移除该文件的旧类
        if file_path in index.file_classes:
            for class_name in index.file_classes[file_path]:
                if class_name in index.classes:
                    del index.classes[class_name]
                fq_key = "{}::{}".format(file_path, class_name)
                if fq_key in index.classes_fq:
                    del index.classes_fq[fq_key]
            del index.file_classes[file_path]
        
        # 重新解析
        abs_path = root_path / file_path
        if abs_path.exists() and abs_path.suffix == '.py':
            try:
                file_info = parse_python_file(str(abs_path))
                
                index.file_imports[file_path] = file_info.imports
                
                for cls in file_info.classes:
                    entry = ClassEntry(
                        name=cls.name,
                        file=file_path,
                        line=cls.line,
                        bases=cls.bases,
                        methods=cls.methods,
                        imports=file_info.imports,
                        depth=0,
                        is_external=False
                    )
                    index.add_class(entry)
            except Exception:
                pass
    
    return index


def get_class_hierarchy_summary(index: ClassIndex) -> dict:
    """
    获取类层次结构摘要
    
    返回:
        {
            "total_classes": int,
            "classes_with_bases": int,
            "max_inheritance_depth": int,
            "most_common_bases": [(base_name, count), ...]
        }
    """
    from collections import Counter
    
    base_counter = Counter()
    classes_with_bases = 0
    
    for entry in index.classes.values():
        if entry.bases:
            classes_with_bases += 1
            for base in entry.bases:
                base_counter[base] += 1
    
    return {
        "total_classes": len(index),
        "classes_with_bases": classes_with_bases,
        "most_common_bases": base_counter.most_common(10)
    }
