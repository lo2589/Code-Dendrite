"""Conservative cross-language edges backed by explicit source evidence."""
from __future__ import annotations

import re
import posixpath
from pathlib import Path


_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
_PY_METHOD_ROUTE = re.compile(
    r"@(?:[A-Za-z_]\w*\.)*(get|post|put|patch|delete|options|head)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.I,
)
_PY_GENERIC_ROUTE = re.compile(
    r"@(?:[A-Za-z_]\w*\.)*route\s*\(\s*['\"]([^'\"]+)['\"](?P<tail>[^)]*)\)",
    re.I,
)
_JS_ROUTE = re.compile(
    r"\b(?:app|router|server)\s*\.\s*(get|post|put|patch|delete|options|head)"
    r"\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*([A-Za-z_$][\w$]*)",
    re.I,
)
_AXIOS_CALL = re.compile(
    r"\baxios\s*\.\s*(get|post|put|patch|delete|options|head)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.I,
)
_FETCH_CALL = re.compile(r"\bfetch\s*\(\s*['\"]([^'\"]+)['\"]", re.I)
_TAURI_INVOKE = re.compile(r"\binvoke\s*\(\s*['\"]([^'\"]+)['\"]")
_TAURI_GENERATE_HANDLER = re.compile(r"\btauri::generate_handler!\s*\[([^\]]*)\]", re.S)


def _path(value: str) -> str:
    value = value.split("?", 1)[0].strip()
    if not value.startswith("/") or "${" in value:
        return ""
    return re.sub(r"/{2,}", "/", value.rstrip("/") or "/")


def _anchor_for_line(by_file: dict[str, list], file: str, line: int):
    candidates = [
        anchor for anchor in by_file.get(file, [])
        if anchor.symbol_type != "class"
        and anchor.line_start <= line <= max(anchor.line_start, anchor.line_end)
    ]
    if not candidates:
        candidates = [
            anchor for anchor in by_file.get(file, [])
            if anchor.symbol_type != "class" and anchor.line_start <= line
        ]
    return max(candidates, key=lambda item: item.line_start) if candidates else None


def _next_anchor(by_file: dict[str, list], file: str, line: int, distance: int = 8):
    candidates = [
        anchor for anchor in by_file.get(file, [])
        if anchor.symbol_type != "class" and line <= anchor.line_start <= line + distance
    ]
    return min(candidates, key=lambda item: item.line_start) if candidates else None


def _same_file_symbol(anchors: dict, file: str, name: str):
    direct = anchors.get(f"{file}::{name}")
    if direct:
        return direct
    candidates = [
        anchor for anchor in anchors.values()
        if anchor.file == file and anchor.symbol.rsplit(".", 1)[-1] == name
    ]
    return candidates[0] if len(candidates) == 1 else None


def _remove_old_bridge_sites(anchors: dict, bridge_kind: str) -> set[str]:
    touched = set()
    for anchor in anchors.values():
        sites = list(anchor.call_sites or [])
        removed_targets = {
            str(site.get("target") or "") for site in sites
            if isinstance(site, dict) and site.get("bridge_kind") == bridge_kind
        }
        kept_sites = [
            site for site in sites
            if not isinstance(site, dict) or site.get("bridge_kind") != bridge_kind
        ]
        if len(kept_sites) != len(sites):
            anchor.call_sites = kept_sites
            anchor.callees = [
                callee for callee in (anchor.callees or [])
                if str(callee.get("target", callee) if isinstance(callee, dict) else callee)
                not in removed_targets
            ]
            touched.add(anchor.id)
    return touched


def _remove_old_http_sites(anchors: dict) -> set[str]:
    return _remove_old_bridge_sites(anchors, "http")


def _add_bridge(caller, target, *, line: int, column: int, kind: str,
                evidence: str, raw_target: str) -> bool:
    if caller is None or target is None or caller.id == target.id:
        return False
    if any(
        isinstance(site, dict)
        and site.get("bridge_kind") == kind
        and site.get("target") == target.id
        for site in (caller.call_sites or [])
    ):
        return False
    caller.callees.append(target.id)
    caller.call_sites.append({
        "target": target.id, "raw_target": raw_target,
        "line": line, "column": column,
        "seq": len(caller.call_sites or []), "conds": ["nocond"],
        "call_kind": "bridge", "bridge_kind": kind,
        "resolution": "exact", "evidence": evidence,
    })
    return True


