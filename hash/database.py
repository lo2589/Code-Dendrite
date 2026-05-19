"""
database.py - 哈希数据库管理
============================
管理文件哈希的持久化存储。
"""

import json
import os
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from .file_hash import get_file_hash
from .ast_hash import get_ast_hash


class ChangeType(Enum):
    """变更类型枚举"""
    UNCHANGED = "unchanged"      # 哈希相同
    CHANGED = "changed"          # 哈希不同
    ADDED = "added"              # 新文件
    DELETED = "deleted"          # 文件删除
    REFACTORED = "refactored"    # AST结构变化但相似度高


def classify_change(
    file_path: str,
    old_hash: str,
    new_hash: str,
    old_ast_hash: Optional[str] = None,
    new_ast_hash: Optional[str] = None
) -> ChangeType:
    """
    分类变更类型
    
    参数:
        file_path: 文件路径
        old_hash: 旧文件哈希
        new_hash: 新文件哈希
        old_ast_hash: 旧AST哈希（可选）
        new_ast_hash: 新AST哈希（可选）
    
    返回:
        ChangeType枚举值
    """
    # 文件删除
    if not Path(file_path).exists():
        return ChangeType.DELETED
    
    # 新文件
    if not old_hash:
        return ChangeType.ADDED
    
    # 哈希相同，未变化
    if old_hash == new_hash:
        return ChangeType.UNCHANGED
    
    # 哈希不同，检查AST
    if old_ast_hash and new_ast_hash:
        if old_ast_hash == new_ast_hash:
            # AST相同但文件哈希不同 -> 格式变化
            return ChangeType.CHANGED
        else:
            # AST也变了 -> 重构
            return ChangeType.REFACTORED
    
    return ChangeType.CHANGED


