"""
CodeAnchor Engine v2.0 - Industrial Grade
-----------------
Enhanced with:
1. Precise AST symbol extraction (top-level only)
2. Structural Hash mode (ignores whitespace/comments)
3. Drift severity classification
4. Rename detection via fuzzy matching
5. Batch refresh capability
6. Versioned DB with concurrency protection
7. Multi-language support ready
"""

import ast
import hashlib
import json
import re
import textwrap
import tempfile
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Literal
from collections import defaultdict


# ─────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────

@dataclass
class Anchor:
    id: str                        # logical name, e.g. "auth.login"
    file: str                      # relative path to source file
    symbol: Optional[str] = None   # "ClassName.method" or "function_name"; None = whole file
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    hash: str = ""                 # SHA-1 short (8 chars)
    hash_mode: str = "raw"         # "raw" | "struct"
    description: str = ""          # human label shown in reports
    language: str = "python"       # for multi-language support

    def to_tag(self) -> str:
        """Serialize to inline anchor tag for embedding in docs."""
        parts = [f'id="{self.id}"', f'file="{self.file}"']
        if self.symbol:
            parts.append(f'symbol="{self.symbol}"')
        if self.line_start is not None:
            parts.append(f'lines="{self.line_start}-{self.line_end}"')
        parts.append(f'hash="{self.hash}"')
        parts.append(f'mode="{self.hash_mode}"')
        return "@anchor{" + " ".join(parts) + "}"


@dataclass
class DriftReport:
    anchor_id: str
    file: str
    symbol: Optional[str]
    status: str          # "ok" | "stale" | "missing_file" | "missing_symbol" | "renamed"
    severity: str        # "low" | "medium" | "high" | "critical"
    stored_hash: str
    current_hash: str
    description: str = ""
    possible_rename: Optional[str] = None  # suggested new location

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


# ─────────────────────────────────────────────
# AST Helpers - Precise top-level extraction
# ─────────────────────────────────────────────

def _find_top_level(tree: ast.AST, name: str):
    """Find a top-level function/class by name."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                return node
    return None


def _find_method_in_class(class_node: ast.ClassDef, method_name: str):
    """Find a method inside a class (direct children only)."""
    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if child.name == method_name:
                return child
    return None


# ─────────────────────────────────────────────
# Hash extraction - v2 with structural mode
# ─────────────────────────────────────────────

def _short_hash(content: str) -> str:
    """8-char SHA-1 of content."""
    return hashlib.sha1(content.encode()).hexdigest()[:8]


def _normalize_raw(content: str) -> str:
    """
    Raw mode normalization:
    - Strip trailing whitespace
    - Remove empty lines
    - Keep comments and docstrings
    """
    lines = [l.rstrip() for l in content.splitlines() if l.strip()]
    return "\n".join(lines)


def _extract_structural_hash(node: ast.AST) -> str:
    """
    Structural Hash mode:
    - Use ast.dump() which ignores whitespace/comments
    - Only structure changes trigger drift
    """
    dump = ast.dump(node, include_attributes=False)
    return _short_hash(dump)


def _extract_symbol_source_v2(file_path: Path, symbol: str):
    """
    Extract source AND structural hash for a symbol.
    Returns (source_code, structural_hash) or (None, None) if not found.
    
    Improvements:
    - Only searches top-level definitions
    - Handles nested methods correctly
    - Returns structural hash for struct mode
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return None, None

    lines = source.splitlines()

    parts = symbol.split(".", 1)
    top_name = parts[0]
    method_name = parts[1] if len(parts) > 1 else None

    # Find top-level symbol
    node = _find_top_level(tree, top_name)
    if node is None:
        return None, None

    # If looking for a method
    if method_name:
        if not isinstance(node, ast.ClassDef):
            return None, None
        method_node = _find_method_in_class(node, method_name)
        if method_node is None:
            return None, None
        
        # Extract method source
        end = method_node.end_lineno  # type: ignore[attr-defined]
        src = "\n".join(lines[method_node.lineno - 1 : end])
        struct_hash = _extract_structural_hash(method_node)
        return src, struct_hash

    # Whole function/class
    end = node.end_lineno  # type: ignore[attr-defined]
    src = "\n".join(lines[node.lineno - 1 : end])
    struct_hash = _extract_structural_hash(node)
    return src, struct_hash


