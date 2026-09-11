import json

from evaluation import run_swe_cdd_v2_6 as runner


def test_v2_6_metadata_is_explicit_and_has_no_forced_diff_limit():
    meta = runner.base_meta_v2_6({}, ".")
    assert meta["nav_protocol"] == "cdd_v2_6"
    assert meta["cdd_runner_version"] == "cdd.swebench_runner.v2.6"
    assert meta["prompt_language"] == "zh-CN"
    assert meta["anchor_read_version"] == "cdd.anchor_read.v2.6"
    assert meta["navigation_action_limit"] is None
    assert meta["navigation_limit_policy"] == "no_forced_diff_transition_v2_6"


def test_v2_6_prompt_is_anchor_first_and_has_complete_diff_shape():
    prompt = runner.SYSTEM_NAV_CDD_V2_6
    assert "<anchor> 文件/路径.py::符号" in prompt
    assert "该命令优先于直接读取原文件" in prompt
    assert "diff --git a/文件/路径.py b/文件/路径.py" in prompt
    assert "七个导航动作" not in prompt
    assert "软先验" not in prompt
    assert "A（问题入口）" not in prompt
    assert runner.NAV_HINT_CDD_V2_6 == ""


def test_v2_6_parser_keeps_all_commands_for_rejection():
    commands = runner.extract_commands_v2_6(
        "<anchors> distinct\n<read> django/db/models/query.py:1-100"
    )
    assert [command[0] for command in commands] == ["anchors", "read"]


def test_v2_6_anchor_reads_only_the_selected_anchor(tmp_path):
    source = tmp_path / "pkg" / "query.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "class QuerySet:\n"
        "    def distinct(self, *field_names):\n"
        "        return self._chain()\n"
        "\n"
        "    def other(self):\n"
        "        return None\n",
        encoding="utf-8",
    )
    index = tmp_path / ".codedendrite" / "anchors.json"
    index.parent.mkdir()
    index.write_text(json.dumps({
        "pkg/query.py::QuerySet.distinct": {
            "id": "pkg/query.py::QuerySet.distinct",
            "symbol": "QuerySet.distinct",
            "file": "pkg/query.py",
            "line_start": 2,
            "line_end": 3,
            "hash": "test",
            "symbol_type": "method"
        }
    }), encoding="utf-8")
    meta = runner.base_meta_v2_6({}, str(tmp_path))

    result = runner.run_tool_v2_6(
        "anchor",
        "pkg/query.py::QuerySet.distinct",
        str(tmp_path),
        meta,
    )

    assert "ANCHOR pkg/query.py::QuerySet.distinct" in result
    assert "def distinct" in result
    assert "def other" not in result
    assert meta["inspected_nodes"] == ["pkg/query.py::QuerySet.distinct"]
    assert meta["read_files"] == ["pkg/query.py"]


def test_v2_6_packet_formatter_translates_fixed_labels():
    packet = {
        "issue": {"title": "broken"},
        "navigation": {"status": "ambiguous", "confidence": "low", "reason": "原因"},
        "candidates": [],
        "alternatives": [],
        "boundaries": [{"signal_id": "S0", "resolution": "unresolved"}],
        "recommended_action": None,
    }
    text = runner.format_issue_packet_compact_zh(packet)
    assert "问题：broken" in text
    assert "导航：模糊/低 | 原因" in text
    assert "边界：S0:未解决" in text
    assert "建议动作：无" in text
