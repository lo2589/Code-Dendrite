"""
dblock - 磁盘数据库的跨平台进程锁
=================================
多个 cdd 进程 / agent 可能同时对同一个索引库（.code_hash_db.json /
.code_genome_db.json / .codedendrite/*）做 load -> mutate -> save。
没有锁时，后写者会用自己 load 时的旧快照整体覆盖先写者的改动。

用法::

    from scanner.shared.dblock import db_lock
    with db_lock(self.db_path):
        self._merge_concurrent_writes()   # 把别的进程刚写进去的合并回来
        ...原子写...

平台：
- POSIX  -> fcntl.flock(LOCK_EX)          阻塞直到拿到独占锁
- Windows -> msvcrt.locking(LK_LOCK)      轮询直到拿到
- 其它    -> no-op（只保证单进程正确，退化为原来的行为）
"""
from __future__ import annotations

import contextlib
import os
import time

try:  # POSIX
    import fcntl

    def _acquire(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def _release(handle) -> None:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass

except ImportError:  # pragma: no cover - Windows / exotic
    try:
        import msvcrt

        def _acquire(handle) -> None:
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    return
                except OSError:
                    time.sleep(0.1)

        def _release(handle) -> None:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass

    except ImportError:  # no locking primitive available

        def _acquire(handle) -> None:
            return None

        def _release(handle) -> None:
            return None


@contextlib.contextmanager
def db_lock(target_path):
    """
    对 `target_path` 持有一个独占的建议锁，直到 with 块结束。

    锁本身落在 `<target_path>.lock` 上，从不删除（删除会引入 TOCTOU 竞态），
    体积为 0。同一进程内可重入由 OS 语义决定，跨进程严格互斥。
    """
    lock_path = str(target_path) + ".lock"
    parent = os.path.dirname(lock_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    handle = open(lock_path, "a+")
    try:
        _acquire(handle)
        yield
    finally:
        _release(handle)
        handle.close()
