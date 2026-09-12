import json
from pathlib import Path

from view.browser.context import _context, _js, _one_hop, _subtree
from view.browser.dom_sidebar import _HTML
from view.module_tree.draw_pages import (DRAW_FORMAT, DRAW_STAMP, changed_inputs,
                                       manifest_path, may_have_new_files,
                                       read_files, read_manifest, write_files,
                                       write_manifest)


def _write_shell(ctx: dict) -> int:
    """The whole file tree, none of the contents."""
    shell_js = (
        "const ANCHORS = {};\n"
        "const FILE_ANCHORS = " + _js({p: [] for p in ctx["order"]}) + ";\n"
        "const FILE_COUNT = "   + _js(ctx["counts"]) + ";\n"
        "const FILE_TREE = "    + _js(ctx["tree"]) + ";\n"
        "const PAGE_OF = "      + _js(ctx["page_of"]) + ";\n"
        "const PAGE_SELF = null;\n"
    )
    shell = DRAW_STAMP.format(DRAW_FORMAT) + (
        _HTML
        .replace("__DATA_JS__", shell_js)
        .replace("__FILE_CODE_JS__", "const FILE_CODE = {};\n")
        .replace("__PROJECT__", ctx["root"].name))
    ctx["out"].write_text(shell, encoding="utf-8")
    return len(shell)


def _write_page(ctx: dict, path: str) -> int:
    """One page: this file, its source, and the files one hop away.

    The manifest written beside it names the same set by content hash, which is
    what lets opening this page later decide in one pass whether anything it
    can draw has moved — without loading the repository to find out.
    """
    near = _one_hop(ctx["anchors"], ctx["file_anchors"], path, ctx["owner"])
    ids = set()
    for name in near:
        ids.update(ctx["file_anchors"].get(name, []))
    page_anchors = {nid: ctx["slim"][nid] for nid in ids if nid in ctx["slim"]}
    page_files = {f: ctx["file_anchors"][f] for f in near if f in ctx["file_anchors"]}
    # No source in the page. It was three quarters of the weight — a 282MB
    # single page, then 1.3GB of them — and it was a snapshot: stale the moment
    # the file was edited, and present for one file only, so every neighbour's
    # anchor answered "source not available". The page carries the graph; the
    # source comes off disk when something asks for it.
    code = {}
    page_js = (
        "const ANCHORS = "      + _js(page_anchors) + ";\n"
        "const FILE_ANCHORS = " + _js(page_files) + ";\n"
        "const FILE_COUNT = "   + _js({f: ctx["counts"].get(f, 0) for f in near}) + ";\n"
        "const FILE_TREE = "    + _js(_subtree(near)) + ";\n"
        "const PAGE_OF = "      + _js({f: ctx["page_of"][f] for f in near if f in ctx["page_of"]}) + ";\n"
        "const PAGE_SELF = "    + _js(path) + ";\n"
    )
    html = DRAW_STAMP.format(DRAW_FORMAT) + (
        _HTML
        .replace("__DATA_JS__", page_js)
        .replace("__FILE_CODE_JS__", "const FILE_CODE = " + _js(code) + ";\n")
        .replace("__PROJECT__", ctx["root"].name))
    ident = ctx["page_of"][path]
    (ctx["pages_dir"] / (ident + ".html")).write_text(html, encoding="utf-8")
    write_manifest(ctx["pages_dir"], ident, path, ctx["root"], near)
    return len(html)


def refresh_page(root: str, output: str, page: str, update_index: bool = True) -> dict:
    """Bring exactly one page up to date, and nothing else.

    Opening a page is the only moment anyone needs it to be true, and a page
    depends on a known handful of files. So the work is that handful: hash them,
    and if none moved say so and stop. Rebuilding the repository to answer a
    question about one file is what made the drawing something nobody dared
    click.

    Whether files appeared or vanished is the shell's business, not this page's,
    and it is settled here too: the index cannot have gained or lost a file
    without being rewritten, so its mtime says whether the question is even
    worth asking. When the answer is yes the tree is rewritten — it carries no
    source, only the tree, so it is cheap — and the links it hands out are
    right again immediately.
    """
    pages_dir = Path(output).parent / (Path(output).stem + "_pages")
    anchors_json = Path(root) / ".codedendrite" / "anchors.json"
    manifest = read_manifest(pages_dir, page)
    changed = changed_inputs(root, manifest) if manifest is not None else []
    # Both of these are file stats and a few hashes. Neither reads the index,
    # which is the whole point: the common answer is "nothing moved".
    if manifest is not None and not changed and not may_have_new_files(pages_dir, anchors_json):
        return {"page": page, "state": "current", "changed": []}

    if changed and update_index:
        try:
            from usage.cli import update as _update
        except ImportError:
            # Run as a script, sys.path holds the package directory and not the
            # tree root above it, so neither spelling of the import resolves yet.
            import sys as _sys
            _root = str(Path(__file__).resolve().parent.parent.parent.parent)
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            from usage.cli import update as _update
        # Only the files that moved, and only the topology those touch: the
        # module tree and the summaries are a whole-repository question and
        # belong to the idle pass, not to one click.
        _update(root, changed_files=changed, topology_only=True)

    ctx = _context(root, output)
    covered = read_files(ctx["pages_dir"])
    moved = covered is None or covered != ctx["order"]
    path = {pid: name for name, pid in ctx["page_of"].items()}.get(str(page))

    if path is None:
        if manifest is None:
            return {"page": page, "state": "unknown"}
        # The file this page held has left the index. Drop the page rather than
        # leave a drawing of something that is not there.
        for leftover in (ctx["pages_dir"] / (str(page) + ".html"),
                         manifest_path(ctx["pages_dir"], page)):
            try:
                leftover.unlink()
            except OSError:
                pass
        _write_shell(ctx)
        write_files(ctx["pages_dir"], ctx["order"])
        return {"page": page, "state": "removed", "changed": changed}

    size = _write_page(ctx, path)
    if moved:
        _write_shell(ctx)
    # Always, not only when the tree moved: this is what closes the mtime gate
    # above. Left alone, every open after any index write would read the index
    # again to re-learn that nothing had changed.
    write_files(ctx["pages_dir"], ctx["order"])
    return {"page": page, "file": path, "changed": changed, "bytes": size,
            "shell": moved,
            "state": "rebuilt" if manifest is not None else "created"}
