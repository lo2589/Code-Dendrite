"""
codeGenome/database.py - 锚点数据库
======================================
持久化存储和管理代码锚点。
"""

import json
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from .types import CodeAnchor, AnchorIndex


class AnchorDatabase:
    """
    锚点数据库

    持久化存储锚点，支持：
    - JSON 文件存储
    - 按文件/类别查询
    - Hash 查找
    - 变更检测
    """

    def __init__(self, db_path: str = ".code_genome_db.json"):
        self.db_path = db_path
        self.index = AnchorIndex()
        self._load()

    def _load(self):
        """加载数据库"""
        if Path(self.db_path).exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._deserialize(data)
            except (json.JSONDecodeError, KeyError):
                self.index = AnchorIndex()

    def _save(self):
        """保存数据库"""
        data = self._serialize()
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _serialize(self) -> dict:
        """序列化数据库"""
        return {
            "anchors": {
                anchor_id: anchor.to_dict()
                for anchor_id, anchor in self.index.anchors.items()
            },
            "file_anchors": self.index.file_anchors,
            "category_anchors": self.index.category_anchors,
            "hash_toId": self.index.hash_to_id
        }

    def _deserialize(self, data: dict):
        """反序列化数据库"""
        self.index = AnchorIndex()

        anchors_data = data.get("anchors", {})
        for anchor_id, anchor_dict in anchors_data.items():
            anchor = CodeAnchor(**anchor_dict)
            self.index.anchors[anchor_id] = anchor

        self.index.file_anchors = data.get("file_anchors", {})
        self.index.category_anchors = data.get("category_anchors", {})
        self.index.hash_to_id = data.get("hashToId", {})

    def add(self, anchor: CodeAnchor):
        """添加锚点"""
        self.index.add(anchor)

    def add_index(self, index: AnchorIndex):
        """添加锚点索引"""
        for anchor in index.anchors.values():
            self.index.add(anchor)

    def get(self, anchor_id: str) -> Optional[CodeAnchor]:
        """获取锚点"""
        return self.index.get(anchor_id)

    def get_by_hash(self, hash_val: str) -> Optional[CodeAnchor]:
        """通过哈希获取锚点"""
        return self.index.get_by_hash(hash_val)

    def get_by_file(self, file: str) -> List[CodeAnchor]:
        """获取文件的锚点"""
        return self.index.get_by_file(file)

    def get_by_category(self, category: str) -> List[CodeAnchor]:
        """获取类别的锚点"""
        return self.index.get_by_category(category)

    def search(self, query: str) -> List[CodeAnchor]:
        """
        搜索锚点

        支持：
        - 按 ID 搜索
        - 按名称搜索
        - 按文件搜索
        """
        results = []
        query_lower = query.lower()

        for anchor in self.index.anchors.values():
            if query_lower in anchor.id.lower():
                results.append(anchor)
            elif query_lower in anchor.name.lower():
                results.append(anchor)
            elif query_lower in anchor.file.lower():
                results.append(anchor)

        return results

    def find_identical(self, code: str) -> Optional[CodeAnchor]:
        """查找相同代码的锚点"""
        hash_val = hashlib.sha1(code.encode()).hexdigest()[:12]
        return self.get_by_hash(hash_val)

    def save(self):
        """保存数据库"""
        self._save()

    def clear(self):
        """清空数据库"""
        self.index = AnchorIndex()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.index.get_stats()

    def __len__(self) -> int:
        return len(self.index)

    def get_all_anchors(self) -> List[CodeAnchor]:
        """获取所有锚点"""
        return list(self.index.anchors.values())


class ProjectGenome:
    """
    项目基因组 - 管理整个项目的锚点
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.db = AnchorDatabase(str(self.project_root / ".code_genome_db.json"))

    def scan(self):
        """扫描项目"""
        from .python_extractor import extract_python_directory
        from .cpp_extractor import extract_cpp_directory

        self.db.clear()

        if (self.project_root / "src").exists():
            py_index = extract_python_directory(str(self.project_root / "src"))
            self.db.add_index(py_index)

        else:
            py_index = extract_python_directory(str(self.project_root))
            self.db.add_index(py_index)

        cpp_dirs = ['src', 'include', 'lib']
        for cpp_dir in cpp_dirs:
            if (self.project_root / cpp_dir).exists():
                from .cpp_extractor import extract_cpp_directory
                cpp_index = extract_cpp_directory(str(self.project_root / cpp_dir))
                self.db.add_index(cpp_index)

        self.db.save()

    def find_anchor_by_hash(self, hash_val: str) -> Optional[CodeAnchor]:
        """通过哈希查找锚点"""
        return self.db.get_by_hash(hash_val)

    def find_anchor_by_location(self, file: str, line: int) -> Optional[CodeAnchor]:
        """通过位置查找锚点"""
        anchors = self.db.get_by_file(file)
        for anchor in anchors:
            if anchor.line_start <= line <= anchor.line_end:
                return anchor
        return None

    def get_imports(self, file: str) -> List[CodeAnchor]:
        """获取文件的导入"""
        anchors = self.db.get_by_file(file)
        return [a for a in anchors if a.is_import]

    def get_classes(self, file: str) -> List[CodeAnchor]:
        """获取文件的类"""
        anchors = self.db.get_by_file(file)
        return [a for a in anchors if a.is_class]

    def get_main_blocks(self, file: str) -> List[CodeAnchor]:
        """获取文件的 __main__ 块"""
        anchors = self.db.get_by_file(file)
        return [a for a in anchors if a.is_main_block]

    def get_statement_blocks(self, file: str) -> List[CodeAnchor]:
        """获取文件的裸语句块"""
        anchors = self.db.get_by_file(file)
        return [a for a in anchors if a.category == "statements"]

    def check_file_drift(self, file: str) -> Dict[str, Any]:
        """检查文件的代码漂移"""
        from .python_extractor import extract_python_file
        from .cpp_extractor import extract_cpp_file

        if file.endswith('.py'):
            current_index = extract_python_file(file)
        elif file.endswith(('.cpp', '.h', '.hpp', '.cc', '.cxx', '.hxx')):
            current_index = extract_cpp_file(file)
        else:
            return {"status": "unsupported"}

        current_anchors = {
            a.hash: a
            for a in current_index.anchors.values()
        }

        old_anchors = {
            a.hash: a
            for a in self.db.get_by_file(file)
        }

        added = [current_anchors[h] for h in current_anchors if h not in old_anchors]
        removed = [old_anchors[h] for h in old_anchors if h not in current_anchors]
        unchanged = [current_anchors[h] for h in current_anchors if h in old_anchors]

        return {
            "status": "checked",
            "file": file,
            "added": len(added),
            "removed": len(removed),
            "unchanged": len(unchanged),
            "added_anchors": added,
            "removed_anchors": removed
        }

    def save(self):
        """保存数据库"""
        self.db.save()

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.db.get_stats()
