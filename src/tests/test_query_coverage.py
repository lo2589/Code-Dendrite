import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


CODEDENDRITE_ROOT = Path(__file__).resolve().parents[1]
if str(CODEDENDRITE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODEDENDRITE_ROOT))

from analyzer.anchors import get_anchor, resolve_anchor_candidates
from api.inspector import find_attribute_call_sites, get_upward_chain
from api.query import cmd_chain, cmd_edges


def _anchor(anchor_id, symbol, file, line, symbol_type):
    return {
        "id": anchor_id,
        "symbol": symbol,
        "file": file,
        "line_start": line,
        "line_end": line + 1,
        "hash": "",
        "symbol_type": symbol_type,
    }


class QueryCoverageTests(unittest.TestCase):
    def test_callers_excludes_dataflow_neighbors(self):
        anchors = {
            name: _anchor(f"{name}.py::{name}", name, f"{name}.py", 1, "function")
            for name in ("discount", "total_due", "tax", "route")
        }
        records = {item["id"]: item for item in anchors.values()}
        (self.root / ".codedendrite" / "anchors.json").write_text(
            json.dumps(records), encoding="utf-8"
        )
        (self.root / ".codedendrite" / "relations.json").write_text(
            json.dumps({"edges": [
                {"from_id": "total_due.py::total_due", "to_id": "discount.py::discount", "edge_type": "call"},
                {"from_id": "route.py::route", "to_id": "discount.py::discount", "edge_type": "dispatch"},
                {"from_id": "tax.py::tax", "to_id": "discount.py::discount", "edge_type": "dataflow"},
            ]}), encoding="utf-8"
        )
        chain = get_upward_chain("discount.py::discount", str(self.root))
        self.assertEqual({row["symbol"] for row in chain if row["depth"] == 1},
                         {"total_due", "route"})

    def test_upward_chain_keeps_same_named_callers_from_distinct_files(self):
        anchors = {
            "target.py::parse_args": _anchor(
                "target.py::parse_args", "parse_args", "target.py", 1, "function"
            ),
            "first.py::main": _anchor(
                "first.py::main", "main", "first.py", 1, "function"
            ),
            "second.py::main": _anchor(
                "second.py::main", "main", "second.py", 1, "function"
            ),
        }
        (self.root / ".codedendrite" / "anchors.json").write_text(
            json.dumps(anchors), encoding="utf-8"
        )
        (self.root / ".codedendrite" / "relations.json").write_text(
            json.dumps({
                "edges": [
                    {"from_id": "first.py::main", "to_id": "target.py::parse_args", "edge_type": "call"},
                    {"from_id": "second.py::main", "to_id": "target.py::parse_args", "edge_type": "call"},
                ]
            }),
            encoding="utf-8",
        )

        chain = get_upward_chain("target.py::parse_args", str(self.root))
        self.assertEqual(
            {entry["id"] for entry in chain if entry["depth"] == 1},
            {"first.py::main", "second.py::main"},
        )

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / ".codedendrite").mkdir()
        (self.root / "methods.py").write_text(
            "class First:\n"
            "    def end_cell(self):\n"
            "        pass\n\n"
            "class Second:\n"
            "    def end_cell(self):\n"
            "        pass\n\n"
            "def run(manager):\n"
            "    manager.end_cell()\n",
            encoding="utf-8",
        )
        anchors = {
            "methods.py::First.end_cell": _anchor(
                "methods.py::First.end_cell", "First.end_cell", "methods.py", 2, "method"
            ),
            "methods.py::Second.end_cell": _anchor(
                "methods.py::Second.end_cell", "Second.end_cell", "methods.py", 6, "method"
            ),
            "methods.py::run": _anchor(
                "methods.py::run", "run", "methods.py", 9, "function"
            ),
        }
        (self.root / ".codedendrite" / "anchors.json").write_text(
            json.dumps(anchors), encoding="utf-8"
        )
        (self.root / ".codedendrite" / "relations.json").write_text(
            json.dumps({"edges": []}), encoding="utf-8"
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_short_method_name_returns_all_candidates(self):
        candidates = resolve_anchor_candidates("end_cell", str(self.root))
        self.assertEqual(
            {candidate.id for candidate in candidates},
            {
                "methods.py::First.end_cell",
                "methods.py::Second.end_cell",
            },
        )

    def test_get_anchor_does_not_silently_choose_ambiguous_short_name(self):
        self.assertIsNone(get_anchor("end_cell", str(self.root)))
        resolved = get_anchor("methods.py::First.end_cell", str(self.root))
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.id, "methods.py::First.end_cell")

    def test_callers_rejects_ambiguous_short_name(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = cmd_chain("end_cell", str(self.root), direction="up")
        self.assertEqual(status, 2)
        self.assertIn("Ambiguous symbol", stderr.getvalue())
        self.assertIn("methods.py::First.end_cell", stderr.getvalue())
        self.assertIn("methods.py::Second.end_cell", stderr.getvalue())

    def test_full_method_id_reports_unresolved_attribute_calls(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = cmd_chain(
                "methods.py::First.end_cell",
                str(self.root),
                direction="up",
            )
        self.assertEqual(status, 0)
        output = stdout.getvalue()
        self.assertIn("does not prove the method is unused", output)
        self.assertIn("methods.py:10  manager.end_cell(...)", output)

    def test_find_zero_edges_reports_coverage_warning(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            cmd_edges("end_cell", str(self.root))
        output = stdout.getvalue()
        self.assertIn("0 indexed edges does not prove this method is unused", output)
        self.assertIn("Possible unresolved attribute calls", output)

    def test_attribute_call_sites_do_not_claim_type_resolution(self):
        sites = find_attribute_call_sites("end_cell", str(self.root))
        self.assertEqual(len(sites), 1)
        self.assertEqual(sites[0]["receiver"], "manager")
        self.assertEqual(sites[0]["line"], 10)


if __name__ == "__main__":
    unittest.main()