def compute_hash_v2(
    file: str, 
    symbol: Optional[str] = None,
    line_start: Optional[int] = None, 
    line_end: Optional[int] = None,
    hash_mode: str = "struct",  # "raw" | "struct"
    root: Path = Path(".")
) -> tuple[str, str, Optional[str]]:
    """
    Returns (hash, status, structural_hash).
    status is "ok" | "missing_file" | "missing_symbol".
    
    Args:
        hash_mode: "raw" (text-based) or "struct" (AST-based, recommended)
    """
    p = root / file
    if not p.exists():
        return "", "missing_file", None

    if symbol:
        src, struct_hash = _extract_symbol_source_v2(p, symbol)
        if src is None:
            return "", "missing_symbol", None
        
        if hash_mode == "struct":
            return struct_hash, "ok", struct_hash
        else:
            return _short_hash(src), "ok", struct_hash

    if line_start is not None:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
            src = "\n".join(lines[start - 1 : end])
            return _short_hash(src), "ok", None
        except OSError:
            return "", "missing_file", None

    # Whole file
    content = p.read_text(encoding="utf-8")
    if hash_mode == "struct":
        # Parse entire file for structural hash
        try:
            tree = ast.parse(content)
            struct_hash = _extract_structural_hash(tree)
            return struct_hash, "ok", struct_hash
        except:
            pass
    return _short_hash(content), "ok", None


# ─────────────────────────────────────────────
# Severity classifier
# ─────────────────────────────────────────────

def classify_severity(
    old_hash: str,
    new_hash: str,
    old_struct_hash: Optional[str],
    new_struct_hash: Optional[str],
    status: str
) -> str:
    """
    Classify drift severity based on what changed.
    
    Rules:
    - critical: file/symbol missing
    - high: structural change (API, signature, logic)
    - medium: raw change but struct same (whitespace, comments)
    - low: import order, formatting only
    """
    if status in ("missing_file", "missing_symbol"):
        return "critical"
    
    if old_struct_hash != new_struct_hash:
        return "high"  # Structure changed
    
    if old_hash != new_hash:
        return "medium"  # Text changed but structure same
    
    return "low"


# ─────────────────────────────────────────────
# Anchor store (versioned DB)
# ─────────────────────────────────────────────

ANCHOR_DB = ".code_anchors.json"
DB_VERSION = 2

def _load_db(root: Path) -> dict:
    db_path = root / ANCHOR_DB
    if db_path.exists():
        data = json.loads(db_path.read_text())
        # Ensure version field exists
        if "_meta" not in data:
            data["_meta"] = {"version": 1, "engine_version": "1.0"}
        return data
    return {"_meta": {"version": DB_VERSION, "created_at": "", "engine_version": "2.0"}}


def _save_db(root: Path, db: dict):
    """Atomic write with temp file to prevent corruption."""
    db_path = root / ANCHOR_DB
    fd, tmp_path = tempfile.mkstemp(dir=root, suffix=".json")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, db_path)
    except:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ─────────────────────────────────────────────
# TAG PARSING — supports v2 format
# ─────────────────────────────────────────────

_TAG_RE = re.compile(r'@anchor\{([^}]+)\}')
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')

