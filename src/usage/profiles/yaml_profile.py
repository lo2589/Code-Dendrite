"""Project-owned YAML loader bridge for config-routed call graphs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _loader_anchors(anchors: dict) -> list:
    registered = [
        anchor for anchor in anchors.values()
        if getattr(anchor, "registered_as", None) in {"config.load", "yaml.load"}
    ]
    named = [
        anchor for anchor in anchors.values()
        if str(getattr(anchor, "symbol", "")).rsplit(".", 1)[-1]
        in {"load_config", "load_yaml", "parse_yaml", "yaml_model_load"}
        and getattr(anchor, "symbol_type", "") in {"function", "method"}
    ]
    yaml_methods = [
        anchor for anchor in anchors.values()
        if str(getattr(anchor, "symbol", "")) == "YAML.load"
        and getattr(anchor, "symbol_type", "") == "method"
    ]
    unique = {}
    for anchor in registered + named + yaml_methods:
        unique[anchor.id] = anchor
    return list(unique.values())


def _module_name(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    if not normalized.endswith(".py"):
        raise ValueError("YAML loader is not a Python module: {}".format(file_path))
    module = normalized[:-3].replace("/", ".")
    if module.endswith(".__init__"):
        module = module[:-9]
    return module


def _flatten(data: dict) -> dict:
    flat = {}

    def visit(value: Any, path_parts: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, path_parts + (str(key),))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path_parts + (str(index),))
        else:
            flat[".".join(path_parts)] = value

    visit(data, ())
    return flat


def _token(value: Any) -> str | None:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value).strip().lower()
    return None


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _safe_load_with_bases(source: Path, seen: set[Path] | None = None) -> tuple[dict, list[str]]:
    """Safe YAML fallback with PaddleDetection-style recursive ``_BASE_``."""
    import yaml

    source = source.resolve()
    seen = set(seen or ())
    if source in seen:
        raise ValueError("recursive YAML _BASE_: {}".format(source))
    seen.add(source)
    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML document must be a mapping: {}".format(source))
    base_refs = data.pop("_BASE_", [])
    if isinstance(base_refs, str):
        base_refs = [base_refs]
    merged = {}
    included = []
    for raw_ref in base_refs or []:
        base_path = Path(str(raw_ref)).expanduser()
        if not base_path.is_absolute():
            base_path = source.parent / base_path
        base_data, nested = _safe_load_with_bases(base_path, seen)
        merged = _deep_merge(merged, base_data)
        included.extend(nested)
        included.append(str(base_path.resolve()))
    return _deep_merge(merged, data), included


def _mapping_paths(data: dict) -> set[str]:
    paths = set()

    def visit(value: Any, prefix: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = prefix + (str(key),)
                paths.add(".".join(child_path))
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, prefix + (str(index),))

    visit(data, ())
    return paths


def load_yaml_profile(path: str | Path, root: str | Path, anchors: dict) -> dict:
    """Execute the indexed project's own YAML loader in an isolated process."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError("YAML file not found: {}".format(source))
    repo_root = Path(__file__).resolve().parents[3]
    loader_errors = []
    data = None
    loader_id = None
    loader_candidates = _loader_anchors(anchors)
    for loader in loader_candidates:
        module = _module_name(loader.file)
        function = str(loader.symbol)
        command = [
            sys.executable,
            "-m",
            "tools.CodeDendrite.api.yaml_profile_worker",
            str(Path(root).expanduser().resolve()),
            module,
            function,
            str(source),
        ]
        result = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip() or "unknown loader error"
            loader_errors.append({"loader": loader.id, "error": message.splitlines()[-1]})
            continue
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            loader_errors.append({"loader": loader.id, "error": "invalid JSON result"})
            continue
        loader_id = loader.id
        break

    included_files = []
    if data is None:
        try:
            data, included_files = _safe_load_with_bases(source)
        except Exception as exc:
            raise ValueError("Project YAML loaders and safe fallback failed: {}".format(exc)) from exc
        suffix = "+_BASE_" if included_files else ""
        loader_id = "PyYAML.safe_load{} (fallback)".format(suffix)
    if not isinstance(data, dict):
        raise ValueError("Project YAML loader result must be a mapping")

    flat = _flatten(data)
    tokens = {token for token in (_token(value) for value in flat.values()) if token}
    return {
        "path": str(source),
        "loader": loader_id,
        "loader_candidates": [anchor.id for anchor in loader_candidates],
        "loader_errors": loader_errors,
        "included_files": included_files,
        "data": data,
        "flat": flat,
        "mapping_paths": sorted(_mapping_paths(data)),
        "tokens": tokens,
    }


