from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve()
CODEDENDRITE_ROOT = HERE.parents[1]
PROJECT_ROOT = CODEDENDRITE_ROOT.parents[1]

sys.path.insert(0, str(CODEDENDRITE_ROOT))

from serve.api.workflow import run_debug_loop


def main() -> None:
    result = run_debug_loop(
        error_msg='Runtime error near handle_request line 804 when method == "chat_message"',
        file_path="backend/main.py",
        root=str(PROJECT_ROOT),
        entry_symbol="LLMSchedulerServer.handle_request",
        target_symbol="LLMSchedulerServer.handle_request",
        conditions={"method": "chat_message"},
        refresh=True,
        limit=3,
    )

    print("=== Loop Stage ===")
    print(result["loop_stage"])
    print("=== Top Suspect ===")
    print((result.get("top_suspect") or {}).get("symbol"))
    print("=== Loop Summary ===")
    print(result["loop_summary"])
    print("=== Module Summary ===")
    print(result.get("module_summary"))
    print("=== Next Action ===")
    print(result["next_action"])
    print("=== Verification Summary ===")
    print(result["verification_summary"])

    assert result["loop_stage"] == "verify", "loop_stage should end at verify"
    assert (result.get("top_suspect") or {}).get("symbol"), "top_suspect should not be empty"
    assert result.get("module_summary"), "module_summary should not be empty"
    assert result.get("loop_summary"), "loop_summary should not be empty"
    assert result.get("next_action"), "next_action should not be empty"

    print("\nPASS: debug loop smoke test succeeded")


if __name__ == "__main__":
    main()
