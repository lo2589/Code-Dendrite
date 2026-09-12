import json
import sys
from pathlib import Path


ROOT = str(Path(__file__).resolve().parent.parent)            # src：import 根
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])       # 仓库根
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from usage.packets.task_context_packet import generate_task_context  # noqa: E402


ANCHORS = {
    "app.py::main": {
        "id": "app.py::main", "symbol": "main", "file": "app.py",
        "line_start": 1, "line_end": 4,
    },
    "app.py::helper": {
        "id": "app.py::helper", "symbol": "helper", "file": "app.py",
        "line_start": 6, "line_end": 8,
    },
    "other.py::helper": {
        "id": "other.py::helper", "symbol": "helper", "file": "other.py",
        "line_start": 1, "line_end": 2,
    },
}


def _golden():
    path = Path(__file__).parent / "fixtures" / "evidence_lanes_v1_v2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _packet(relations):
    return generate_task_context(
        "app.py::main", root=PROJECT_ROOT, anchors=ANCHORS, relations=relations,
        module_tree=None,
    )


def _lane_summary(packet):
    task = packet["task_slice"]
    return {
        "candidate_entries": [row["entry"] for row in task["candidates"]],
        "boundary_resolutions": sorted({row["resolution"] for row in task["boundaries"]}),
    }


def test_v1_projection_relations_are_boundaries_not_commands():
    packet = _packet({
        "edges": [{
            "from_id": "app.py::main", "to_id": "app.py::helper",
            "edge_type": "call",
        }]
    })

    assert _lane_summary(packet) == _golden()["v1_projection"]
    assert packet["navigation"]["relation_resolution_counts"] == {
        "resolution_unavailable": 1,
    }
    assert packet["anchor_packet"]["downstream"] == []
    assert packet["anchor_packet"]["boundaries"][0]["resolution"] == "resolution_unavailable"
    assert all("next_command" not in row for row in packet["task_slice"]["boundaries"])


def test_v2_resolution_values_remain_distinct():
    packet = _packet({
        "edges": [
            {
                "from_id": "app.py::main", "to_id": "app.py::helper",
                "edge_type": "call", "resolution": "exact",
                "evidence": "compiler_confirmed",
            },
            {
                "from_id": "app.py::main", "to_id": "other.py::helper",
                "edge_type": "call", "resolution": "possible",
                "evidence": "short_name_candidate",
            },
            {
                "from_id": "app.py::main", "to_id": "missing.py::unknown",
                "edge_type": "call", "resolution": "unresolved",
                "evidence": "receiver_type_unknown",
            },
            {
                "from_id": "app.py::main", "to_id": "native.py::unknown",
                "edge_type": "call", "resolution": "unsupported",
                "evidence": "frontend_capability_missing",
            },
        ]
    })

    assert _lane_summary(packet) == _golden()["v2_program_model"]
    related = packet["task_slice"]["candidates"][1]
    assert related["entry"] == "app.py::helper"
    assert related["next_command"] == "expand app.py::helper"
    assert packet["navigation"]["relation_resolution_counts"] == {
        "exact": 1, "possible": 1, "unresolved": 1, "unsupported": 1,
    }
    assert all("next_command" not in row for row in packet["task_slice"]["boundaries"])


def test_ambiguous_entry_uses_alternative_lane_only():
    packet = generate_task_context(
        "helper", root=PROJECT_ROOT, anchors=ANCHORS, relations={"edges": []},
        module_tree=None,
    )
    task = packet["task_slice"]
    summary = {
        "candidate_count": len(task["candidates"]),
        "alternative_count": len(task["alternatives"]),
        "recommended_command_count": sum(
            1 for row in task["alternatives"] if "next_command" in row
        ),
    }

    assert summary == _golden()["ambiguous_entry"]
    assert packet["navigation"]["status"] == "ambiguous"
    assert all(row["resolution"] == "possible" for row in task["alternatives"])
