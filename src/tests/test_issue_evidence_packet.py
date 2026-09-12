import json
import sys
from pathlib import Path


ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from usage.packets.issue_evidence_packet import (  # noqa: E402
    VERSION,
    extract_issue_signals,
    format_issue_packet_compact,
    generate_issue_evidence_packet,
    validate_issue_evidence_packet,
)


def _anchors():
    return {
        "django/utils/decorators.py::method_decorator": {
            "id": "django/utils/decorators.py::method_decorator",
            "symbol": "method_decorator",
            "file": "django/utils/decorators.py",
            "line_start": 20,
            "line_end": 50,
        },
        "django/auth/decorators.py::login_required": {
            "id": "django/auth/decorators.py::login_required",
            "symbol": "login_required",
            "file": "django/auth/decorators.py",
            "line_start": 5,
            "line_end": 10,
        },
        "tests/decorators.py::method_decorator": {
            "id": "tests/decorators.py::method_decorator",
            "symbol": "method_decorator",
            "file": "tests/decorators.py",
            "line_start": 3,
            "line_end": 6,
        },
    }


def test_full_issue_path_disambiguates_duplicate_symbol():
    issue = (Path(__file__).parent / "fixtures" / "issue_evidence_method_decorator.md").read_text()
    packet = generate_issue_evidence_packet(issue, anchors=_anchors())

    assert packet["version"] == VERSION
    assert packet["navigation"]["status"] == "resolved"
    assert packet["candidates"][0]["file"] == "django/utils/decorators.py"
    assert packet["recommended_action"]["kind"] == "expand_anchor"
    assert packet["recommended_action"]["target"] == "django/utils/decorators.py::method_decorator"
    assert len(packet["recommended_action"]["argv"]) == 3


def test_conflicting_strong_evidence_abstains():
    issue = """Failure in django/auth/decorators.py::login_required.
File \"/repo/django/utils/decorators.py\", line 25, in method_decorator
TypeError: bad wrapper
"""
    packet = generate_issue_evidence_packet(issue, anchors=_anchors())

    assert packet["navigation"]["status"] == "ambiguous"
    assert packet["recommended_action"] is None
    assert packet["candidates"] == []
    assert any(candidate["contradictions"] for candidate in packet["alternatives"])


def test_duplicate_symbol_without_path_is_ambiguous():
    packet = generate_issue_evidence_packet(
        "`method_decorator` breaks metadata", anchors=_anchors(),
    )
    assert packet["navigation"]["status"] == "ambiguous"
    assert packet["recommended_action"] is None
    assert packet["candidates"] == []
    assert len(packet["alternatives"]) == 2


def test_root_level_file_name_is_path_evidence():
    anchors = {
        "app.py::handler": {
            "id": "app.py::handler", "symbol": "handler", "file": "app.py",
            "line_start": 1, "line_end": 4,
        }
    }
    packet = generate_issue_evidence_packet(
        "The handler in app.py returns the wrong value.", anchors=anchors,
    )
    assert packet["navigation"]["status"] == "resolved"
    assert packet["recommended_action"]["target"] == "app.py"


def test_generic_prose_does_not_become_an_action():
    packet = generate_issue_evidence_packet(
        "The previous value should return a useful error message.", anchors=_anchors(),
    )
    assert packet["navigation"]["status"] == "unresolved"
    assert packet["recommended_action"] is None
    assert all(not signal["navigation_eligible"] for signal in packet["signals"])
    assert packet["boundaries"]


def test_deepest_traceback_frame_is_the_strong_frame():
    issue = """Traceback:
  File \"/repo/tests/decorators.py\", line 4, in test_it
  File \"/repo/django/utils/decorators.py\", line 25, in method_decorator
TypeError: bad wrapper
"""
    packet = generate_issue_evidence_packet(issue, anchors=_anchors())
    assert packet["navigation"]["status"] == "resolved"
    assert packet["candidates"][0]["file"] == "django/utils/decorators.py"


def test_packet_omits_raw_issue_and_schema_is_json():
    issue = "secret-ish issue text about `login_required`"
    packet = generate_issue_evidence_packet(issue, anchors=_anchors())
    schema_path = Path(ROOT) / "schemas" / "task_context_packet_v2.schema.json"
    schema = json.loads(schema_path.read_text())

    assert schema["properties"]["version"]["const"] == VERSION
    assert packet["issue"]["raw_text_included"] is False
    assert "raw_text" not in packet["issue"]
    assert packet["issue"]["sha256"]
    assert "Action:" in format_issue_packet_compact(packet)


def test_ambiguous_packet_cannot_carry_an_action():
    packet = generate_issue_evidence_packet(
        "`method_decorator` breaks metadata", anchors=_anchors(),
    )
    packet["recommended_action"] = {
        "kind": "inspect_file",
        "target": "tests/decorators.py",
        "argv": ["cdd", "file", "tests/decorators.py"],
        "because": ["S0"],
    }
    try:
        validate_issue_evidence_packet(packet)
    except ValueError as exc:
        assert "must abstain" in str(exc)
    else:
        raise AssertionError("ambiguous packet accepted an action")


def test_candidate_alternative_boundary_lanes_do_not_share_actions():
    packet = generate_issue_evidence_packet(
        "`method_decorator` fails with TypeError", anchors=_anchors(),
    )
    assert packet["candidates"] == []
    assert packet["alternatives"]
    assert packet["boundaries"]
    assert all("argv" not in row and "next_command" not in row for row in packet["alternatives"])
    assert all("argv" not in row and "next_command" not in row for row in packet["boundaries"])
