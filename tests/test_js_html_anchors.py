"""JS/TS regex-analyzer edges, and inline <script> blocks inside .html.

Three bugs found together while tracing a real front-end call chain that
codedendrite could not see at all: the extractor crashed on one of its own
three function-declaration patterns, .html files were never opened, and the
one that was extracted (calls, as bare identifiers) was discarded before it
reached anchors.json rather than being handed to the resolver that already
exists to turn bare names into file::symbol edges.
"""

import tempfile
import unittest
from pathlib import Path

from index.api.anchors import generate_all_anchors, load_anchors
from parse.codeAnalysis.analyzer import get_analyzer


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TypeScriptAnalyzerCrashTests(unittest.TestCase):
    def test_function_expr_pattern_has_no_second_group_but_must_not_crash(self) -> None:
        # function_patterns' third entry (`const x = function`) captures only
        # the name; a source containing this form used to raise IndexError
        # from an unconditional match.group(2) — silently discarding the
        # whole file wherever the caller's try/except swallowed it.
        analyzer = get_analyzer(".", language="typescript")
        source = "const handler = function(a, b) { return a + b; };"
        functions = analyzer._extract_functions(source, "x.js")
        names = {f.name for f in functions}
        self.assertIn("handler", names)


class HtmlInlineScriptAnchorTests(unittest.TestCase):
    def test_functions_inside_a_script_tag_are_indexed_with_the_right_line(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(tmp_path / "page.html", (
                "<!doctype html>\n"
                "<body>\n"
                "<script>\n"
                "function outer(){\n"
                "  return inner();\n"
                "}\n"
                "function inner(){ return 1; }\n"
                "</script>\n"
                "</body>\n"
            ))
            generate_all_anchors(root=str(tmp_path))
            anchors = load_anchors(str(tmp_path))

            outer = anchors.get("page.html::outer")
            inner = anchors.get("page.html::inner")
            self.assertIsNotNone(outer, "inline <script> functions were not indexed at all")
            self.assertIsNotNone(inner)
            # Line 4 in the file: 3 lines of markup/tag, then `function outer(){`.
            self.assertEqual(outer.line_start, 4)

    def test_a_script_with_only_a_src_attribute_is_not_treated_as_inline(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(tmp_path / "page.html", '<script src="app.js"></script>\n')
            generate_all_anchors(root=str(tmp_path))
            anchors = load_anchors(str(tmp_path))
            self.assertFalse(
                any(a.file == "page.html" for a in anchors.values()),
                "a linked script has no inline body to extract functions from",
            )


class JsTsCalleeResolutionTests(unittest.TestCase):
    def test_same_file_bare_call_names_become_real_edges(self) -> None:
        # The regex extractor has no scope information, so a call comes out as
        # a bare name ("helper", not "file.js::helper"). _finalize_anchor_graph
        # already resolves any anchor's callees generically — same-file
        # candidate first, then a project-wide-unique symbol — for every
        # language; the bug was that JS/TS anchors never populated callees at
        # all, so that existing resolver had nothing to work with.
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _write(tmp_path / "app.js", (
                "function main(){\n"
                "  return helper();\n"
                "}\n"
                "function helper(){ return 1; }\n"
            ))
            generate_all_anchors(root=str(tmp_path))
            anchors = load_anchors(str(tmp_path))

            main = anchors.get("app.js::main")
            helper = anchors.get("app.js::helper")
            self.assertIsNotNone(main)
            self.assertIsNotNone(helper)
            self.assertIn("app.js::helper", main.callees)
            self.assertIn("app.js::main", helper.callers)


if __name__ == "__main__":
    unittest.main()