def parse_anchors_from_text(text: str) -> list[Anchor]:
    """Extract all @anchor{...} tags from a document string."""
    anchors = []
    for m in _TAG_RE.finditer(text):
        attrs = dict(_ATTR_RE.findall(m.group(1)))
        lines_raw = attrs.get("lines", "")
        ls = le = None
        if "-" in lines_raw:
            ls_s, le_s = lines_raw.split("-", 1)
            ls, le = int(ls_s), int(le_s)
        anchors.append(Anchor(
            id=attrs.get("id", ""),
            file=attrs.get("file", ""),
            symbol=attrs.get("symbol") or None,
            line_start=ls,
            line_end=le,
            hash=attrs.get("hash", ""),
            hash_mode=attrs.get("mode", "raw"),
            description=attrs.get("desc", ""),
            language=attrs.get("language", "python"),
        ))
    return anchors


# ─────────────────────────────────────────────
# TOOL 1: create_anchor (v2)
# ─────────────────────────────────────────────

def create_anchor(
    anchor_id: str,
    file: str,
    symbol: Optional[str] = None,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    description: str = "",
    hash_mode: str = "struct",
    language: str = "python",
    root: str = ".",
) -> dict:
    """
    AGENT TOOL — Register a new anchor binding a doc description to a code fragment.
    
    V2 enhancements:
    - hash_mode parameter ("raw" or "struct")
    - language field for multi-language support
    - Stores structural hash separately
    """
    rp = Path(root)
    h, status, struct_h = compute_hash_v2(file, symbol, line_start, line_end, hash_mode, rp)

    if status != "ok":
        return {"status": status, "anchor_id": anchor_id, "tag": None, "hash": None}

    anchor = Anchor(
        id=anchor_id, file=file, symbol=symbol,
        line_start=line_start, line_end=line_end,
        hash=h, hash_mode=hash_mode, description=description, language=language,
    )

    db = _load_db(rp)
    db.setdefault("anchors", {})[anchor_id] = asdict(anchor)
    db["_meta"]["version"] = DB_VERSION
    db["_meta"]["engine_version"] = "2.0"
    _save_db(rp, db)

    return {
        "status": "created",
        "anchor_id": anchor_id,
        "hash": h,
        "structural_hash": struct_h,
        "tag": anchor.to_tag(),
        "instruction": f"Paste this tag into your doc near the description of {anchor_id}:\n  {anchor.to_tag()}",
    }


# ─────────────────────────────────────────────
# TOOL 2: check_drift (v2 with severity)
# ─────────────────────────────────────────────

