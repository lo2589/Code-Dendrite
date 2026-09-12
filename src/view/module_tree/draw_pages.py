"""What one `cdd draw` page is made of, and whether it has moved since.

A page holds one file plus the files one hop away, so those files — and only
those — decide whether it is still true. Their content hashes are written
beside the page when it is generated, and comparing them on the way out is
what lets opening a page answer "this is current" without touching the rest of
the repository: unchanged, serve it; changed, redo this one page.
"""

import hashlib
import json
from pathlib import Path

# The page format. Bump whenever the shell/page split or the page data shape
# changes, so a reader can tell what it is holding. Timestamps cannot: a
# single-page drawing generated before paging existed is newer than the index
# it was built from, and every "is this current?" test said yes for a month.
DRAW_FORMAT = 4
DRAW_STAMP = "<!--cdd-draw-format:{}-->"


def page_id(path: str) -> str:
    """A page's name, derived from the file it holds and nothing else.

    It used to be the file's position in the sorted list, which made every id
    depend on which OTHER files existed: adding one file renumbered every page
    after it, so the shell's links and the pages on disk disagreed and one
    file's contents could be written under another's name. Position is not
    identity. A hash of the path is: it is the same id for the life of the file,
    whatever else appears or disappears around it.
    """
    return hashlib.blake2b(path.encode("utf-8"), digest_size=8).hexdigest()


def file_hash(path) -> str:
    """The content hash of one file; empty when it cannot be read.

    Content, not mtime. An mtime moves when nothing changed (a checkout, a
    touch) and stands still when everything did (a copy restored in place), and
    both mistakes are how a month-old drawing kept being called current.
    """
    digest = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def hashes_of(root, files) -> dict:
    """Content hashes for a page's inputs, keyed by repo-relative path."""
    base = Path(root)
    return {name: file_hash(base / name) for name in sorted(files)}


def manifest_path(pages_dir, page_id):
    return Path(pages_dir) / "{}.json".format(page_id)


def write_manifest(pages_dir, page_id, page_file, root, files) -> None:
    """Record what this page was built from, beside the page itself."""
    manifest_path(pages_dir, page_id).write_text(json.dumps({
        "format": DRAW_FORMAT,
        "page": page_file,
        "files": hashes_of(root, files),
    }, ensure_ascii=False), encoding="utf-8")


def read_manifest(pages_dir, page_id):
    """The page's manifest, or None when it is absent or of another format."""
    try:
        data = json.loads(manifest_path(pages_dir, page_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format") != DRAW_FORMAT:
        return None
    return data


def changed_inputs(root, manifest) -> list:
    """Which of a page's inputs no longer hash to what the page was built from.

    An empty list is the answer that matters: nothing this page can draw has
    changed, so the page on disk is not stale — it is finished.
    """
    if not manifest:
        return []
    stored = manifest.get("files") or {}
    base = Path(root)
    return [name for name, digest in sorted(stored.items())
            if file_hash(base / name) != digest]


def files_path(pages_dir):
    # Not a valid page id — those are hex — so it can never collide with one.
    return Path(pages_dir) / "_files.json"


def write_files(pages_dir, files) -> None:
    """Which files the drawing covers, so a later open can tell what moved."""
    files_path(pages_dir).write_text(json.dumps({
        "format": DRAW_FORMAT,
        "files": sorted(files),
    }, ensure_ascii=False), encoding="utf-8")


def read_files(pages_dir):
    """The covered file list, or None when absent or of another format."""
    try:
        data = json.loads(files_path(pages_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format") != DRAW_FORMAT:
        return None
    return list(data.get("files") or [])


def may_have_new_files(pages_dir, anchors_json) -> bool:
    """Whether the file set is even worth checking.

    Checking it means reading the index, which is the expensive thing this whole
    scheme exists to avoid on an ordinary open. The index cannot have gained or
    lost a file without being rewritten, so its mtime is a safe gate: it can
    only ask for an unnecessary look, never miss a real change.
    """
    try:
        return Path(anchors_json).stat().st_mtime_ns > files_path(pages_dir).stat().st_mtime_ns
    except OSError:
        return True
