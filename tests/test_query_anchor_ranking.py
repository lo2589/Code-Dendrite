from serve.api.query import _rank_anchor_matches
from base.shared.types import Anchor


def _anchor(anchor_id, symbol, file, line):
    return Anchor(
        id=anchor_id,
        symbol=symbol,
        file=file,
        line_start=line,
        line_end=line + 1,
        hash="test",
    )


def test_anchor_search_ranks_exact_symbol_before_path_matches():
    anchors = {
        "code/compact/processor.py::Processor": _anchor(
            "code/compact/processor.py::Processor", "Processor", "code/compact/processor.py", 1
        ),
        "code/run.py::process": _anchor(
            "code/run.py::process", "process", "code/run.py", 10
        ),
        "code/worker.py::Worker.process": _anchor(
            "code/worker.py::Worker.process", "Worker.process", "code/worker.py", 20
        ),
    }

    matches = _rank_anchor_matches(anchors, "process")

    assert [anchor_id for anchor_id, _ in matches] == [
        "code/run.py::process",
        "code/worker.py::Worker.process",
        "code/compact/processor.py::Processor",
    ]


def test_anchor_search_keeps_legacy_path_only_matches():
    anchor_id = "code/compact/processor.py::Unrelated"
    anchors = {
        anchor_id: _anchor(anchor_id, "Unrelated", "code/compact/processor.py", 1)
    }

    assert [item[0] for item in _rank_anchor_matches(anchors, "process")] == [anchor_id]