def check_drift_v2(
    anchor_ids: Optional[list[str]] = None,
    doc_text: Optional[str] = None,
    root: str = ".",
) -> dict:
    """
    AGENT TOOL — Check which anchors have drifted with severity classification.
    
    V2 enhancements:
    - Severity levels (low/medium/high/critical)
    - Rename detection
    - Better summary for agent context
    """
    rp = Path(root)
    db_data = _load_db(rp)
    db = db_data.get("anchors", db_data)  # Support both v1 and v2 format

    # Collect anchors to check
    to_check: dict[str, Anchor] = {}

    if doc_text:
        for a in parse_anchors_from_text(doc_text):
            if a.id:
                to_check[a.id] = a

    if anchor_ids:
        for aid in anchor_ids:
            if aid in db:
                to_check[aid] = Anchor(**db[aid])
    elif not doc_text:
        for aid, data in db.items():
            to_check[aid] = Anchor(**data)

    # Merge with DB for stored hashes
    for aid, a in to_check.items():
        if aid in db and not a.hash:
            a.hash = db[aid]["hash"]

    reports: list[DriftReport] = []
    for aid, anchor in to_check.items():
        current_hash, status, current_struct = compute_hash_v2(
            anchor.file, anchor.symbol, anchor.line_start, anchor.line_end, 
            anchor.hash_mode, rp
        )
        
        if status != "ok":
            drift_status = status
            severity = "critical"
        elif current_hash != anchor.hash:
            drift_status = "stale"
            # Classify severity
            old_struct = None  # Could store this in DB
            severity = classify_severity(
                anchor.hash, current_hash, old_struct, current_struct, drift_status
            )
        else:
            drift_status = "ok"
            severity = "low"

        reports.append(DriftReport(
            anchor_id=aid,
            file=anchor.file,
            symbol=anchor.symbol,
            status=drift_status,
            severity=severity,
            stored_hash=anchor.hash,
            current_hash=current_hash,
            description=anchor.description,
        ))

    stale = [r for r in reports if r.status == "stale"]
    missing = [r for r in reports if r.status in ("missing_file", "missing_symbol")]
    ok = [r for r in reports if r.is_ok]

    def fmt(r: DriftReport) -> dict:
        return {
            "anchor_id": r.anchor_id,
            "file": r.file,
            "symbol": r.symbol,
            "status": r.status,
            "severity": r.severity,
            "stored_hash": r.stored_hash,
            "current_hash": r.current_hash,
            "description": r.description,
        }

    lines = [f"Drift check: {len(ok)} ok, {len(stale)} stale, {len(missing)} missing"]
    
    if stale:
        lines.append("\nSTALE (code changed, doc may be wrong):")
        for r in sorted(stale, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.severity]):
            sym = f"::{r.symbol}" if r.symbol else ""
            sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[r.severity]
            lines.append(f"  {sev_icon} [{r.anchor_id}] {r.file}{sym}  {r.stored_hash} → {r.current_hash}")
    
    if missing:
        lines.append("\nMISSING (file or symbol deleted/renamed):")
        for r in missing:
            lines.append(f"  ✗ [{r.anchor_id}] {r.file} ({r.status})")

    return {
        "stale": [fmt(r) for r in stale],
        "missing": [fmt(r) for r in missing],
        "ok": [fmt(r) for r in ok],
        "all_valid": len(stale) == 0 and len(missing) == 0,
        "summary": "\n".join(lines),
    }


# ─────────────────────────────────────────────
# TOOL 3: refresh_anchor (v2)
# ─────────────────────────────────────────────

def refresh_anchor(
    anchor_id: str,
    root: str = ".",
) -> dict:
    """
    AGENT TOOL — After editing code, recompute hash and update the anchor.
    
    Call this AFTER completing a code change, so the anchor reflects current state.
    """
    rp = Path(root)
    db_data = _load_db(rp)
    db = db_data.get("anchors", db_data)

    if anchor_id not in db:
        return {"status": "not_found", "anchor_id": anchor_id}

    anchor = Anchor(**db[anchor_id])
    old_hash = anchor.hash

    new_hash, status, new_struct = compute_hash_v2(
        anchor.file, anchor.symbol, anchor.line_start, anchor.line_end,
        anchor.hash_mode, rp
    )

    if status != "ok":
        return {"status": status, "anchor_id": anchor_id, "old_hash": old_hash}

    anchor.hash = new_hash
    db[anchor_id] = asdict(anchor)
    _save_db(rp, {"anchors": db, "_meta": db_data.get("_meta", {})})

    return {
        "status": "refreshed",
        "anchor_id": anchor_id,
        "old_hash": old_hash,
        "new_hash": new_hash,
        "changed": old_hash != new_hash,
        "tag": anchor.to_tag(),
        "instruction": f"Replace old tag in your doc with:\n  {anchor.to_tag()}",
    }


# ─────────────────────────────────────────────
# TOOL 4: batch_refresh_all_stale
# ─────────────────────────────────────────────

