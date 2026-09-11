"""One page of `cdd draw` is kept true by its own content hashes.

A page holds one file plus the files one hop away, so those files decide whether
it is still correct. Opening it hashes exactly them: unchanged, serve what is on
disk; changed, re-index those files and rewrite that one page. What this pins is
that the cheap answer stays cheap and the expensive one stays correct — and that
a page whose id has moved refuses to be fixed one page at a time.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from index.api.anchors import generate_all_anchors            # noqa: E402
from view.visualize import draw_pages                        # noqa: E402
from view.visualize.anchor_browser import generate, refresh_page  # noqa: E402

TS = """export function render({ title, items }: Props): void {
  console.log(title)
  items.forEach((i) => { console.log(i) })
}
"""
PY_SRC = "def helper(x):\n    return x + 1\n\n\ndef main():\n    return helper(1)\n"


def _project(tmp_path: Path) -> tuple:
    (tmp_path / "app.py").write_text(PY_SRC, encoding="utf-8")
    (tmp_path / "ui.ts").write_text(TS, encoding="utf-8")
    generate_all_anchors(str(tmp_path))
    output = tmp_path / ".codedendrite" / "anchor_browser.html"
    generate(str(tmp_path), str(output))
    return output, output.parent / "anchor_browser_pages"


def _page_of(pages_dir: Path, name: str) -> str:
    """A file's page, computed rather than looked up.

    The id is a function of the path alone, so the test can name a page without
    scanning anything — and if that ever stops being true, every assertion in
    this file that depends on a stable id fails at once.
    """
    ident = draw_pages.page_id(name)
    assert (pages_dir / (ident + ".html")).exists(), "no page for {}".format(name)
    return ident


def test_every_page_records_its_own_inputs(tmp_path):
    output, pages_dir = _project(tmp_path)
    assert output.read_text(encoding="utf-8").startswith(
        draw_pages.DRAW_STAMP.format(draw_pages.DRAW_FORMAT)
    ), "the shell declares its format; a timestamp cannot"

    for manifest in pages_dir.glob("*.json"):
        if manifest.name == "_files.json":   # the covered-file list, not a page
            continue
        record = json.loads(manifest.read_text(encoding="utf-8"))
        assert record["format"] == draw_pages.DRAW_FORMAT
        assert record["page"] in record["files"], "a page's own file is one of its inputs"
        assert all(digest for digest in record["files"].values())


def test_untouched_page_is_current_and_does_no_work(tmp_path):
    output, pages_dir = _project(tmp_path)
    page = _page_of(pages_dir, "ui.ts")
    before = (pages_dir / (page + ".html")).stat().st_mtime_ns

    verdict = refresh_page(str(tmp_path), str(output), page)

    assert verdict["state"] == "current"
    assert verdict["changed"] == []
    assert (pages_dir / (page + ".html")).stat().st_mtime_ns == before, \
        "nothing moved, so nothing is rewritten"


def test_changed_file_rebuilds_only_its_own_page(tmp_path):
    output, pages_dir = _project(tmp_path)
    changed_page = _page_of(pages_dir, "ui.ts")
    other_page = _page_of(pages_dir, "app.py")
    other_before = (pages_dir / (other_page + ".html")).stat().st_mtime_ns

    (tmp_path / "ui.ts").write_text(
        TS + "\nexport function reset({ hard }: Opts): void {\n"
             "  render({ title: 'x', items: [] })\n}\n",
        encoding="utf-8")

    verdict = refresh_page(str(tmp_path), str(output), changed_page)

    assert verdict["state"] == "rebuilt"
    assert verdict["changed"] == ["ui.ts"]
    assert (pages_dir / (other_page + ".html")).stat().st_mtime_ns == other_before, \
        "an unrelated page is not touched"

    # The new symbol is in the page, with the span the fixed parser gives it —
    # a destructured parameter used to close the body on the signature line.
    body = (pages_dir / (changed_page + ".html")).read_text(encoding="utf-8")
    anchors = json.loads(body.split("const ANCHORS = ", 1)[1].split(";\n", 1)[0])
    assert "ui.ts::reset" in anchors
    assert anchors["ui.ts::reset"]["le"] > anchors["ui.ts::reset"]["ls"], \
        "a multi-line function must not be one line long"
    assert anchors["ui.ts::render"]["le"] == 4


def test_a_second_open_after_a_rebuild_is_current_again(tmp_path):
    output, pages_dir = _project(tmp_path)
    page = _page_of(pages_dir, "app.py")
    (tmp_path / "app.py").write_text(PY_SRC + "\n\ndef extra():\n    return main()\n",
                                     encoding="utf-8")

    assert refresh_page(str(tmp_path), str(output), page)["state"] == "rebuilt"
    again = refresh_page(str(tmp_path), str(output), page)
    assert again["state"] == "current", "the rebuild must record the new hashes"


def test_page_ids_do_not_move_when_the_file_set_changes(tmp_path):
    output, pages_dir = _project(tmp_path)
    before = {name: _page_of(pages_dir, name) for name in ("app.py", "ui.ts")}

    # Sorts before both existing files, which under position-derived ids would
    # have shifted every page after it. An id derived from the path cannot move.
    (tmp_path / "aaa.py").write_text("def first():\n    return 1\n", encoding="utf-8")
    generate_all_anchors(str(tmp_path))
    generate(str(tmp_path), str(output))

    for name, ident in before.items():
        assert _page_of(pages_dir, name) == ident, "{} moved".format(name)
    assert _page_of(pages_dir, "aaa.py") == draw_pages.page_id("aaa.py")


def test_an_unrelated_new_file_leaves_other_pages_alone(tmp_path):
    output, pages_dir = _project(tmp_path)
    page = _page_of(pages_dir, "ui.ts")
    (tmp_path / "aaa.py").write_text("def first():\n    return 1\n", encoding="utf-8")
    generate_all_anchors(str(tmp_path))

    verdict = refresh_page(str(tmp_path), str(output), page)

    # The page itself is still true — none of its own inputs moved — so it is
    # not redrawn. The file tree did move, so the shell is brought up to date
    # in the same pass and starts linking to the new file.
    assert verdict["changed"] == [], verdict
    assert verdict["shell"] is True, verdict
    assert "aaa.py" in output.read_text(encoding="utf-8")
    assert draw_pages.page_id("aaa.py") in output.read_text(encoding="utf-8")


def test_a_file_the_full_pass_never_saw_gets_its_page_on_first_open(tmp_path):
    output, pages_dir = _project(tmp_path)
    (tmp_path / "late.py").write_text("def late():\n    return 2\n", encoding="utf-8")
    generate_all_anchors(str(tmp_path))
    ident = draw_pages.page_id("late.py")
    assert not (pages_dir / (ident + ".html")).exists()

    verdict = refresh_page(str(tmp_path), str(output), ident)

    assert verdict["state"] == "created", verdict
    assert (pages_dir / (ident + ".html")).exists()
    assert "late.py::late" in (pages_dir / (ident + ".html")).read_text(encoding="utf-8")


def test_a_deleted_file_loses_its_page(tmp_path):
    output, pages_dir = _project(tmp_path)
    page = _page_of(pages_dir, "ui.ts")
    (tmp_path / "ui.ts").unlink()
    generate_all_anchors(str(tmp_path))

    verdict = refresh_page(str(tmp_path), str(output), page)

    assert verdict["state"] == "removed", verdict
    assert not (pages_dir / (page + ".html")).exists()
    assert not draw_pages.manifest_path(pages_dir, page).exists()


def test_the_cheap_answer_stops_reading_the_index(tmp_path):
    output, pages_dir = _project(tmp_path)
    page = _page_of(pages_dir, "ui.ts")
    # A first call after the full pass may still look, because the index was
    # written after the covered-file list. It must record that it looked, so the
    # next open is settled by hashes alone.
    refresh_page(str(tmp_path), str(output), page)
    assert draw_pages.may_have_new_files(pages_dir, tmp_path / ".codedendrite" / "anchors.json") is False
    assert refresh_page(str(tmp_path), str(output), page)["state"] == "current"


def test_a_lost_manifest_is_rebuilt_not_trusted(tmp_path):
    output, pages_dir = _project(tmp_path)
    page = _page_of(pages_dir, "ui.ts")
    draw_pages.manifest_path(pages_dir, page).unlink()

    # With no record of what the page was built from, "unchanged" is not
    # something anyone can claim. The page is redone and the record restored.
    verdict = refresh_page(str(tmp_path), str(output), page)
    assert verdict["state"] == "created", verdict
    assert draw_pages.manifest_path(pages_dir, page).exists()


def test_an_id_belonging_to_no_file_is_not_invented(tmp_path):
    output, _pages_dir = _project(tmp_path)
    assert refresh_page(str(tmp_path), str(output),
                        draw_pages.page_id("never/existed.py"))["state"] == "unknown"


def test_hash_is_content_not_mtime(tmp_path):
    target = tmp_path / "same.py"
    target.write_text("x = 1\n", encoding="utf-8")
    first = draw_pages.file_hash(target)
    import os
    os.utime(target, (0, 0))
    assert draw_pages.file_hash(target) == first, "touching a file changes nothing"
    target.write_text("x = 2\n", encoding="utf-8")
    assert draw_pages.file_hash(target) != first
