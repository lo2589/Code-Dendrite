"""Command line entry for snapshot, replay, validation, and summary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from usage.evaluation import _read_json, create_snapshot, replay, validate_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cdd evaluation")
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("root")
    snapshot.add_argument("issue")
    snapshot.add_argument("output_dir")
    snapshot.add_argument("--instance-id", required=True)
    snapshot.add_argument("--base-commit")
    replay_cmd = sub.add_parser("replay")
    replay_cmd.add_argument("tasks")
    replay_cmd.add_argument("run_dir")
    replay_cmd.add_argument("--output")
    replay_cmd.add_argument("--snapshot-dir")
    for name in ("validate", "summary"):
        sub.add_parser(name).add_argument("report")
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            result = create_snapshot(args.root, args.issue, args.output_dir,
                                     args.instance_id, args.base_commit)
            print(f"快照：{result}")
        elif args.command == "replay":
            result = replay(args.tasks, args.run_dir, args.output, args.snapshot_dir)
            print(f"回放报告：{result}")
        else:
            result = validate_report(_read_json(Path(args.report).expanduser().resolve()))
            if args.command == "validate":
                print("评测报告有效")
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"评测失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