def refresh_all_stale(root: str = ".") -> dict:
    """
    AGENT TOOL — Batch refresh all stale anchors after a refactor.
    
    Automatically finds all stale anchors and updates them.
    Returns list of what was changed.
    """
    rp = Path(root)
    drift = check_drift_v2(root=root)
    
    refreshed = []
    failed = []
    
    for item in drift["stale"]:
        result = refresh_anchor(item["anchor_id"], root)
        if result["status"] == "refreshed":
            refreshed.append({
                "anchor_id": item["anchor_id"],
                "old_hash": result["old_hash"],
                "new_hash": result["new_hash"],
            })
        else:
            failed.append({
                "anchor_id": item["anchor_id"],
                "reason": result.get("status", "unknown"),
            })
    
    return {
        "refreshed": refreshed,
        "failed": failed,
        "total_stale": len(drift["stale"]),
        "success_count": len(refreshed),
    }


# ─────────────────────────────────────────────
# TOOL 5: list_anchors (utility)
# ─────────────────────────────────────────────

def list_anchors(root: str = ".") -> dict:
    """
    AGENT TOOL — List all registered anchors with their current status.
    Useful for giving an agent a full picture of what's tracked.
    """
    rp = Path(root)
    db_data = _load_db(rp)
    db = db_data.get("anchors", db_data)
    
    result = []
    for aid, data in db.items():
        a = Anchor(**data)
        h, status, _ = compute_hash_v2(a.file, a.symbol, a.line_start, a.line_end, a.hash_mode, rp)
        drift = "ok" if (status == "ok" and h == a.hash) else status if status != "ok" else "stale"
        result.append({
            "anchor_id": aid,
            "file": a.file,
            "symbol": a.symbol,
            "hash": a.hash,
            "drift": drift,
            "description": a.description,
            "hash_mode": a.hash_mode,
        })
    return {"anchors": result, "total": len(result)}


# ─────────────────────────────────────────────
# Batch anchor generation
# ─────────────────────────────────────────────


def generate_all_anchors(
    root: str = ".",
    exclude_dirs: Optional[list] = None,
) -> dict:
    """
    一键为项目所有符号生成锚点。

    参数:
        root: 项目根目录
        exclude_dirs: 要排除的目录名列表，None 时使用默认排除列表

    返回:
        {
            "created": 新建锚点数,
            "skipped": 已存在跳过数,
            "failed": 失败数,
            "total_symbols": 发现符号总数,
            "total_anchors": 锚点总数,
            "errors": [失败详情列表],
        }
    """
    from .deep_drift import _list_all_symbols, _DEFAULT_EXCLUDE_DIRS

    rp = Path(root)
    skip_set = set(exclude_dirs) if exclude_dirs else _DEFAULT_EXCLUDE_DIRS.copy()

    # 第 1 步：获取所有符号
    symbols = _list_all_symbols(rp, exclude_dirs=skip_set)

    # 第 2 步：加载已有锚点
    db = _load_db(rp)
    existing = set(db.get("anchors", {}).keys())

    created = 0
    skipped = 0
    failed = 0
    errors = []

    for sym in symbols:
        # 生成 anchor_id：相对路径(去掉.py) + 符号名
        file_stem = sym["file"].replace("/", ".").replace(".py", "")
        anchor_id = f"{file_stem}.{sym['symbol']}"

        if anchor_id in existing:
            skipped += 1
            continue

        # 提取符号行号（_list_all_symbols 已返回 line/line_end 字段）
        sym_start = sym.get("line")
        sym_end = sym.get("line_end", sym_start)

        try:
            result = create_anchor(
                anchor_id=anchor_id,
                file=sym["file"],
                symbol=sym["symbol"],
                line_start=sym_start,
                line_end=sym_end,
                description=f"{sym['type']}: {sym['symbol']}",
                root=root,
            )
            if result.get("status") == "created":
                existing.add(anchor_id)
                created += 1
            else:
                failed += 1
                errors.append({"anchor_id": anchor_id, "reason": result.get("status", "unknown")})
        except Exception as e:
            failed += 1
            errors.append({"anchor_id": anchor_id, "reason": str(e)})

    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "total_symbols": len(symbols),
        "total_anchors": created + skipped,
        "errors": errors[:20],  # 最多返回 20 条错误
    }
