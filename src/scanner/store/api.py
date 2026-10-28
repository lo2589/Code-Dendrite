"""
codeGenome/api.py - 查询接口
=============================
统一的查询接口，支持自然语言和结构化查询。
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from scanner.shared.genome_types import CodeAnchor, AnchorIndex
from scanner.language.python.genome import extract_python_file, extract_python_directory, PythonExtractor
from scanner.language.cpp.genome import extract_cpp_file, extract_cpp_directory
from scanner.store.database import AnchorDatabase, ProjectGenome


class GenomeQuery:
    """
    代码基因组查询接口

    使用示例:
        query = GenomeQuery("/path/to/project")
        query.scan()

        # 查找类
        classes = query.find_classes("Robot")

        # 查找导入
        imports = query.find_imports("torch")

        # 查找裸代码
        bare_code = query.find_bare_code_blocks()
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.db = AnchorDatabase(str(self.project_root / ".code_genome_db.json"))
        self._loaded = False

    def scan(self):
        """扫描项目"""
        self.db.clear()
        self.parse_failures = []
        self.auto_fixed = []

        py_extractor = PythonExtractor()
        py_index = py_extractor.extract_directory(str(self.project_root))
        self.db.add_index(py_index)
        self.parse_failures.extend(py_index.parse_failures)
        self.auto_fixed.extend(py_index.auto_fixed)

        cpp_dirs = ['src', 'include', '.']
        for cpp_dir in cpp_dirs:
            dir_path = self.project_root / cpp_dir
            if dir_path.exists():
                for ext in ['.cpp', '.h', '.hpp', '.cc', '.cxx']:
                    if list(dir_path.glob(f'*{ext}')):
                        cpp_index = extract_cpp_directory(
                            str(dir_path),
                            project_root=str(self.project_root),
                        )
                        self.db.add_index(cpp_index)
                        break

        self.db.save()
        self._loaded = True

    def reload(self):
        """重新加载数据库"""
        self._load()

    def _load(self):
        """加载数据库"""
        self.db = AnchorDatabase(str(self.project_root / ".code_genome_db.json"))
        self._loaded = len(self.db) > 0

    def ensure_loaded(self):
        """确保数据库已加载"""
        if not self._loaded:
            self._load()

    def find_by_id(self, anchor_id: str) -> Optional[CodeAnchor]:
        """通过 ID 查找锚点"""
        self.ensure_loaded()
        return self.db.get(anchor_id)

    def find_by_hash(self, hash_val: str) -> Optional[CodeAnchor]:
        """通过哈希查找锚点"""
        self.ensure_loaded()
        return self.db.get_by_hash(hash_val)

    def find_by_location(self, file: str, line: int) -> Optional[CodeAnchor]:
        """通过位置查找锚点"""
        self.ensure_loaded()
        anchors = self.db.get_by_file(file)
        for anchor in anchors:
            if anchor.line_start <= line <= anchor.line_end:
                return anchor
        return None

    def find_by_code(self, code: str) -> Optional[CodeAnchor]:
        """通过代码内容查找锚点"""
        self.ensure_loaded()
        return self.db.find_identical(code)

    def search(self, query: str) -> List[CodeAnchor]:
        """搜索锚点"""
        self.ensure_loaded()
        return self.db.search(query)

    def find_classes(self, name: str = None) -> List[CodeAnchor]:
        """查找类"""
        self.ensure_loaded()
        if name:
            return [a for a in self.db.get_by_category("classes")
                    if name.lower() in a.name.lower()]
        return self.db.get_by_category("classes")

    def find_structs(self, name: str = None) -> List[CodeAnchor]:
        """查找结构体"""
        self.ensure_loaded()
        if name:
            return [a for a in self.db.get_by_category("structs")
                    if name.lower() in a.name.lower()]
        return self.db.get_by_category("structs")

    def find_functions(self, name: str = None) -> List[CodeAnchor]:
        """查找函数"""
        self.ensure_loaded()
        if name:
            return [a for a in self.db.get_by_category("functions")
                    if name.lower() in a.name.lower()]
        return self.db.get_by_category("functions")

    def find_methods(self, class_name: str = None) -> List[CodeAnchor]:
        """查找方法"""
        self.ensure_loaded()
        methods = self.db.get_by_category("methods")
        if class_name:
            return [m for m in methods if class_name in m.parent_id]
        return methods

    def find_imports(self, name: str = None) -> List[CodeAnchor]:
        """查找导入"""
        self.ensure_loaded()
        imports = self.db.get_by_category("imports") + self.db.get_by_category("includes")
        if name:
            return [i for i in imports if name.lower() in i.name.lower()]
        return imports

    def find_main_blocks(self) -> List[CodeAnchor]:
        """查找 __main__ 块"""
        self.ensure_loaded()
        return self.db.get_by_category("__main__")

    def find_bare_code_blocks(self) -> List[CodeAnchor]:
        """查找裸代码块（可能存在隐蔽执行）"""
        self.ensure_loaded()
        statements = self.db.get_by_category("statements")
        return [s for s in statements if not s.parent_id]

    def find_assignments(self, name: str = None) -> List[CodeAnchor]:
        """查找赋值"""
        self.ensure_loaded()
        assigns = self.db.get_by_category("assigns")
        if name:
            return [a for a in assigns if name.lower() in a.name.lower()]
        return assigns

    def find_variables(self, name: str = None) -> List[CodeAnchor]:
        """查找变量"""
        self.ensure_loaded()
        vars_list = self.db.get_by_category("vars")
        if name:
            return [v for v in vars_list if name.lower() in v.name.lower()]
        return vars_list

    def get_file_anchors(self, file: str) -> List[CodeAnchor]:
        """获取文件的所有锚点"""
        self.ensure_loaded()
        return self.db.get_by_file(file)

    def get_file_structure(self, file: str) -> Dict[str, Any]:
        """获取文件的结构"""
        self.ensure_loaded()
        anchors = self.db.get_by_file(file)

        structure = {
            "file": file,
            "imports": [],
            "assignments": [],
            "main_blocks": [],
            "bare_statements": [],
            "classes": [],
            "functions": []
        }

        for anchor in anchors:
            if anchor.category == "imports":
                structure["imports"].append(anchor)
            elif anchor.category == "assigns":
                structure["assignments"].append(anchor)
            elif anchor.category == "__main__":
                structure["main_blocks"].append(anchor)
            elif anchor.category == "statements":
                structure["bare_statements"].append(anchor)
            elif anchor.category == "classes":
                structure["classes"].append(anchor)
            elif anchor.category == "functions":
                structure["functions"].append(anchor)

        return structure

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        self.ensure_loaded()
        return self.db.get_stats()

    def check_file_drift(self, file: str) -> Dict[str, Any]:
        """检查文件变更"""
        from scanner.language.python.genome import extract_python_file
        from scanner.language.cpp.genome import extract_cpp_file

        if file.endswith('.py'):
            current_index = extract_python_file(file)
        elif file.endswith(('.cpp', '.h', '.hpp', '.cc', '.cxx', '.hxx')):
            current_index = extract_cpp_file(file)
        else:
            return {"status": "unsupported"}

        current_anchors = {a.hash: a for a in current_index.anchors.values()}
        old_anchors = {a.hash: a for a in self.db.get_by_file(file)}

        added = [current_anchors[h] for h in current_anchors if h not in old_anchors]
        removed = [old_anchors[h] for h in old_anchors if h not in current_anchors]

        return {
            "status": "checked",
            "file": file,
            "added": len(added),
            "removed": len(removed),
            "added_anchors": [
                {
                    "id": a.id,
                    "name": a.name,
                    "category": a.category,
                    "line": a.line_start
                }
                for a in added
            ],
            "removed_anchors": [
                {
                    "id": a.id,
                    "name": a.name,
                    "category": a.category,
                    "line": a.line_start
                }
                for a in removed
            ]
        }

    def generate_report(self) -> str:
        """生成项目报告"""
        self.ensure_loaded()
        stats = self.get_stats()

        lines = [
            "# Code Genome Report",
            "",
            f"Total Anchors: {stats['total']}",
            "",
            "## By Language",
        ]

        for lang, count in stats['by_language'].items():
            lines.append(f"- {lang}: {count}")

        lines.append("")
        lines.append("## By Category")

        for cat, count in stats['by_category'].items():
            lines.append(f"- {cat}: {count}")

        lines.append("")
        lines.append("## Files")

        for file, anchor_ids in self.db.index.file_anchors.items():
            lines.append(f"- {file}: {len(anchor_ids)} anchors")

        return "\n".join(lines)


def create_query(project_root: str) -> GenomeQuery:
    """创建查询接口"""
    return GenomeQuery(project_root)


def scan_project(project_root: str) -> GenomeQuery:
    """扫描项目并返回查询接口"""
    query = GenomeQuery(project_root)
    query.scan()
    return query
