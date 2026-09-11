"""Language-neutral single-file control-flow overlay dispatch."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from base.shared.types import Anchor


_CONTROL = re.compile(
    r"\b(?P<kind>if|else\s+if|switch|match|when|for|foreach|while|do|try|catch)\b"
    r"(?P<expr>[^\n{;]*)\{",
    re.I,
)
_CALL = re.compile(r"(?:(?:[A-Za-z_$][\w$]*)\s*(?:\.|::|->)\s*)?([A-Za-z_$][\w$-]*)\s*\(")
_NOISE = {"if", "for", "foreach", "while", "switch", "match", "when", "catch", "return", "new"}


def _brace_end(source: str, opening: int) -> int:
    depth = 0
    quote = ""
    escaped = False
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
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(source) - 1


def _line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _generic_control_flow(root: Path, rel: str, source: str) -> dict[str, Anchor]:
    from parse.languages.pipeline import parse_paths

    parsed, _failures, _completed = parse_paths(root, [root / rel])
    functions = sorted(
        (item for item in parsed.values() if item.symbol_type in {"function", "method"}),
        key=lambda item: (item.line_start, item.id),
    )
    if not functions:
        return {}
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    result: dict[str, Anchor] = {}
    ranges: list[tuple[int, int, str]] = []
    for index, function in enumerate(functions):
        start_line = max(1, function.line_start)
        inferred_end = functions[index + 1].line_start - 1 if index + 1 < len(functions) else len(lines)
        end_line = function.line_end if function.line_end > start_line else inferred_end
        begin = offsets[min(start_line - 1, len(offsets) - 1)]
        finish = offsets[min(max(start_line, end_line), len(offsets) - 1)]
        fragment = source[begin:finish]
        for ordinal, match in enumerate(_CONTROL.finditer(fragment), 1):
            opening = begin + match.end() - 1
            closing = _brace_end(source, opening)
            if closing >= finish:
                closing = finish - 1
            line_start = _line(source, begin + match.start())
            line_end = _line(source, max(opening, closing))
            raw_kind = re.sub(r"\s+", " ", match.group("kind").lower())
            kind = "loop" if raw_kind in {"for", "foreach", "while", "do"} else "try" if raw_kind in {"try", "catch"} else "condition"
            owner = function.id
            containing = [entry for entry in ranges if entry[0] <= opening <= entry[1]]
            if containing:
                owner = min(containing, key=lambda entry: entry[1] - entry[0])[2]
            anchor_id = f"{function.id}#{kind}:{line_start}:{ordinal}"
            expr = " ".join(match.group("expr").strip().split())
            metadata = {"keyword": raw_kind, "expr": expr}
            if kind == "condition":
                metadata["cases"] = [{"scope_label": "body", "condition": expr or raw_kind}]
            elif kind == "loop":
                metadata["loop_kind"] = raw_kind
            body = source[opening + 1:closing]
            sites = []
            for seq, call in enumerate(_CALL.finditer(body)):
                target = call.group(1)
                if target.lower() in _NOISE:
                    continue
                sites.append({
                    "target": target, "raw_target": target,
                    "line": _line(source, opening + 1 + call.start()),
                    "column": 0, "seq": seq, "conds": [expr or "nocond"],
                    "resolution": "unresolved", "evidence": "control-flow-call",
                })
            digest = hashlib.sha1(f"{anchor_id}:{line_end}:{expr}".encode()).hexdigest()[:12]
            result[anchor_id] = Anchor(
                id=anchor_id, symbol=f"{kind}_block_{ordinal}", file=rel,
                line_start=line_start, line_end=line_end, hash=digest,
                language=function.language, symbol_type="virtual_block",
                is_virtual=True, virtual_kind=kind, parent_anchor=owner,
                scope_label="body", block_metadata=metadata,
                callees=[site["target"] for site in sites], call_sites=sites,
            )
            ranges.append((opening, closing, anchor_id))
    return result


def extract_file_control_flow(root: str | Path, rel_path: str, source: str | None = None) -> dict[str, Anchor]:
    root_path = Path(root).resolve()
    rel = str(rel_path).replace("\\", "/")
    path = (root_path / rel).resolve()
    if source is None:
        source = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".py", ".pyw"}:
        from index.api.control_flow_blocks import _ControlFlowBlockExtractor
        return _ControlFlowBlockExtractor(root_path, rel, source).extract()
    return _generic_control_flow(root_path, rel, source)


__all__ = ["extract_file_control_flow"]
