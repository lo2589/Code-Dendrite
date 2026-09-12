"""
Tests for CodeAnchor engine.
Run: python test_anchor.py
"""
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from analyzer.identity.engine_v1 import (
    create_anchor, check_drift, refresh_anchor, list_anchors, parse_anchors_from_text
)

SAMPLE_PY = '''
class AuthService:
    def validate(self, token: str) -> bool:
        """Check token validity."""
        return token.startswith("Bearer ")

    def logout(self, user_id: str):
        pass

def helper():
    return 42
'''

def run(label, fn):
    try:
        result = fn()
        print(f"  ✓ {label}")
        return result
    except Exception as e:
        print(f"  ✗ {label}: {e}")
        raise


def test_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = tmpdir

        # write sample file
        src = Path(root) / "auth.py"
        src.write_text(SAMPLE_PY)

        print("\n── 1. create_anchor (file level) ──")
        r = run("whole file anchor", lambda: create_anchor(
            "auth.file", "auth.py", description="Entire auth module", root=root
        ))
        assert r["status"] == "created", r
        assert len(r["hash"]) == 8
        assert "@anchor{" in r["tag"]

        print("\n── 2. create_anchor (symbol level) ──")
        r = run("class method anchor", lambda: create_anchor(
            "auth.validate", "auth.py", symbol="AuthService.validate",
            description="Token validation logic", root=root
        ))
        assert r["status"] == "created"

        r = run("top-level function anchor", lambda: create_anchor(
            "auth.helper", "auth.py", symbol="helper", root=root
        ))
        assert r["status"] == "created"

        r = run("missing symbol returns error", lambda: create_anchor(
            "auth.ghost", "auth.py", symbol="GhostClass.nowhere", root=root
        ))
        assert r["status"] == "missing_symbol"

        print("\n── 3. check_drift (all ok) ──")
        r = run("no drift on fresh anchors", lambda: check_drift(root=root))
        assert r["all_valid"], r["summary"]
        assert len(r["ok"]) == 3

        print("\n── 4. simulate code change → stale ──")
        modified = SAMPLE_PY.replace(
            'return token.startswith("Bearer ")',
            'return token.startswith("Bearer ") and len(token) > 10'
        )
        src.write_text(modified)

        r = run("detects stale after change", lambda: check_drift(root=root))
        stale_ids = [s["anchor_id"] for s in r["stale"]]
        assert "auth.validate" in stale_ids, f"Expected stale, got: {r['summary']}"
        assert "auth.file" in stale_ids
        # helper function unchanged
        assert "auth.helper" not in stale_ids

        print("\n── 5. refresh_anchor ──")
        r = run("refresh stale anchor", lambda: refresh_anchor("auth.validate", root=root))
        assert r["status"] == "refreshed"
        assert r["changed"] is True
        assert "@anchor{" in r["tag"]

        r = run("after refresh, no longer stale", lambda: check_drift(
            anchor_ids=["auth.validate"], root=root
        ))
        assert r["all_valid"]

        print("\n── 6. missing file ──")
        r = run("anchor to non-existent file", lambda: create_anchor(
            "ghost.file", "nonexistent.py", root=root
        ))
        assert r["status"] == "missing_file"

        print("\n── 7. parse @anchor tags from doc text ──")
        doc = """
# Auth Module
<!-- @anchor{id="auth.validate" file="auth.py" symbol="AuthService.validate" hash="deadbeef"} -->
This validates tokens...

<!-- @anchor{id="auth.helper" file="auth.py" symbol="helper" hash="aabbccdd"} -->
Helper function.
"""
        anchors = run("parse from doc text", lambda: parse_anchors_from_text(doc))
        assert len(anchors) == 2
        assert anchors[0].id == "auth.validate"
        assert anchors[0].symbol == "AuthService.validate"

        r = run("check_drift via doc_text", lambda: check_drift(doc_text=doc, root=root))
        # auth.validate was refreshed so its DB hash is current; tag in doc has wrong hash → stale
        stale_ids = [s["anchor_id"] for s in r["stale"]]
        assert "auth.validate" in stale_ids or "auth.helper" in stale_ids

        print("\n── 8. list_anchors ──")
        r = run("list all anchors", lambda: list_anchors(root=root))
        assert r["total"] == 3
        ids = [a["anchor_id"] for a in r["anchors"]]
        assert "auth.validate" in ids

        print("\n── 9. line-range anchor ──")
        r = run("line range anchor", lambda: create_anchor(
            "auth.lines", "auth.py", line_start=2, line_end=6,
            description="AuthService class header", root=root
        ))
        assert r["status"] == "created"

        r = run("line range drift check ok", lambda: check_drift(
            anchor_ids=["auth.lines"], root=root
        ))
        assert r["all_valid"]

        print("\n✅ All tests passed!\n")


if __name__ == "__main__":
    test_all()