def yaml_component_graph(anchors: dict, profile: dict) -> list[dict]:
    """Resolve ordered ``[from, repeat, component, args]`` YAML layer specs.

    A component is accepted only when its exact leaf symbol identifies one indexed
    class. This keeps YAML selection deterministic and avoids fuzzy name guesses.
    """
    by_leaf: dict[str, list] = {}
    for anchor in anchors.values():
        if getattr(anchor, "symbol_type", "") != "class":
            continue
        leaf = str(getattr(anchor, "symbol", "")).rsplit(".", 1)[-1]
        by_leaf.setdefault(leaf, []).append(anchor)

    rows = []

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, path + (str(key),))
            return
        if not isinstance(value, list):
            return
        for local_index, item in enumerate(value):
            if not (
                isinstance(item, list)
                and len(item) >= 3
                and isinstance(item[1], int)
                and isinstance(item[2], str)
                and (
                    isinstance(item[0], int)
                    or isinstance(item[0], list)
                    and all(isinstance(part, int) for part in item[0])
                )
            ):
                continue
            module_name = item[2]
            leaf = module_name.rsplit(".", 1)[-1]
            matches = by_leaf.get(leaf, [])
            rows.append({
                "index": len(rows),
                "path": ".".join(path + (str(local_index),)),
                "from": item[0],
                "repeats": item[1],
                "component": module_name,
                "anchor_id": matches[0].id if len(matches) == 1 else None,
                "resolution": "exact" if len(matches) == 1 else "unresolved" if not matches else "ambiguous",
            })

    visit(profile.get("data") or {}, ())
    return rows


def active_registered_keys(anchors: dict, profile: dict) -> set[str]:
    flat = dict(profile.get("flat") or {})
    mapping_paths = set(profile.get("mapping_paths") or ())
    mapping_leaves = {path.rsplit(".", 1)[-1] for path in mapping_paths}

    def words(value: str) -> list[str]:
        return [part for chunk in value.lower().replace("-", "_").split(".")
                for part in chunk.split("_") if part]

    def related(left: str, right: str) -> bool:
        return left == right or left.startswith(right) or right.startswith(left)

    active = set()
    for anchor in anchors.values():
        for site in getattr(anchor, "call_sites", []) or []:
            if not isinstance(site, dict):
                continue
            key = str(site.get("registry_key") or "")
            if not key:
                continue
            leaf = key.lower().rsplit(".", 1)[-1]
            for config_path in site.get("config_paths", []) or []:
                matching_fields = [
                    field_path
                    for field_path, value in flat.items()
                    if _token(value) == leaf
                    and (
                        field_path == config_path
                        or any(related(part, field)
                               for part in words(config_path)
                               for field in words(field_path))
                    )
                ]
                if len(matching_fields) == 1:
                    active.add(key)

    for anchor in anchors.values():
        keys = {str(getattr(anchor, "registered_as", "") or "")}
        keys.update(
            str(item.get("key") or "")
            for item in getattr(anchor, "block_metadata", {}).get("decorators", [])
            if isinstance(item, dict)
        )
        for key in keys - {""}:
            implicit_key = any(
                isinstance(item, dict)
                and str(item.get("key") or "") == key
                and item.get("implicit_key") is True
                for item in getattr(anchor, "block_metadata", {}).get("decorators", [])
            )
            if implicit_key and (key in mapping_paths or key in mapping_leaves):
                active.add(key)
                continue
            key_segments = key.lower().split(".")
            leaf = key_segments[-1] if key_segments else ""
            namespace = words(".".join(key_segments[:-1]))
            for field_path, value in flat.items():
                if _token(value) != leaf:
                    continue
                if not namespace and implicit_key:
                    active.add(key)
                    break
                field_words = words(field_path)
                if any(related(part, field) for part in namespace for field in field_words):
                    active.add(key)
                    break
    return active


__all__ = ["load_yaml_profile", "active_registered_keys", "yaml_component_graph"]