def apply_http_bridges(root: str | Path, anchors: dict) -> set[str]:
    """Connect literal HTTP clients to literal server routes across languages.

    Only method+path exact matches become edges. Dynamic URLs are deliberately
    left unresolved instead of inventing a cross-language relationship.
    """
    root_path = Path(root)
    touched = _remove_old_http_sites(anchors)
    by_file: dict[str, list] = {}
    for anchor in anchors.values():
        if not anchor.is_virtual:
            by_file.setdefault(anchor.file, []).append(anchor)
    for values in by_file.values():
        values.sort(key=lambda item: (item.line_start, item.line_end))

    sources: dict[str, str] = {}
    for file in by_file:
        path = root_path / file
        if path.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}:
            continue
        try:
            sources[file] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

    routes: dict[tuple[str, str], list] = {}
    for file, source in sources.items():
        for match in _PY_METHOD_ROUTE.finditer(source):
            target = _next_anchor(by_file, file, source.count("\n", 0, match.start()) + 1)
            path = _path(match.group(2))
            if target and path:
                routes.setdefault((match.group(1).upper(), path), []).append(target)
        for match in _PY_GENERIC_ROUTE.finditer(source):
            path = _path(match.group(1))
            methods = re.findall(r"['\"]([A-Za-z]+)['\"]", match.group("tail")) or ["GET"]
            target = _next_anchor(by_file, file, source.count("\n", 0, match.start()) + 1)
            for method in methods:
                if target and path and method.upper() in _HTTP_METHODS:
                    routes.setdefault((method.upper(), path), []).append(target)
        for match in _JS_ROUTE.finditer(source):
            path = _path(match.group(2))
            target = _same_file_symbol(anchors, file, match.group(3))
            if target and path:
                routes.setdefault((match.group(1).upper(), path), []).append(target)

    for file, source in sources.items():
        calls = []
        for match in _AXIOS_CALL.finditer(source):
            calls.append((match, match.group(1).upper(), _path(match.group(2))))
        for match in _FETCH_CALL.finditer(source):
            tail = source[match.end():match.end() + 300]
            method_match = re.search(r"\bmethod\s*:\s*['\"]([A-Za-z]+)['\"]", tail, re.I)
            calls.append((match, method_match.group(1).upper() if method_match else "GET", _path(match.group(1))))
        for match, method, path in calls:
            targets = routes.get((method, path), [])
            if len(targets) != 1:
                continue
            line = source.count("\n", 0, match.start()) + 1
            caller = _anchor_for_line(by_file, file, line)
            target = targets[0]
            if caller is None or caller.id == target.id:
                continue
            if _add_bridge(
                caller, target, line=line,
                column=match.start() - source.rfind("\n", 0, match.start()) - 1,
                kind="http", evidence="literal-http-method-path",
                raw_target=f"{method} {path}",
            ):
                touched.add(caller.id)
    return touched


