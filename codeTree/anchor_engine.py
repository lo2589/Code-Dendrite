"""
CodeAnchor Engine
-----------------
Binds documentation descriptions to specific code fragments via hash.
When code changes, anchors become stale — agents detect drift before acting.

Anchor format (embedded in any text/markdown/json doc):
    @anchor{id="auth.login" file="src/auth/login.py" symbol="LoginHandler.authenticate" hash="a3f2c1d8"}

Granularity options:
    - file-level:    hash entire file
    - symbol-level:  hash a specific function/class (via AST)
    - line-range:    hash lines N-M
"""

import ast
import hashlib
import json
import re
import textwrap
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


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
    description: str = ""          # human label shown in reports

    def to_tag(self) -> str:
        """Serialize to inline anchor tag for embedding in docs."""
        parts = [f'id="{self.id}"', f'file="{self.file}"']
        if self.symbol:
            parts.append(f'symbol="{self.symbol}"')
        if self.line_start is not None:
            parts.append(f'lines="{self.line_start}-{self.line_end}"')
        parts.append(f'hash="{self.hash}"')
        return "@anchor{" + " ".join(parts) + "}"


@dataclass
class DriftReport:
    anchor_id: str
    file: str
    symbol: Optional[str]
    status: str          # "ok" | "stale" | "missing_file" | "missing_symbol"
    stored_hash: str
    current_hash: str
    description: str = ""

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


# ─────────────────────────────────────────────
# Hash extraction
# ─────────────────────────────────────────────

def _short_hash(content: str) -> str:
    """8-char SHA-1 of normalized content (strips comments/blank lines for stability)."""
    lines = [l.rstrip() for l in content.splitlines() if l.strip()]
    normalized = "\n".join(lines)
    return hashlib.sha1(normalized.encode()).hexdigest()[:8]


