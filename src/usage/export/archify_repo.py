"""git 身份 + 本机 archify CLI。

archify 用 ``meta.repository``（地址 + 40 位 commit）把节点的 ``sources`` 钉在已提交的
字节上，``--repo-root`` 时逐个核对路径和行号。索引是按工作树建的，所以被引用的文件
有未提交改动时要说出来：那几处行号可能和 commit 里的对不上。
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

_SKILL_HOMES = (".agents", ".claude", ".codex", ".cursor", ".config/opencode", ".opencode")


def _git(root, *args):
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _strip_userinfo(url):
    return re.sub(r"^(https?://)[^/@]+@", r"\1", url)


def repository_identity(root):
    """返回 (meta.repository 或 None, 有未提交改动的路径集合)。不是 git 仓库就是 (None, set())。"""
    revision = _git(root, "rev-parse", "HEAD")
    if not revision or not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        return None, set()
    url = _strip_userinfo(_git(root, "remote", "get-url", "origin") or "")
    web = re.match(r"^https://(github\.com|gitee\.com)/", url)
    repo = {"url": url or Path(root).resolve().as_uri(), "revision": revision,
            "link_mode": "web" if web else "local-only"}
    if web:
        repo["provider"] = "github" if web.group(1) == "github.com" else "gitee"
    dirty = set()
    for line in (_git(root, "status", "--porcelain") or "").splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path:
            dirty.add(path)
    return repo, dirty


def find_archify():
    """找 archify 的 bin/archify.mjs：先看 ARCHIFY_CLI，再看各家 agent 的全局 skill 目录。"""
    explicit = os.environ.get("ARCHIFY_CLI")
    if explicit and Path(explicit).expanduser().is_file():
        return Path(explicit).expanduser()
    home = Path.home()
    for base in _SKILL_HOMES:
        cand = home / base / "skills" / "archify" / "bin" / "archify.mjs"
        if cand.is_file():
            return cand
    return None


def find_node():
    explicit = os.environ.get("ARCHIFY_NODE")
    if explicit and Path(explicit).expanduser().is_file():
        return str(Path(explicit).expanduser())
    return shutil.which("node")


def deliver_command(cli, node, ir_path, html_path, root, with_repo):
    cmd = [node or "node", str(cli or "<archify>/bin/archify.mjs"), "deliver", "architecture",
           str(ir_path), str(html_path), "--json", "--quality", "showcase"]
    if with_repo:
        cmd += ["--repo-root", str(root)]
    return cmd


def run_deliver(cmd):
    """跑 archify deliver。返回 (退出码, stdout, stderr)。"""
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return out.returncode, out.stdout, out.stderr
