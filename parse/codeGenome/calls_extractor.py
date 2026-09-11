"""
calls_extractor.py — 补全锚点的 metadata.calls 字段

现有锚点的 metadata.calls 大多为空，导致 pathTracer 无法构建调用图。
本模块扫描已有锚点库，用 AST 提取每个函数的调用关系，写回 anchors.json。

用法：
    python calls_extractor.py --project /path/to/project
    python calls_extractor.py --project . --dry-run   # 只打印不写入

设计原则：
    - 只补全 calls 字段，不修改其他字段
    - 支持 Python（AST精确）和其他语言（正则降级）
    - 增量更新：已有 calls 的锚点跳过，除非 --force
"""
from __future__ import annotations

import ast
import re
import json
import sys
import argparse
from pathlib import Path
from typing import Optional


# ── Python AST 调用提取 ────────────────────────────────────


class CallExtractorVisitor(ast.NodeVisitor):
    """从 AST 中提取函数调用列表。"""

    def __init__(self):
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call):
        name = self._get_call_name(node)
        if name:
            self.calls.append(name)
        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            # obj.method → method（只取方法名，避免过度具体）
            return node.func.attr
        return None


def extract_calls_python(source_code: str) -> list[str]:
    """从 Python 源码提取调用的函数名列表。"""
    try:
        tree = ast.parse(source_code)
        visitor = CallExtractorVisitor()
        visitor.visit(tree)
        # 去重，保留顺序
        seen = set()
        result = []
        for name in visitor.calls:
            if name not in seen and not name.startswith("_"):
                seen.add(name)
                result.append(name)
        return result
    except SyntaxError:
        return []


# ── 其他语言：正则降级 ────────────────────────────────────


CALL_PATTERNS = {
    "ts": re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('),
    "js": re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('),
    "java": re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('),
    "cpp": re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('),
    "go": re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('),
    "rust": re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('),
}

# 过滤掉语言关键字和常见控制流（不是函数调用）
KEYWORDS = {
    "if", "for", "while", "switch", "return", "new", "delete",
    "class", "def", "fn", "func", "function", "async", "await",
    "import", "from", "try", "catch", "except", "finally",
    "print", "len", "range", "type", "isinstance", "super",
}


def extract_calls_regex(source_code: str, language: str) -> list[str]:
    """用正则从源码提取调用（降级方案）。"""
    pattern = CALL_PATTERNS.get(language)
    if not pattern:
        return []
    names = pattern.findall(source_code)
    seen = set()
    result = []
    for name in names:
        if name not in KEYWORDS and name not in seen and not name.startswith("_"):
            seen.add(name)
            result.append(name)
    return result[:30]  # 正则容易过多，限制数量


# ── 主流程 ────────────────────────────────────────────────


def extract_calls_for_anchor(anchor: dict, project_root: Path) -> list[str]:
    """
    为单个锚点提取调用列表。

    优先从锚点的 code 字段提取，
    其次从源文件按行号切片读取。
    """
    language = anchor.get("language", "py")
    source = ""

    # 优先用已存储的 code
    if anchor.get("code"):
        source = anchor["code"]
    else:
        # 从源文件读取
        file_path = project_root / anchor.get("file", "")
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                start = anchor.get("line_start", 1) - 1
                end = anchor.get("line_end", start + 1)
                source = "".join(lines[max(0, start):end])
            except Exception:
                return []

    if not source:
        return []

    if language == "py":
        return extract_calls_python(source)
    else:
        return extract_calls_regex(source, language)


def patch_anchors_calls(
    anchors_path: Path,
    project_root: Path,
    dry_run: bool = False,
    force: bool = False,
    verbose: bool = False,
) -> dict:
    """
    扫描 anchors.json，补全所有锚点的 metadata.calls 字段。

    返回统计信息。
    """
    if not anchors_path.exists():
        print(f"[错误] 锚点文件不存在: {anchors_path}")
        return {}

    with open(anchors_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    anchors = data.get("anchors", data)
    stats = {"total": 0, "patched": 0, "skipped": 0, "failed": 0}

    for anchor_id, anchor in anchors.items():
        stats["total"] += 1
        category = anchor.get("category", "")

        # 只处理函数和方法
        if category not in ("functions", "methods", "classes"):
            stats["skipped"] += 1
            continue

        meta = anchor.setdefault("metadata", {})
        existing_calls = meta.get("calls", [])

        # 已有且不强制更新则跳过
        if existing_calls and not force:
            stats["skipped"] += 1
            continue

        try:
            calls = extract_calls_for_anchor(anchor, project_root)
            meta["calls"] = calls
            stats["patched"] += 1
            if verbose:
                print(f"  ✓ {anchor_id}: {len(calls)} 个调用")
        except Exception as e:
            stats["failed"] += 1
            if verbose:
                print(f"  ✗ {anchor_id}: {e}")

    if not dry_run:
        # 原子写入
        tmp = anchors_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(anchors_path)
        print(f"[完成] 已写入 {anchors_path}")
    else:
        print("[dry-run] 未写入磁盘")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="补全锚点的 metadata.calls 字段"
    )
    parser.add_argument("--project", default=".", help="项目根目录")
    parser.add_argument(
        "--anchors",
        default=None,
        help="anchors.json 路径（默认 project/.codedendrite/anchors.json）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只分析不写入")
    parser.add_argument("--force", action="store_true", help="强制覆盖已有 calls 字段")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    anchors_path = (
        Path(args.anchors)
        if args.anchors
        else project_root / ".codedendrite" / "anchors.json"
    )

    print(f"项目根目录: {project_root}")
    print(f"锚点文件:   {anchors_path}")
    print(f"模式:       {'dry-run' if args.dry_run else '写入'}")
    print()

    stats = patch_anchors_calls(
        anchors_path=anchors_path,
        project_root=project_root,
        dry_run=args.dry_run,
        force=args.force,
        verbose=args.verbose,
    )

    print()
    print(f"统计:")
    print(f"  总锚点:   {stats.get('total', 0)}")
    print(f"  已补全:   {stats.get('patched', 0)}")
    print(f"  跳过:     {stats.get('skipped', 0)}")
    print(f"  失败:     {stats.get('failed', 0)}")


if __name__ == "__main__":
    main()
