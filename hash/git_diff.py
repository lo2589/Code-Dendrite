"""
git_diff.py - Git变更检测 (Medium L1-003)
==========================================
获取Git仓库中的变更文件列表。
"""

import subprocess
from pathlib import Path
from typing import List, Optional


def get_changed_files(root: str, since_commit: Optional[str] = None) -> List[str]:
    """
    获取变更文件列表
    
    参数:
        root: 项目根目录
        since_commit: 可选，与指定commit比较。
                      None表示获取未提交的变更（工作区+暂存区）
    
    返回:
        相对路径列表，非Git仓库返回空列表
    
    实现方式:
        1. 如果指定commit: git diff --name-only <commit>
        2. 如果未指定: git diff --name-only HEAD（未提交的变更）
                      + git diff --name-only --cached（暂存区变更）
        3. 非Git仓库: 返回空列表
    
    潜在问题处理:
        - .git目录不存在: 返回空列表
        - git命令不存在: 返回空列表
        - 空仓库（无commit）: 尝试 git status 获取
    """
    root_path = Path(root)
    
    # 检查是否是Git仓库
    git_dir = root_path / ".git"
    if not git_dir.exists():
        return []
    
    changed_files = set()
    
    try:
        if since_commit:
            # 与指定commit比较
            result = _run_git_command(
                ["git", "diff", "--name-only", since_commit],
                cwd=root
            )
            if result:
                changed_files.update(result)
        else:
            # 获取工作区变更
            result = _run_git_command(
                ["git", "diff", "--name-only"],
                cwd=root
            )
            if result:
                changed_files.update(result)
            
            # 获取暂存区变更
            result = _run_git_command(
                ["git", "diff", "--name-only", "--cached"],
                cwd=root
            )
            if result:
                changed_files.update(result)
            
            # 获取未跟踪文件
            result = _run_git_command(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=root
            )
            if result:
                changed_files.update(result)
    
    except Exception:
        # Git相关错误，尝试获取所有未提交变更
        try:
            result = _run_git_status(root)
            if result:
                changed_files.update(result)
        except Exception:
            return []
    
    return sorted(list(changed_files))


def get_commits_since(root: str, since: str, until: Optional[str] = None) -> List[str]:
    """
    获取指定时间范围内的commit SHA列表
    
    参数:
        root: 项目根目录
        since: 开始时间/commit
        until: 结束时间/commit（默认HEAD）
    
    返回:
        commit SHA列表（从新到旧）
    """
    cmd = ["git", "log", "--format=%H", f"--since={since}"]
    if until:
        cmd.append(f"--until={until}")
    
    result = _run_git_command(cmd, cwd=root)
    return result if result else []


def get_file_at_commit(root: str, file_path: str, commit: str) -> Optional[str]:
    """
    获取指定commit时的文件内容
    
    参数:
        root: 项目根目录
        file_path: 相对文件路径
        commit: commit SHA
    
    返回:
        文件内容，文件不存在返回None
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{file_path}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return result.stdout
        return None
    
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def get_last_modified_commit(root: str, file_path: str) -> Optional[str]:
    """
    获取文件最后修改的commit SHA
    
    参数:
        root: 项目根目录
        file_path: 相对文件路径
    
    返回:
        commit SHA，失败返回None
    """
    result = _run_git_command(
        ["git", "log", "-1", "--format=%H", "--", file_path],
        cwd=root
    )
    return result[0] if result else None


def _run_git_command(cmd: List[str], cwd: str, timeout: int = 10) -> List[str]:
    """
    执行Git命令并返回输出行列表
    
    返回:
        输出行列表（去除空行）
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            return []
        
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []


def _run_git_status(root: str) -> List[str]:
    """
    使用git status获取变更文件（用于空仓库场景）
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return []
        
        files = []
        for line in result.stdout.splitlines():
            if len(line) > 3:
                # 格式: "XY filename" 或 "XY filename -> newname"
                file_part = line[3:].strip()
                if " -> " in file_part:
                    # 重命名情况，取新文件名
                    file_part = file_part.split(" -> ")[1]
                files.append(file_part)
        
        return files
    
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
