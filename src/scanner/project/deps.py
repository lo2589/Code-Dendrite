"""External package dependencies, read off the import anchors.

`ModuleView` already reports a `dependencies` count, but those are module-to-module
edges *inside* the project — they answer "what does this area couple to". This
answers the other question: **which distributions must be installed before the
project imports at all**.

The genome database already stores every import as its own anchor, so nothing new
has to be parsed:

    {"id": "py.cache.imports.argon2", "category": "imports",
     "name": "low_level", "metadata": {"from_module": "argon2"}}

An import is external when its top-level module is neither a standard-library
module nor a module that lives in the project. Relative imports never leave the
project and are dropped before that test.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

# Import name -> distribution name, for the cases where `pip install <name>`
# is not the name you import. Anything absent is reported as imported.
DISTRIBUTIONS = {
    "argon2": "argon2-cffi",
    "attr": "attrs",
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "fitz": "PyMuPDF",
    "git": "GitPython",
    "jwt": "PyJWT",
    "OpenSSL": "pyOpenSSL",
    "PIL": "Pillow",
    "serial": "pyserial",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "yaml": "PyYAML",
    "zoneinfo": "backports.zoneinfo",
}


def _imported_module(anchor: dict) -> str | None:
    """The top-level module one import anchor pulls in, or None if it is local.

    The statement text is read first and the extractor's metadata only as a
    fallback. `name` holds the *bound* name, which for `import numpy as np` is
    the alias, and for `from x import y` is `y` — neither is the module. The
    stored `code` is the source line, so it settles both cases.

    `from . import x` and `from .pkg import y` resolve inside the project, so
    they are never dependencies no matter what they name.
    """
    module = ""
    code = str(anchor.get("code") or "").strip()
    if code.startswith("from "):
        module = code[5:].split(" import", 1)[0].strip()
    elif code.startswith("import "):
        # `import a.b as c, d` — the first name is the one this anchor is for.
        module = code[7:].split(",")[0].split(" as ")[0].strip()

    if not module:
        metadata = anchor.get("metadata") or {}
        module = str(metadata.get("from_module") or "").strip()

    if not module or module.startswith("."):
        return None
    return module.split(".")[0]


def _project_modules(root: Path, files) -> set[str]:
    """Top-level names that resolve to project files rather than to a package."""
    names: set[str] = set()
    for raw in files:
        if not raw:
            continue
        try:
            relative = Path(raw).resolve().relative_to(root)
        except ValueError:
            # Indexed from somewhere outside the root; it cannot shadow an
            # import inside it either.
            continue
        parts = relative.parts
        if not parts:
            continue
        # Every directory on the way down, not just the first: a package deep
        # in the tree is still imported by its own name once anything adds its
        # parent to sys.path, which vendored trees and test roots routinely do.
        # Over-matching here only ever drops a name from the dependency list,
        # which is the safe direction — a missing local name would be reported
        # as a package that does not exist.
        for part in parts[:-1]:
            names.add(part)
        names.add(relative.stem)
    return names


def external_dependencies(database: dict, root: str | Path) -> dict:
    """Group every external import by top-level module.

    Returns {"root", "modules": [{"module", "distribution", "count", "files"}],
             "unresolved_relative", "scanned"}.
    """
    root_path = Path(root).expanduser().resolve()
    anchors = database.get("anchors") or {}

    files = {anchor.get("file") for anchor in anchors.values()}
    local = _project_modules(root_path, files)
    stdlib = set(sys.stdlib_module_names)

    hits: dict[str, set[str]] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)
    relative = 0
    scanned = 0

    for anchor in anchors.values():
        if anchor.get("category") != "imports":
            continue
        scanned += 1
        module = _imported_module(anchor)
        if module is None:
            relative += 1
            continue
        if module in local or module in stdlib:
            continue
        counts[module] += 1
        source = anchor.get("file")
        if source:
            try:
                source = str(Path(source).resolve().relative_to(root_path))
            except ValueError:
                pass
            hits[module].add(source)

    modules = [
        {
            "module": module,
            "distribution": DISTRIBUTIONS.get(module, module),
            "count": counts[module],
            "files": sorted(hits[module]),
        }
        for module in sorted(counts, key=lambda name: (-counts[name], name))
    ]
    return {
        "root": str(root_path),
        "modules": modules,
        "unresolved_relative": relative,
        "scanned": scanned,
    }


def format_report(report: dict, show_files: bool = False) -> str:
    """One line per distribution, widest first."""
    lines = [
        "{} external packages from {} import anchors".format(
            len(report["modules"]), report["scanned"]
        )
    ]
    for row in report["modules"]:
        name = row["distribution"]
        alias = "" if name == row["module"] else "  (import {})".format(row["module"])
        lines.append("  {:<24} {:>4} imports{}".format(name, row["count"], alias))
        if show_files:
            for path in row["files"]:
                lines.append("      {}".format(path))
    if not report["modules"]:
        lines.append("  (none — the project imports only stdlib and itself)")
    return "\n".join(lines)
