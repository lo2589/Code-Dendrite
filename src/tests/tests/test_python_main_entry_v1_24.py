import tempfile
from pathlib import Path

from analyzer.anchors import generate_all_anchors, load_anchors


def test_main_guard_is_its_own_anchor_calling_main() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        (root / "app.py").write_text(
            "def main():\n"
            "    return 1\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )

        generate_all_anchors(str(root))
        anchors = load_anchors(str(root))

        entry_id = "app.py::__main__"
        main_id = "app.py::main"
        assert "app.py::<module>" not in anchors
        assert anchors[entry_id].symbol == "__main__"
        assert anchors[entry_id].symbol_type == "entrypoint"
        assert anchors[entry_id].line_start == 4
        assert anchors[entry_id].line_end == 5
        assert anchors[entry_id].callees == [main_id]
        assert anchors[main_id].callers == [entry_id]
