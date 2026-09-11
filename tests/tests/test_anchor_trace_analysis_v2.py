import tempfile
import unittest
from pathlib import Path

from evaluation.analyze_anchor_trace_v2 import (
    build_graph,
    common_prefix_last,
    extract_read_sources,
    infer_start_anchor,
    map_touches_to_anchors,
    official_statuses,
    parse_patch_touches,
    shortest_path,
)


class AnchorTraceAnalysisV2Tests(unittest.TestCase):
    def test_patch_insert_maps_to_old_cursor(self):
        diff = """diff --git a/pkg/a.py b/pkg/a.py
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -10,2 +10,3 @@
 keep
+new
 old
"""
        touches = parse_patch_touches(diff)
        self.assertEqual(touches[0].file, "pkg/a.py")
        self.assertEqual(touches[0].lines, (11,))

    def test_touch_prefers_smallest_enclosing_anchor(self):
        touches = parse_patch_touches("""--- a/a.py
+++ b/a.py
@@ -5 +5 @@
-old
+new
""")
        anchors = {
            "a.py::C": {"file": "a.py", "line_start": 1, "line_end": 20, "symbol_type": "class"},
            "a.py::C.f": {"file": "a.py", "line_start": 4, "line_end": 8, "symbol_type": "method"},
        }
        mapped, _ = map_touches_to_anchors(touches, anchors)
        self.assertEqual(mapped, ["a.py::C.f"])

    def test_issue_owner_and_member_select_method(self):
        packet = {
            "signals": [
                {"kind": "exact_symbol", "value": "VotingClassifier"},
                {"kind": "exact_symbol", "value": "fit"},
            ]
        }
        anchors = {
            "v.py::VotingClassifier": {
                "symbol": "VotingClassifier",
                "file": "v.py",
                "line_start": 1,
                "line_end": 30,
            },
            "v.py::VotingClassifier.fit": {
                "symbol": "VotingClassifier.fit",
                "file": "v.py",
                "line_start": 10,
                "line_end": 20,
            },
            "x.py::Other.fit": {
                "symbol": "Other.fit",
                "file": "x.py",
                "line_start": 1,
                "line_end": 5,
            },
        }
        self.assertEqual(infer_start_anchor(packet, anchors)["anchor"], "v.py::VotingClassifier.fit")

    def test_recommended_anchor_is_authoritative(self):
        packet = {
            "signals": [{"kind": "exact_symbol", "value": "exception"}],
            "recommended_action": {"kind": "expand_anchor", "target": "a.py::right"},
        }
        anchors = {
            "a.py::right": {"symbol": "right", "file": "a.py"},
            "x.py::exception": {"symbol": "exception", "file": "x.py"},
        }
        self.assertEqual(infer_start_anchor(packet, anchors)["anchor"], "a.py::right")

    def test_deepest_traceback_file_line_is_authoritative(self):
        packet = {
            "signals": [
                {
                    "kind": "traceback_frame",
                    "value": "/venv/site-packages/pkg/a.py",
                    "line": 12,
                },
                {"kind": "exact_symbol", "value": "wrong"},
            ],
            "recommended_action": {"kind": "expand_anchor", "target": "x.py::wrong"},
        }
        anchors = {
            "pkg/a.py::C": {
                "symbol": "C",
                "file": "pkg/a.py",
                "line_start": 1,
                "line_end": 30,
                "symbol_type": "class",
            },
            "pkg/a.py::C.f": {
                "symbol": "C.f",
                "file": "pkg/a.py",
                "line_start": 10,
                "line_end": 15,
                "symbol_type": "method",
            },
            "x.py::wrong": {
                "symbol": "wrong",
                "file": "x.py",
                "line_start": 1,
                "line_end": 2,
            },
        }
        result = infer_start_anchor(packet, anchors)
        self.assertEqual(result["anchor"], "pkg/a.py::C.f")
        self.assertEqual(result["source_line"], 12)

    def test_extracts_numbered_read_source(self):
        turns = [{"role": "user", "content": "READ a.py:4-5\n```python\n  4  def f():\n  5      return 1\n```"}]
        self.assertEqual(extract_read_sources(turns)["a.py"][5], "    return 1")

    def test_accepts_versioned_pipeline_report(self):
        statuses = official_statuses(
            {"summary": {"resolved_ids": ["ok"], "error_ids": ["bad"]}}
        )
        self.assertEqual(statuses, {"ok": "resolved", "bad": "error"})

    def test_path_and_fork(self):
        graph = {"A": {"B"}, "B": {"C"}}
        self.assertEqual(shortest_path(graph, "A", "C"), ["A", "B", "C"])
        self.assertEqual(common_prefix_last(["A", "B"], ["A", "B", "C"]), "B")

    def test_read_source_recovers_nested_lexical_edge(self):
        anchors = {
            "a.py::entry": {"symbol": "entry", "file": "a.py", "line_start": 1, "line_end": 2},
            "a.py::gold": {"symbol": "gold", "file": "a.py", "line_start": 4, "line_end": 6},
            "a.py::helper": {"symbol": "helper", "file": "a.py", "line_start": 8, "line_end": 9},
        }
        shown = {"a.py": {4: "def gold():", 5: "    delayed(helper)()", 6: "    return 1"}}
        with tempfile.TemporaryDirectory() as tmp:
            directed, _ = build_graph(
                Path(tmp),
                anchors,
                {"edges": []},
                lexical_files={"a.py"},
                read_sources=shown,
            )
        self.assertIn("a.py::helper", directed["a.py::gold"])


if __name__ == "__main__":
    unittest.main()