def _extract_symbol_source(file_path: Path, symbol: str) -> Optional[str]:
    """
    Extract source of a top-level function or class (or Class.method) via AST.
    Returns None if symbol not found.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return None

    lines = source.splitlines()

    parts = symbol.split(".", 1)
    top_name = parts[0]
    method_name = parts[1] if len(parts) > 1 else None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == top_name:
                if method_name is None:
                    # whole function/class
                    end = node.end_lineno  # type: ignore[attr-defined]
                    return "\n".join(lines[node.lineno - 1 : end])
                elif isinstance(node, ast.ClassDef):
                    # look for method inside class
                    for child in ast.walk(node):
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if child.name == method_name:
                                end = child.end_lineno  # type: ignore[attr-defined]
                                return "\n".join(lines[child.lineno - 1 : end])
    return None


def _extract_lines_source(file_path: Path, start: int, end: int) -> Optional[str]:
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[start - 1 : end])
    except OSError:
        return None


def compute_hash(file: str, symbol: Optional[str] = None,
                 line_start: Optional[int] = None, line_end: Optional[int] = None,
                 root: Path = Path(".")) -> tuple[str, str]:
    """
    Returns (hash, status) where status is "ok" | "missing_file" | "missing_symbol".
    """
    p = root / file
    if not p.exists():
        return "", "missing_file"

    if symbol:
        src = _extract_symbol_source(p, symbol)
        if src is None:
            return "", "missing_symbol"
        return _short_hash(src), "ok"

    if line_start is not None:
        src = _extract_lines_source(p, line_start, line_end or line_start)
        if src is None:
            return "", "missing_file"
        return _short_hash(src), "ok"

    # whole file
    return _short_hash(p.read_text(encoding="utf-8")), "ok"


# ─────────────────────────────────────────────
# Anchor store (JSON sidecar file)
# ─────────────────────────────────────────────

ANCHOR_DB = ".code_anchors.json"

def _load_db(root: Path) -> dict[str, dict]:
    db_path = root / ANCHOR_DB
    if db_path.exists():
        return json.loads(db_path.read_text())
    return {}


def _save_db(root: Path, db: dict[str, dict]):
    db_path = root / ANCHOR_DB
    db_path.write_text(json.dumps(db, indent=2, ensure_ascii=False))


# ─────────────────────────────────────────────
# TAG PARSING — read anchors embedded in docs
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
            description=attrs.get("desc", ""),
        ))
    return anchors


# ─────────────────────────────────────────────
# TOOL 1: create_anchor
# ─────────────────────────────────────────────

def create_anchor(
    anchor_id: str,
    file: str,
    symbol: Optional[str] = None,
    line_start: Optional[int] = None,
    line_end: Optional[int] = None,
    description: str = "",
    root: str = ".",
) -> dict:
    """
    AGENT TOOL — Register a new anchor binding a doc description to a code fragment.

    Args:
        anchor_id:   Logical dot-path name, e.g. "auth.login.validate"
        file:        Path to source file relative to root
        symbol:      Optional "ClassName.method" or bare "function_name"
        line_start:  Optional start line (1-indexed) for line-range mode
        line_end:    Optional end line
        description: Human-readable label for reports
        root:        Project root directory

    Returns dict with:
        tag (str):     The @anchor{...} tag to paste into your doc
        hash (str):    Current hash
        status (str):  "created" | "missing_file" | "missing_symbol"
    """
    rp = Path(root)
    h, status = compute_hash(file, symbol, line_start, line_end, rp)

    if status != "ok":
        return {"status": status, "anchor_id": anchor_id, "tag": None, "hash": None}

    anchor = Anchor(
        id=anchor_id, file=file, symbol=symbol,
        line_start=line_start, line_end=line_end,
        hash=h, description=description,
    )

    db = _load_db(rp)
    db[anchor_id] = asdict(anchor)
    _save_db(rp, db)

    return {
        "status": "created",
        "anchor_id": anchor_id,
        "hash": h,
        "tag": anchor.to_tag(),
        "instruction": f"Paste this tag into your doc near the description of {anchor_id}:\n  {anchor.to_tag()}",
    }


# ─────────────────────────────────────────────
# TOOL 2: check_drift
# ─────────────────────────────────────────────

def check_drift(
    anchor_ids: Optional[list[str]] = None,
    doc_text: Optional[str] = None,
    root: str = ".",
) -> dict:
    """
    AGENT TOOL — Check which anchors have drifted (code changed since last binding).

    Call this at the START of every agent session before touching code.

    Args:
        anchor_ids:  List of specific IDs to check; None = check all in DB
        doc_text:    Optional raw doc string — anchors embedded as @anchor{...} tags
                     will also be extracted and checked
        root:        Project root directory

    Returns dict with:
        stale (list):   Anchors where code has changed
        missing (list): Anchors where file/symbol no longer exists
        ok (list):      Anchors that are still valid
        summary (str):  Human-readable summary for agent context
    """
    rp = Path(root)
    db = _load_db(rp)

    # collect anchors to check
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

    # also merge with DB for stored hashes
    for aid, a in to_check.items():
        if aid in db and not a.hash:
            a.hash = db[aid]["hash"]

    reports: list[DriftReport] = []
    for aid, anchor in to_check.items():
        current_hash, status = compute_hash(
            anchor.file, anchor.symbol, anchor.line_start, anchor.line_end, rp
        )
        if status != "ok":
            drift_status = status
        elif current_hash != anchor.hash:
            drift_status = "stale"
        else:
            drift_status = "ok"

        reports.append(DriftReport(
            anchor_id=aid,
            file=anchor.file,
            symbol=anchor.symbol,
            status=drift_status,
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
            "stored_hash": r.stored_hash,
            "current_hash": r.current_hash,
            "description": r.description,
        }

    lines = [f"Drift check: {len(ok)} ok, {len(stale)} stale, {len(missing)} missing"]
    if stale:
        lines.append("\nSTALE (code changed, doc may be wrong):")
        for r in stale:
            sym = f"::{r.symbol}" if r.symbol else ""
            lines.append(f"  ⚠ [{r.anchor_id}] {r.file}{sym}  {r.stored_hash} → {r.current_hash}")
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
# TOOL 3: refresh_anchor
# ─────────────────────────────────────────────

def refresh_anchor(
    anchor_id: str,
    root: str = ".",
) -> dict:
    """
    AGENT TOOL — After editing code, recompute hash and update the anchor.

    Call this AFTER completing a code change, so the anchor reflects current state.

    Args:
        anchor_id:  The anchor to refresh
        root:       Project root directory

    Returns dict with:
        old_hash (str):  Previous hash
        new_hash (str):  Updated hash
        tag (str):       Updated @anchor{...} tag to replace in doc
        status (str):    "refreshed" | "missing_file" | "missing_symbol" | "not_found"
    """
    rp = Path(root)
    db = _load_db(rp)

    if anchor_id not in db:
        return {"status": "not_found", "anchor_id": anchor_id}

    anchor = Anchor(**db[anchor_id])
    old_hash = anchor.hash

    new_hash, status = compute_hash(
        anchor.file, anchor.symbol, anchor.line_start, anchor.line_end, rp
    )

    if status != "ok":
        return {"status": status, "anchor_id": anchor_id, "old_hash": old_hash}

    anchor.hash = new_hash
    db[anchor_id] = asdict(anchor)
    _save_db(rp, db)

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
# TOOL 4: list_anchors  (utility)
# ─────────────────────────────────────────────

def list_anchors(root: str = ".") -> dict:
    """
    AGENT TOOL — List all registered anchors with their current status.
    Useful for giving an agent a full picture of what's tracked.
    """
    rp = Path(root)
    db = _load_db(rp)
    result = []
    for aid, data in db.items():
        a = Anchor(**data)
        h, status = compute_hash(a.file, a.symbol, a.line_start, a.line_end, rp)
        drift = "ok" if (status == "ok" and h == a.hash) else status if status != "ok" else "stale"
        result.append({
            "anchor_id": aid,
            "file": a.file,
            "symbol": a.symbol,
            "hash": a.hash,
            "drift": drift,
            "description": a.description,
        })
    return {"anchors": result, "total": len(result)}
