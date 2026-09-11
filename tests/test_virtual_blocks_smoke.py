import sys
from pathlib import Path
import shutil


ROOT = str(Path(__file__).resolve().parent.parent)
TMP_ROOT = str(Path(ROOT).parent.parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from index.api.anchors import generate_all_anchors, load_anchors
from relate.api.relations import generate_relations, load_relations


def test_virtual_blocks_create_parent_block_child_chain():
    tmp_path = Path(TMP_ROOT) / "tmp_cd_virtual_pytest"
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True)
    sample = tmp_path / "sample.py"
    sample.write_text(
        "\n".join(
            [
                "def child():",
                "    return 1",
                "",
                "def main(flag, items):",
                "    if flag:",
                "        child()",
                "    for item in items:",
                "        child()",
                "    return 0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    generate_all_anchors(str(tmp_path), include_virtual_blocks=True)
    generate_relations(str(tmp_path))

    anchors = load_anchors(str(tmp_path))
    relations = load_relations(str(tmp_path))

    virtual_blocks = [a for a in anchors.values() if a.symbol_type == "virtual_block"]
    assert virtual_blocks, "expected virtual block anchors"

    main_id = "sample.py::main"
    child_id = "sample.py::child"
    block_ids = {a.id for a in virtual_blocks if a.parent_anchor == main_id}
    assert block_ids, "expected blocks owned by main"

    edges = relations["edges"]
    parent_to_block = [
        e for e in edges
        if e["from_id"] == main_id and e["to_id"] in block_ids and e["edge_type"] == "call"
    ]
    assert parent_to_block, "expected parent -> block call edges"

    block_to_child = [
        e for e in edges
        if e["from_id"] in block_ids and e["to_id"] == child_id and e["edge_type"] == "call"
    ]
    assert block_to_child, "expected block -> child call edges"

    direct_parent_child = [
        e for e in edges
        if e["from_id"] == main_id and e["to_id"] == child_id and e["edge_type"] == "call"
    ]
    assert not direct_parent_child, "nested control-flow call should be routed through virtual blocks"
