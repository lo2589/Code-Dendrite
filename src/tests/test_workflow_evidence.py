import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from usage.workflow import _rank_bug_suspects, _resolve_target_anchor
from analyzer.shared.types import Anchor


def _anchor(anchor_id: str, line: int) -> Anchor:
    file_name, symbol = anchor_id.split("::", 1)
    return Anchor(
        id=anchor_id,
        symbol=symbol,
        file=file_name,
        line_start=line,
        line_end=line + 2,
        hash="",
    )


class WorkflowEvidenceTests(unittest.TestCase):
    def test_file_target_is_not_promoted_to_first_function(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            anchors = {
                "api/cli.py::_ensure_path": _anchor("api/cli.py::_ensure_path", 18),
                "api/cli.py::main": _anchor("api/cli.py::main", 329),
            }
            with patch(
                "usage.smart.smart_analyze",
                return_value=SimpleNamespace(target="api/cli.py"),
            ):
                resolved = _resolve_target_anchor(
                    target_symbol=None,
                    error_msg="parser.parse_args was linked incorrectly",
                    file_path="api/cli.py",
                    root=str(root),
                    anchors=anchors,
                )
            self.assertIsNone(resolved)

    def test_same_file_alone_is_not_enough_for_edit_suspect(self) -> None:
        anchors = {
            "api/cli.py::_ensure_path": _anchor("api/cli.py::_ensure_path", 18),
            "api/cli.py::main": _anchor("api/cli.py::main", 329),
        }
        suspects = _rank_bug_suspects(
            anchors=anchors,
            target_anchor=None,
            relation_edges=[],
            traced_nodes=[],
            file_path="api/cli.py",
            error_msg="parser.parse_args was linked incorrectly",
            limit=5,
        )
        self.assertEqual(suspects, [])


if __name__ == "__main__":
    unittest.main()
