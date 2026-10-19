"""Canonical CodeDendrite anchor identity helpers.

Real code symbols use the same public ID everywhere:

    relative/path.py::Class.method

Non-symbol assets keep the same file namespace and add an explicit kind:

    relative/path.py::import:json
"""

from pathlib import Path
from typing import Optional, Union


PathLike = Union[str, Path]


def canonical_file_id(file_path: PathLike, project_root: Optional[PathLike] = None) -> str:
    """Return a stable POSIX file path, relative to the scanned project when possible."""
    path = Path(file_path).expanduser()
    if project_root is not None:
        root = Path(project_root).expanduser().resolve()
        try:
            path = path.resolve().relative_to(root)
        except ValueError:
            path = Path(path.name)
    elif path.is_absolute():
        path = Path(path.name)
    normalized = path.as_posix()
    return normalized[2:] if normalized.startswith("./") else normalized


def symbol_anchor_id(file_id: str, symbol: str) -> str:
    """Build the canonical ID for a real function, class, or method."""
    return "{}::{}".format(file_id.replace("\\", "/"), symbol)


def asset_anchor_id(file_id: str, kind: str, name: str) -> str:
    """Build a collision-resistant ID for a non-symbol code asset."""
    return "{}::{}:{}".format(file_id.replace("\\", "/"), kind, name)