class HashDatabase:
    """
    哈希数据库
    
    存储文件: .code_hash_db.json
    格式: {
        "_meta": {
            "version": 1,
            "updated_at": "2026-04-02T10:00:00",
            "file_count": 100
        },
        "files": {
            "path/to/file.py": {
                "hash": "abcd1234",
                "ast_hash": "efgh5678",
                "language": "python",
                "updated_at": "2026-04-02T10:00:00"
            }
        }
    }
    """
    
    DB_FILE = ".code_hash_db.json"
    DB_VERSION = 1
    
    def __init__(self, root: str):
        """
        初始化哈希数据库
        
        参数:
            root: 项目根目录
        """
        self.root = Path(root)
        self.db_path = self.root / self.DB_FILE
        self.data = self.load()
    
    def load(self) -> Dict:
        """
        加载数据库
        
        返回:
            数据库字典
        """
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding='utf-8'))
                # 确保基本结构存在
                if "_meta" not in data:
                    data["_meta"] = {"version": self.DB_VERSION}
                if "files" not in data:
                    data["files"] = {}
                return data
            except json.JSONDecodeError:
                pass
        
        return {
            "_meta": {
                "version": self.DB_VERSION,
                "created_at": datetime.now().isoformat(),
                "file_count": 0
            },
            "files": {}
        }
    
    def save(self):
        """
        原子写入数据库（防止损坏）
        """
        # 更新元数据
        self.data["_meta"]["updated_at"] = datetime.now().isoformat()
        self.data["_meta"]["file_count"] = len(self.data["files"])
        
        # 使用临时文件 + rename实现原子写入
        fd, tmp_path = tempfile.mkstemp(dir=self.root, suffix=".json")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.db_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    
    def update(self, file_paths: List[str]) -> int:
        """
        更新文件哈希
        
        参数:
            file_paths: 文件路径列表（相对或绝对）
        
        返回:
            成功更新的文件数量
        """
        count = 0
        now = datetime.now().isoformat()
        
        for fp in file_paths:
            # 处理路径
            if os.path.isabs(fp):
                abs_path = Path(fp)
                rel_path = str(abs_path.relative_to(self.root))
            else:
                rel_path = fp
                abs_path = self.root / fp
            
            if not abs_path.exists():
                # 文件不存在，从数据库移除
                if rel_path in self.data["files"]:
                    del self.data["files"][rel_path]
                continue
            
            # 检测语言
            language = self._detect_language(abs_path)
            
            # 计算哈希
            file_hash = get_file_hash(str(abs_path))
            ast_hash = get_ast_hash(str(abs_path), language) if language else ""
            
            if file_hash:
                self.data["files"][rel_path] = {
                    "hash": file_hash,
                    "ast_hash": ast_hash,
                    "language": language or "unknown",
                    "updated_at": now
                }
                count += 1
        
        if count > 0:
            self.save()
        
        return count
    
    def get(self, file_path: str) -> Optional[Dict]:
        """
        获取文件的哈希信息
        
        参数:
            file_path: 相对文件路径
        
        返回:
            哈希信息字典，不存在返回None
        """
        return self.data["files"].get(file_path)
    
    def get_all(self) -> Dict[str, str]:
        """
        获取所有文件的哈希映射
        
        返回:
            {文件路径: 文件哈希} 字典
        """
        return {
            path: info["hash"]
            for path, info in self.data["files"].items()
        }
    
    def remove(self, file_path: str):
        """
        从数据库移除文件
        
        参数:
            file_path: 相对文件路径
        """
        if file_path in self.data["files"]:
            del self.data["files"][file_path]
            self.save()
    
    def clear(self):
        """清空数据库"""
        self.data["files"] = {}
        self.save()
    
    def get_new_files(self, root: str) -> List[str]:
        """
        扫描 root 下的文件，返回不在 DB 中的新文件（上次 build 后新增的）。
        使用 CodeDendriteIgnore 过滤，与 rebuild 保持一致。
        """
        import os
        from pathlib import Path
        try:
            from shared.codedendrite_ignore import CodeDendriteIgnore
        except ImportError:
            from tools.CodeDendrite.shared.codedendrite_ignore import CodeDendriteIgnore

        root_path = Path(root)
        ignore = CodeDendriteIgnore(root)
        new_files = []
        for dirpath, dirnames, filenames in os.walk(root_path):
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.py")]
            for fname in filenames:
                fp = dp / fname
                if not ignore.should_scan(fp):
                    continue
                try:
                    rel = str(fp.relative_to(root_path))
                except ValueError:
                    continue
                if rel not in self.data["files"]:
                    new_files.append(rel)
        return new_files

    def get_stale_files(self) -> List[str]:
        """
        获取哈希过期的文件列表（当前哈希与存储哈希不同）

        返回:
            过期文件的相对路径列表
        """
        try:
            from shared.codedendrite_ignore import CodeDendriteIgnore
        except ImportError:
            from tools.CodeDendrite.shared.codedendrite_ignore import CodeDendriteIgnore

        ignore = CodeDendriteIgnore(str(self.root))
        stale = []

        for rel_path, info in self.data["files"].items():
            abs_path = self.root / rel_path
            if not ignore.should_scan(abs_path):
                continue

            if not abs_path.exists():
                stale.append(rel_path)
                continue

            current_hash = get_file_hash(str(abs_path))
            if current_hash != info.get("hash", ""):
                stale.append(rel_path)

        return stale
    
    def _detect_language(self, file_path: Path) -> Optional[str]:
        """根据文件扩展名检测语言"""
        ext_map = {
            ".py": "python",
            ".pyw": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".java": "java",
            ".c": "cpp",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
            ".hxx": "cpp",
        }
        return ext_map.get(file_path.suffix.lower())
    
    def __len__(self) -> int:
        """返回数据库中的文件数量"""
        return len(self.data["files"])
    
    def __contains__(self, file_path: str) -> bool:
        """检查文件是否在数据库中"""
        return file_path in self.data["files"]
