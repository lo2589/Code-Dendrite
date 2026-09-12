"""Isolated worker that executes a target project's YAML loader."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
from pathlib import Path


def main(argv=None) -> int:
    args = list(argv or sys.argv[1:])
    if len(args) != 4:
        print("usage: yaml_profile_worker ROOT MODULE FUNCTION YAML", file=sys.stderr)
        return 2
    root, module_name, function_name, yaml_path = args
    sys.path.insert(0, str(Path(root).resolve()))
    top_package = module_name.split(".", 1)[0]
    loaded_top = sys.modules.get(top_package)
    if loaded_top is not None and not hasattr(loaded_top, "__path__"):
        del sys.modules[top_package]

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        module = importlib.import_module(module_name)
        loader = module
        for part in function_name.split("."):
            loader = getattr(loader, part)
        result = loader(Path(yaml_path))
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    if not isinstance(result, dict):
        raise TypeError("{} returned {}, expected mapping".format(
            function_name, type(result).__name__,
        ))
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
