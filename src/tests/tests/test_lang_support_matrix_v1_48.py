"""CDD V1.48 language support matrix — three-tier capability contract.

Tier definitions (these are the contract, not aspirational labels):

* **T1 — symbols + call edges**: per fixture, ``parse_paths`` (or
  ``generate_all_anchors`` for ``html``) yields at least two anchors and the
  caller records a ``helper`` callee.
* **T2 — symbols only (generic / component)**: at least one anchor is produced
  but no call-edge guarantee is made. ``scala``, ``objective-c``, ``sql`` live
  here because their generic adapter only does conservative function
  detection.
* **T3 — recognized but not parsed**: ``language_for_path`` returns a spec but
  the analyzer is ``None``; ``parse_paths`` produces zero anchors. Applies to
  ``yaml``, ``json``, ``toml``.

The matrix is bound to ``src/tests/fixtures/lang_matrix/`` and guarded by the
README matrix section (see :func:`test_readme_matrix_matches_fixtures`).
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from analyzer.anchors import generate_all_anchors, load_anchors
from scanner.language.pipeline import parse_paths
from scanner.language.registry import SPECS, LanguageSpec, language_for_path


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "lang_matrix"
REPO_ROOT = Path(__file__).resolve().parents[3]
README_PATH = REPO_ROOT / "README.md"
EDGE_TOKEN = "helper"  # every fixture's caller → helper target

# (letter, spec_name, tier, primary_ext, use_generate_all)
# Alphabetical filenames (a.py .. w.toml) keep the fixtures dir readable and
# match the legacy .cache/lang_audit/ layout. ``primary_ext`` is the most
# recognizable extension for the spec — it overrides the registry's
# extensions[0] for naming only (e.g. cpp → .cpp instead of .c). The on-disk
# fixtures at FIXTURES_ROOT and this table together are the contract.
MATRIX: List[tuple[str, str, str, str, bool]] = [
    ("a", "python",       "T1", ".py",    False),
    ("b", "typescript",   "T1", ".ts",    False),
    ("c", "javascript",   "T1", ".js",    False),
    ("d", "cpp",          "T1", ".cpp",   False),
    ("e", "java",         "T1", ".java",  False),
    ("f", "kotlin",       "T1", ".kt",    False),
    ("g", "go",           "T1", ".go",    False),
    ("h", "rust",         "T1", ".rs",    False),
    ("i", "swift",        "T1", ".swift", False),
    ("j", "php",          "T1", ".php",   False),
    ("k", "ruby",         "T1", ".rb",    False),
    ("l", "html",         "T1", ".html",  True),   # single-file parse_paths can't see <script>
    ("m", "csharp",       "T1", ".cs",    False),
    ("n", "scala",        "T2", ".scala", False),
    ("o", "objective-c",  "T2", ".m",     False),
    ("p", "shell",        "T1", ".sh",    False),
    ("q", "powershell",   "T1", ".ps1",   False),
    ("r", "vue",          "T1", ".vue",   False),
    ("s", "svelte",       "T1", ".svelte",False),
    ("t", "sql",          "T2", ".sql",   False),
    ("u", "yaml",         "T3", ".yaml",  False),
    ("v", "json",         "T3", ".json",  False),
    ("w", "toml",         "T3", ".toml",  False),
]

_SPEC_BY_NAME = {s.name: s for s in SPECS}


def _filename(letter: str, primary_ext: str) -> str:
    return f"{letter}{primary_ext}"


def _spec(spec_name: str) -> LanguageSpec:
    return _SPEC_BY_NAME[spec_name]


# ---------------------------------------------------------------------------
# Coverage guard — every LanguageSpec must appear in the matrix.
# ---------------------------------------------------------------------------

def test_matrix_covers_every_registry_spec():
    declared = {s.name for s in SPECS}
    classified = {name for _, name, _, _, _ in MATRIX}
    assert classified == declared, (
        f"matrix missing: {declared - classified}; extra: {classified - declared}"
    )


# ---------------------------------------------------------------------------
# T1 — symbols + call edges
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("letter", "spec_name", "primary_ext", "use_generate"),
    [(l, n, e, g) for l, n, t, e, g in MATRIX if t == "T1"],
    ids=[n for _, n, t, _, _ in MATRIX if t == "T1"],
)
def test_t1_emits_symbols_and_helper_edge(
    tmp_path: Path, letter: str, spec_name: str, primary_ext: str, use_generate: bool
):
    fname = _filename(letter, primary_ext)
    src = (FIXTURES_ROOT / fname).read_text(encoding="utf-8")
    path = tmp_path / fname
    path.write_text(src, encoding="utf-8")

    if use_generate:
        generate_all_anchors(str(tmp_path))
        anchors = load_anchors(str(tmp_path))
    else:
        parsed, failures, _ = parse_paths(tmp_path, [path], include_python=True)
        assert not failures, failures
        anchors = parsed

    matches = [a for aid, a in anchors.items() if a.file == fname]
    assert len(matches) >= 2, (
        f"{spec_name}: expected >=2 anchors in {fname}, got {len(matches)}: "
        f"{[a.symbol for a in matches]}"
    )
    has_edge = any(EDGE_TOKEN in str(c) for a in matches for c in a.callees)
    assert has_edge, (
        f"{spec_name}: no anchor in {fname} records a callee matching "
        f"{EDGE_TOKEN!r}; anchors: {[(a.symbol, a.callees) for a in matches]}"
    )


# ---------------------------------------------------------------------------
# T2 — symbols only
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("letter", "spec_name", "primary_ext"),
    [(l, n, e) for l, n, t, e, _ in MATRIX if t == "T2"],
    ids=[n for _, n, t, _, _ in MATRIX if t == "T2"],
)
def test_t2_emits_at_least_one_symbol(
    tmp_path: Path, letter: str, spec_name: str, primary_ext: str
):
    fname = _filename(letter, primary_ext)
    src = (FIXTURES_ROOT / fname).read_text(encoding="utf-8")
    path = tmp_path / fname
    path.write_text(src, encoding="utf-8")
    parsed, failures, _ = parse_paths(tmp_path, [path], include_python=True)
    assert not failures, failures
    matches = [a for aid, a in parsed.items() if a.file == fname]
    assert len(matches) >= 1, (
        f"{spec_name}: expected >=1 anchor in {fname}, got 0"
    )


# ---------------------------------------------------------------------------
# T3 — recognized but not parsed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("letter", "spec_name", "primary_ext"),
    [(l, n, e) for l, n, t, e, _ in MATRIX if t == "T3"],
    ids=[n for _, n, t, _, _ in MATRIX if t == "T3"],
)
def test_t3_recognized_but_zero_anchors(
    tmp_path: Path, letter: str, spec_name: str, primary_ext: str
):
    fname = _filename(letter, primary_ext)
    src = (FIXTURES_ROOT / fname).read_text(encoding="utf-8")
    path = tmp_path / fname
    path.write_text(src, encoding="utf-8")
    spec = language_for_path(path)
    assert spec is not None and spec.name == spec_name
    assert spec.analyzer is None and not spec.executable
    parsed, _failures, completed = parse_paths(tmp_path, [path], include_python=True)
    assert fname in completed
    matches = [a for aid, a in parsed.items() if a.file == fname]
    assert matches == [], (
        f"{spec_name} was promoted to T2/T1 unexpectedly; update the matrix if intentional"
    )


# ---------------------------------------------------------------------------
# README drift guard — the README's "Language support matrix" detail table
# must have one row per MATRIX entry. Drift here is the cheapest early warning
# that the README lies about support depth.
# ---------------------------------------------------------------------------

def _read_readme_matrix_rows() -> List[str]:
    text = README_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = None
    level = 0
    for idx, line in enumerate(lines):
        s = line.strip()
        if s.startswith("## ") and "Language support matrix" in s:
            start, level = idx, 2
            break
        if s.startswith("### ") and "Language support matrix" in s:
            start, level = idx, 3
            break
    if start is None:
        return []
    next_prefix = "#" * (level + 1) + " "
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith(next_prefix):
            end = idx
            break
    spec_names = {s.name for s in SPECS}
    rows: List[str] = []
    for line in lines[start:end]:
        s = line.strip()
        if not s.startswith("|"):
            continue
        if set(s.replace("|", "").strip()) <= {"-", " "}:
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        # detail rows have cells[0] in {T1,T2,T3} and cells[1] is a spec name
        if len(cells) >= 2 and cells[0] in {"T1", "T2", "T3"} and cells[1] in spec_names:
            rows.append(s)
    return rows


def test_readme_matrix_matches_fixtures():
    rows = _read_readme_matrix_rows()
    expected = len(MATRIX)
    assert len(rows) == expected, (
        f"README matrix has {len(rows)} data rows, expected {expected} "
        f"(one per LanguageSpec). Drift here means the README is lying about "
        f"support depth — fix README.md or MATRIX."
    )


# ---------------------------------------------------------------------------
# Registry sanity — every LanguageSpec's extensions are unique (no shadowing).
# ---------------------------------------------------------------------------

def test_registry_extensions_have_no_collision():
    seen: dict[str, LanguageSpec] = {}
    for spec in SPECS:
        for ext in spec.extensions:
            if ext in seen:
                raise AssertionError(
                    f"extension {ext!r} mapped to both {seen[ext].name} and {spec.name}"
                )
            seen[ext] = spec


# ---------------------------------------------------------------------------
# Anti-regression — the README must not still claim an unmeasured "24
# languages" slogan.
# ---------------------------------------------------------------------------

def test_readme_does_not_claim_unmeasured_language_count():
    text = README_PATH.read_text(encoding="utf-8")
    for phrase in ("24 languages", "24 种语言", "supports 24"):
        assert phrase not in text, (
            f"README still advertises {phrase!r}; replace with the measured tier "
            f"counts from src/tests/tests/test_lang_support_matrix_v1_48.py"
        )