_JS_STRING_CONST = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(['\"])(.*?)\2\s*;?"
)
_JS_ROUTE_OBJECT = re.compile(
    r"\bpath\s*:\s*(?P<path>[^,\n]+)\s*,\s*handler\s*:\s*(?:async\s+)?(?:function\s*)?\(",
    re.M,
)


def _js_constants(source: str) -> dict[str, str]:
    return {match.group(1): match.group(3) for match in _JS_STRING_CONST.finditer(source)}


def _js_static_path(expr: str, constants: dict[str, str], factories=None) -> str:
    """Evaluate the static URL prefix of a small JS concatenation expression."""
    factories = factories or {}
    expr = expr.strip()
    called = re.match(r"([A-Za-z_$][\w$]*)\s*\(", expr)
    if called and called.group(1) in factories:
        return factories[called.group(1)]
    parts = []
    for token in re.finditer(r"(['\"])(.*?)\1|\b([A-Za-z_$][\w$]*)\b|\+", expr):
        literal, name = token.group(2), token.group(3)
        if literal is not None:
            parts.append(literal)
        elif name is not None:
            if name not in constants:
                break
            parts.append(constants[name])
    return _path("".join(parts))


def _balanced_argument(source: str, opening: int) -> str:
    depth = 0
    quote = ""
    escaped = False
    start = opening + 1
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"', '`'}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[start:index]
    return source[start:]


def _js_route_factories(source: str, anchors_for_file: list, constants: dict[str, str]) -> dict[str, str]:
    factories = {}
    lines = source.splitlines(keepends=True)
    for anchor in anchors_for_file:
        if anchor.symbol_type == "class":
            continue
        lo = max(0, anchor.line_start - 1)
        hi = max(lo + 1, anchor.line_end)
        body = "".join(lines[lo:hi])
        returned = re.search(r"\breturn\s+([^;\n]+)", body)
        if not returned:
            continue
        path = _js_static_path(returned.group(1), constants)
        if path:
            factories[anchor.symbol.rsplit(".", 1)[-1]] = path
    return factories


def apply_js_http_bridges(root: str | Path, anchors: dict) -> set[str]:
    """Connect JS URL helpers/wrappers to object-style registered routes."""
    root_path = Path(root)
    touched = _remove_old_bridge_sites(anchors, "js-http")
    by_file: dict[str, list] = {}
    for anchor in anchors.values():
        if not anchor.is_virtual:
            by_file.setdefault(anchor.file, []).append(anchor)
    sources = {}
    for file, values in by_file.items():
        values.sort(key=lambda item: (item.line_start, item.line_end))
        if Path(file).suffix.lower() not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            continue
        try:
            sources[file] = (root_path / file).read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

    routes: dict[str, list] = {}
    file_meta = {}
    for file, source in sources.items():
        constants = _js_constants(source)
        factories = _js_route_factories(source, by_file[file], constants)
        file_meta[file] = (constants, factories)
        for match in _JS_ROUTE_OBJECT.finditer(source):
            path = _js_static_path(match.group("path"), constants, factories)
            # Use the handler token, not the preceding path property, so the
            # innermost callback Anchor wins over its enclosing apply().
            line = source.count("\n", 0, match.end()) + 1
            target = _anchor_for_line(by_file, file, line)
            if path and target:
                routes.setdefault(path, []).append(target)

    # A local wrapper counts as HTTP only when its own body contains fetch().
    wrappers = set()
    for file, source in sources.items():
        lines = source.splitlines(keepends=True)
        for anchor in by_file[file]:
            lo, hi = max(0, anchor.line_start - 1), max(anchor.line_start, anchor.line_end)
            if re.search(r"\bfetch\s*\(", "".join(lines[lo:hi])):
                wrappers.add(anchor.symbol.rsplit(".", 1)[-1])
    wrappers.add("fetch")

    for file, source in sources.items():
        constants, factories = file_meta[file]
        for wrapper in wrappers:
            for match in re.finditer(r"\b" + re.escape(wrapper) + r"\s*\(", source):
                expr = _balanced_argument(source, source.find("(", match.start(), match.end()))
                path = _js_static_path(expr, constants, factories)
                targets = routes.get(path, [])
                if len(targets) != 1:
                    continue
                line = source.count("\n", 0, match.start()) + 1
                caller = _anchor_for_line(by_file, file, line)
                if _add_bridge(
                    caller, targets[0], line=line,
                    column=match.start() - source.rfind("\n", 0, match.start()) - 1,
                    kind="js-http", evidence="static-js-url-to-registered-route",
                    raw_target="GET " + path,
                ):
                    touched.add(caller.id)
    return touched


def _worker_constant_paths(file: str, source: str) -> dict[str, str]:
    values = {}
    for match in re.finditer(
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*[^\n;]*(?:resolve|join)\s*\(([^\n;]+)\)",
        source,
    ):
        literals = re.findall(r"['\"]([^'\"]+)['\"]", match.group(2))
        if not literals or not literals[-1].endswith((".js", ".mjs", ".cjs", ".ts")):
            continue
        values[match.group(1)] = posixpath.normpath(
            posixpath.join(posixpath.dirname(file), *literals)
        )
    return values


def apply_js_worker_bridges(root: str | Path, anchors: dict) -> set[str]:
    """Connect Worker.postMessage with its message callbacks in both directions."""
    root_path = Path(root)
    touched = _remove_old_bridge_sites(anchors, "worker-message")
    by_file: dict[str, list] = {}
    for anchor in anchors.values():
        if not anchor.is_virtual:
            by_file.setdefault(anchor.file, []).append(anchor)
    sources = {}
    for file, values in by_file.items():
        values.sort(key=lambda item: (item.line_start, item.line_end))
        if Path(file).suffix.lower() not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            continue
        try:
            sources[file] = (root_path / file).read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass

    for host_file, host_source in sources.items():
        constants = _worker_constant_paths(host_file, host_source)
        for create in re.finditer(
            r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+Worker\s*\(([^)]*)\)",
            host_source,
        ):
            variable, expr = create.group(1), create.group(2)
            names = re.findall(r"\b[A-Za-z_$][\w$]*\b", expr)
            target_file = next((constants[name] for name in names if name in constants), "")
            worker_source = sources.get(target_file)
            if not worker_source:
                continue
            incoming = re.search(r"\bparentPort\s*\.\s*on\s*\(\s*['\"]message['\"]", worker_source)
            outgoing = re.search(
                r"\b" + re.escape(variable) + r"\s*\.\s*on\s*\(\s*['\"]message['\"]",
                host_source,
            )
            worker_handler = _anchor_for_line(
                by_file, target_file,
                worker_source.count("\n", 0, incoming.start()) + 1,
            ) if incoming else None
            host_handler = _anchor_for_line(
                by_file, host_file,
                host_source.count("\n", 0, outgoing.start()) + 1,
            ) if outgoing else None
            for sent in re.finditer(r"\b" + re.escape(variable) + r"\s*\.\s*postMessage\s*\(", host_source):
                line = host_source.count("\n", 0, sent.start()) + 1
                caller = _anchor_for_line(by_file, host_file, line)
                if _add_bridge(
                    caller, worker_handler, line=line,
                    column=sent.start() - host_source.rfind("\n", 0, sent.start()) - 1,
                    kind="worker-message", evidence="worker-instance-postMessage",
                    raw_target=f"{variable}.postMessage -> {target_file}",
                ):
                    touched.add(caller.id)
            if host_handler and worker_handler:
                for sent in re.finditer(r"\bparentPort\s*\.\s*postMessage\s*\(", worker_source):
                    line = worker_source.count("\n", 0, sent.start()) + 1
                    caller = _anchor_for_line(by_file, target_file, line)
                    if _add_bridge(
                        caller, host_handler, line=line,
                        column=sent.start() - worker_source.rfind("\n", 0, sent.start()) - 1,
                        kind="worker-message", evidence="parentPort-postMessage",
                        raw_target=f"parentPort.postMessage -> {variable}.on(message)",
                    ):
                        touched.add(caller.id)
    return touched


