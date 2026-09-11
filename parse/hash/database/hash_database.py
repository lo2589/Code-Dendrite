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

from parse.hash.file_hash import get_file_hash
from parse.hash.ast_hash import get_ast_hash

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
        # 本进程 load 之后显式删除的文件 key；save 时 rebase 要尊重这些删除，
        # 不能被别的进程磁盘快照里的旧条目复活。
        self._removed: set = set()
    
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
    
    def _merge_concurrent_writes(self):
        """
        如果本进程 load 之后，别的 cdd 进程已经写过这个库，把它们新增/更新的
        文件条目合并回来（本进程内存里的条目优先，本进程显式删除的不复活）。
        必须在持有 db_lock 时调用。
        """
        if not self.db_path.exists():
            return
        try:
            disk = json.loads(self.db_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        disk_files = disk.get("files", {})
        if not disk_files:
            return
        merged = dict(disk_files)
        merged.update(self.data["files"])          # 本进程的写优先
        for key in self._removed:                  # 尊重本进程的删除
            merged.pop(key, None)
        self.data["files"] = merged

    def save(self):
        """
        原子写入数据库（防止损坏）。

        持有跨进程 db_lock，并在写前 rebase 到磁盘当前状态，避免并发的
        cdd 进程用各自 load 时的旧快照互相覆盖。
        """
        try:
            from base.shared.dblock import db_lock
        except ImportError:
            from base.shared.dblock import db_lock

        with db_lock(self.db_path):
            self._merge_concurrent_writes()
            self._save_locked()

    def _save_locked(self):
        # 更新元数据
        self.data["_meta"]["updated_at"] = datetime.now().isoformat()
        self.data["_meta"]["file_count"] = len(self.data["files"])

        # Keep temp files out of the scanned project root; otherwise Windows can
        # expose them to the incremental scanner before os.replace finishes.
        tmp_dir = self.root / ".codedendrite"
        tmp_dir.mkdir(exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, prefix="hashdb_", suffix=".json")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.db_path)
        except Exception:
            self.db_path.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
    
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
                rel_path = abs_path.relative_to(self.root).as_posix()
            else:
                rel_path = Path(fp).as_posix()
                abs_path = self.root / fp
            
            if not abs_path.exists():
                # 文件不存在，从数据库移除
                if rel_path in self.data["files"]:
                    del self.data["files"][rel_path]
                self._removed.add(rel_path)
                continue

            # 检测语言
            language = self._detect_language(abs_path)
            if not language:
                if rel_path in self.data["files"]:
                    del self.data["files"][rel_path]
                self._removed.add(rel_path)
                continue
            
            # 计算哈希
            file_hash = get_file_hash(str(abs_path))
            ast_hash = get_ast_hash(str(abs_path), language)
            
            if file_hash:
                self.data["files"][rel_path] = {
                    "hash": file_hash,
                    "ast_hash": ast_hash,
                    "language": language,
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
            self._removed.add(file_path)
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
            from base.shared.codedendrite_ignore import CodeDendriteIgnore
        except ImportError:
            from base.shared.codedendrite_ignore import CodeDendriteIgnore

        root_path = Path(root)
        ignore = CodeDendriteIgnore(root)
        new_files = []
        def _on_walk_error(error):
            return None

        for dirpath, dirnames, filenames in os.walk(root_path, onerror=_on_walk_error):
            dp = Path(dirpath)
            dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.py")]
            for fname in filenames:
                fp = dp / fname
                if not ignore.should_scan(fp):
                    continue
                try:
                    rel = fp.relative_to(root_path).as_posix()
                except ValueError:
                    continue
                if not self._detect_language(fp):
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
            from base.shared.codedendrite_ignore import CodeDendriteIgnore
        except ImportError:
            from base.shared.codedendrite_ignore import CodeDendriteIgnore

        ignore = CodeDendriteIgnore(str(self.root))
        stale = []

        pruned = False

        for rel_path, info in list(self.data["files"].items()):
            abs_path = self.root / rel_path
            if not ignore.should_scan(abs_path) or not self._detect_language(abs_path):
                del self.data["files"][rel_path]
                self._removed.add(rel_path)
                pruned = True
                continue

            if not abs_path.exists():
                stale.append(rel_path)
                continue

            current_hash = get_file_hash(str(abs_path))
            if current_hash != info.get("hash", ""):
                stale.append(rel_path)

        if pruned:
            self.save()

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
