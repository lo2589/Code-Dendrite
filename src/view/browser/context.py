import json
from pathlib import Path

from view.browser.build_file_index import _build_file_index, _build_tree, _load_anchors, _slim
from view.module_tree.draw_pages import page_id


def _owner_index(file_anchors: dict) -> dict:
    """Which file each anchor lives in. Built once, not once per page."""
    owner = {}
    for path, ids in file_anchors.items():
        for nid in ids:
            owner[nid] = path
    return owner


def _one_hop(anchors: dict, file_anchors: dict, focus: str, owner: dict) -> set:
    """The files this one talks to, and nothing further.

    A page carries its own file plus whatever its anchors call or are called
    by. That is the whole of what the graph on that page can draw, so it is
    the whole of what the page needs to hold — and it is what stops the size
    of a page depending on the size of the repository.
    """
    near = {focus}
    for nid in file_anchors.get(focus, []):
        rec = anchors.get(nid) or {}
        for key in ("callers", "callees"):
            for item in rec.get(key, []) or []:
                target = item if isinstance(item, str) else (
                    item.get("target") or item.get("id") or item.get("symbol") if isinstance(item, dict) else None)
                if target and target in owner:
                    near.add(owner[target])
    return near


def _subtree(paths) -> dict:
    return _build_tree(sorted(paths))


def _js(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _context(root: str, output: str) -> dict:
    """Everything the shell and any one page are both built from.

    Built once so a full run and a single-page refresh cannot disagree about
    what page a file is: the page id is this file's position in `order`, and
    two code paths deriving that separately is two mappings waiting to drift.
    """
    anchors = _load_anchors(root)
    file_anchors = _build_file_index(anchors)
    order = sorted(file_anchors.keys())
    out = Path(output)
    pages_dir = out.parent / (out.stem + "_pages")
    pages_dir.mkdir(parents=True, exist_ok=True)
    return {
        "root": Path(root),
        "out": out,
        "pages_dir": pages_dir,
        "anchors": anchors,
        "file_anchors": file_anchors,
        "slim": {nid: _slim(a) for nid, a in anchors.items()},
        "order": order,
        # Derived from the path, so a file appearing or disappearing changes
        # nobody else's page. See draw_pages.page_id.
        "page_of": {path: page_id(path) for path in order},
        "counts": {path: len(ids) for path, ids in file_anchors.items()},
        "owner": _owner_index(file_anchors),
        "tree": _build_tree(order),
    }