def _tauri_command_targets(anchors: dict) -> dict[str, list]:
    commands: dict[str, list] = {}
    for anchor in anchors.values():
        if getattr(anchor, "language", "") != "rust":
            continue
        keys = set()
        if getattr(anchor, "registered_as", None):
            keys.add(str(anchor.registered_as))
        for item in getattr(anchor, "block_metadata", {}).get("decorators", []) or []:
            if (
                isinstance(item, dict)
                and item.get("name") == "tauri::command"
                and item.get("key")
            ):
                keys.add(str(item["key"]))
        for key in keys:
            commands.setdefault(key, []).append(anchor)
    return commands


def apply_tauri_bridges(root: str | Path, anchors: dict) -> set[str]:
    """Connect Tauri JS invoke literals and generate_handler registrations."""
    root_path = Path(root)
    touched = _remove_old_bridge_sites(anchors, "tauri-command")
    touched.update(_remove_old_bridge_sites(anchors, "tauri-command-registration"))
    commands = _tauri_command_targets(anchors)
    if not commands:
        return touched

    by_file: dict[str, list] = {}
    for anchor in anchors.values():
        if not anchor.is_virtual:
            by_file.setdefault(anchor.file, []).append(anchor)
    for values in by_file.values():
        values.sort(key=lambda item: (item.line_start, item.line_end))

    sources = {}
    for file in by_file:
        suffix = Path(file).suffix.lower()
        if suffix not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".rs"}:
            continue
        try:
            sources[file] = (root_path / file).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

    for file, source in sources.items():
        if Path(file).suffix.lower() not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            continue
        for match in _TAURI_INVOKE.finditer(source):
            targets = commands.get(match.group(1), [])
            if len(targets) != 1:
                continue
            line = source.count("\n", 0, match.start()) + 1
            caller = _anchor_for_line(by_file, file, line)
            if _add_bridge(
                caller,
                targets[0],
                line=line,
                column=match.start() - source.rfind("\n", 0, match.start()) - 1,
                kind="tauri-command",
                evidence="tauri-invoke-literal",
                raw_target=match.group(1),
            ):
                touched.add(caller.id)

    for file, source in sources.items():
        if Path(file).suffix.lower() != ".rs":
            continue
        for match in _TAURI_GENERATE_HANDLER.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            caller = _anchor_for_line(by_file, file, line)
            if caller is None:
                continue
            for name in re.findall(r"\b[A-Za-z_]\w*\b", match.group(1)):
                targets = commands.get(name, [])
                if len(targets) != 1:
                    continue
                if _add_bridge(
                    caller,
                    targets[0],
                    line=line,
                    column=match.start() - source.rfind("\n", 0, match.start()) - 1,
                    kind="tauri-command-registration",
                    evidence="tauri-generate-handler",
                    raw_target=name,
                ):
                    touched.add(caller.id)
    return touched


def apply_runtime_bridges(root: str | Path, anchors: dict) -> set[str]:
    touched = set()
    touched.update(apply_http_bridges(root, anchors))
    touched.update(apply_js_http_bridges(root, anchors))
    touched.update(apply_js_worker_bridges(root, anchors))
    touched.update(apply_tauri_bridges(root, anchors))
    return touched
