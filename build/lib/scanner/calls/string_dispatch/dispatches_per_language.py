"""
dispatches_per_language.py — JS/Go/Java/Kotlin dispatch 提取
=============================================================

Python AST 之外的字符串路由 dispatch 边提取：
- JavaScript / TypeScript：switch/case、对象字面量 dispatch
- Go：switch/case、http.HandleFunc 路由
- Java：switch/case、@RequestMapping 类注解 dispatcher
- Kotlin：when、object expression

这是 proposal 性质的实现：覆盖最常见的字符串路由模式，不做完整语义分析。
每个提取器抛异常都返回 []，不破坏现有调用流程。
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List


# js/ts 常见的 dispatch 模式
# 例：
#   switch (action) {
#     case "foo": return this.foo();
#     case "bar": this.bar();
#   }
#   const handlers = { foo: this.foo, bar: this.bar };
#   handlers[action]?.();
_JS_SWITCH_RE = re.compile(
    r"""switch\s*\(\s*(?P<key>[A-Za-z_$][\w$.]*)\s*\)\s*\{""",
    re.MULTILINE,
)
_JS_CASE_RE = re.compile(
    r"""case\s+["'](?P<value>[^"']+)["']\s*:\s*(?P<body>[^;{}]+(?:[{}][^;{}]*)*)[;}]""",
    re.MULTILINE,
)
# dispatch via object literal
_JS_OBJ_DISPATCH_RE = re.compile(
    r"""const\s+(?P<varname>[A-Za-z_$][\w$]*)\s*=\s*\{([^}]+)\}""",
    re.MULTILINE,
)
_JS_OBJ_KEY_RE = re.compile(
    r"""["'](?P<key>[^"']+)["']\s*:\s*(?P<callee>[A-Za-z_$][\w$.]*)""",
)


def extract_dispatches_from_js(source: str, file_path: str) -> List[Dict]:
    """Extract dispatch edges from JavaScript / TypeScript source.

    Patterns covered:
      - switch (key) { case "v": handler(); }
      - const handlers = { "v": handler };

    Both produce edges of the form:
      file_path::<enclosing_function> --[dispatch key=v]--> handler
    """
    edges: List[Dict] = []
    # find enclosing function for each match by tracking { depth and function keywords
    # naive: split by function declarations
    func_re = re.compile(
        r"""(?:function\s+(?P<fname>[A-Za-z_$][\w$]*)\s*\([^)]*\)|(?P<fname2>[A-Za-z_$][\w$]*)\s*\([^)]*\)\s*=>|const\s+(?P<fname3>[A-Za-z_$][\w$]*)\s*=\s*\([^)]*\)\s*=>)\s*\{""",
        re.MULTILINE,
    )
    chunks: List[tuple] = []  # (func_name, body_start, body_end)
    matches = list(func_re.finditer(source))
    for i, m in enumerate(matches):
        name = m.group("fname") or m.group("fname2") or m.group("fname3") or "<anonymous>"
        start = m.end()
        depth = 1
        end = start
        for idx in range(start, len(source)):
            c = source[idx]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        chunks.append((name, start, end))
    if not chunks:
        chunks = [("<module>", 0, len(source))]

    # switch dispatch
    for func_name, s, e in chunks:
        body = source[s:e]
        for sw in _JS_SWITCH_RE.finditer(body):
            key = sw.group("key")
            # search case statements inside the switch body
            inner = body[sw.end():]
            for case in _JS_CASE_RE.finditer(inner):
                value = case.group("value")
                callee_body = case.group("body")
                # Strip leading braces/whitespace; case bodies often
                # start with `{ return foo(); }` so we need to skip past
                # the opening brace to reach the actual call expression.
                callee_body_stripped = re.sub(r"^\s*\{?\s*", "", callee_body)
                callee_match = re.search(r"\b([A-Za-z_$][\w$.]*)\s*\(", callee_body_stripped)
                if not callee_match:
                    continue
                callee = callee_match.group(1)
                edges.append(_per_lang_dispatch_edge(
                    file_path=file_path, func=func_name, key=key, value=value,
                    callee=callee, language="javascript",
                ))
    # object literal dispatch
    for func_name, s, e in chunks:
        body = source[s:e + 1]
        for obj in _JS_OBJ_DISPATCH_RE.finditer(body):
            obj_body = obj.group(2)
            for k in _JS_OBJ_KEY_RE.finditer(obj_body):
                key = k.group("key")
                callee = k.group("callee")
                edges.append(_per_lang_dispatch_edge(
                    file_path=file_path, func=func_name, key=key, value=key,
                    callee=callee, language="javascript",
                ))
    return edges


# Go switch/case + http.HandleFunc
_GO_SWITCH_RE = re.compile(
    r"""switch\s+(?P<key>[A-Za-z_][\w.]*)\s*\{""",
    re.MULTILINE,
)
_GO_CASE_RE = re.compile(
    r"""case\s+["'](?P<value>[^"']+)["']\s*:\s*(?P<body>[^\}]+?)(?=case\s+|default\s+|\})""",
    re.MULTILINE | re.DOTALL,
)
_GO_HANDLE_RE = re.compile(
    r"""(?P<qualifier>(?:http\.HandleFunc|http\.Handle|router\.HandleFunc|\w+\.HandleFunc|\w+\.Handle))\s*\(\s*["'](?P<path>[^"']+)["']\s*,\s*(?P<handler>[A-Za-z_][\w.]*)""",
)


def extract_dispatches_from_go(source: str, file_path: str) -> List[Dict]:
    edges: List[Dict] = []
    func_re = re.compile(
        r"""func\s+(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][\w]*)\s*\([^)]*\)(?:\s*\([^)]*\))?\s*\{"""
    )
    chunks: List[tuple] = []
    matches = list(func_re.finditer(source))
    for i, m in enumerate(matches):
        name = m.group("name")
        start = m.end()
        depth = 1
        end = start
        for idx in range(start, len(source)):
            c = source[idx]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        chunks.append((name, start, end))
    if not chunks:
        chunks = [("<package>", 0, len(source))]

    for func_name, s, e in chunks:
        body = source[s:e]
        for sw in _GO_SWITCH_RE.finditer(body):
            key = sw.group("key")
            inner = body[sw.end():]
            for case in _GO_CASE_RE.finditer(inner):
                value = case.group("value")
                callee_body = case.group("body")
                # Skip leading braces/whitespace; case bodies may begin
                # with `{ return foo(); }` etc.
                callee_body_stripped = re.sub(r"^\s*\{?\s*", "", callee_body)
                callee_match = re.search(r"([A-Za-z_][\w.]*)\s*\(", callee_body_stripped)
                if not callee_match:
                    continue
                callee = callee_match.group(1)
                edges.append(_per_lang_dispatch_edge(
                    file_path=file_path, func=func_name, key=key, value=value,
                    callee=callee, language="go",
                ))
    # http.HandleFunc(\"...\", handler) — top-level package dispatch
    for h in _GO_HANDLE_RE.finditer(source):
        path = h.group("path")
        handler = h.group("handler")
        edges.append(_per_lang_dispatch_edge(
            file_path=file_path, func="<route>", key="path", value=path,
            callee=handler, language="go",
        ))
    return edges


# Java @RequestMapping + switch
_JAVA_SWITCH_RE = re.compile(
    r"""switch\s*\(\s*(?P<key>[A-Za-z_][\w.]*)\s*\)\s*\{""",
)
_JAVA_CASE_RE = re.compile(
    r"""case\s+["'](?P<value>[^"']+)["']\s*:\s*(?P<body>[^;]+);""",
)
_JAVA_REQUEST_RE = re.compile(
    r"""@(?:GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*\(\s*(?:value\s*=\s*)?["'](?P<path>[^"']+)["']""",
)
_JAVA_REQUEST_CLASS_RE = re.compile(
    r"""@RequestMapping\s*\(\s*["'](?P<base>[^"']+)["']""",
)


def extract_dispatches_from_java(source: str, file_path: str) -> List[Dict]:
    edges: List[Dict] = []
    # class-level @RequestMapping base path — used as prefix for method paths
    base_match = _JAVA_REQUEST_CLASS_RE.search(source)
    base = base_match.group("base") if base_match else ""

    method_re = re.compile(
        r"""(?:public|private|protected)?\s*(?:static\s+)?[\w<>,\[\]\s]+\s+(?P<name>[A-Za-z_][\w]*)\s*\([^)]*\)\s*\{""",
        re.MULTILINE,
    )
    chunks: List[tuple] = []
    matches = list(method_re.finditer(source))
    for i, m in enumerate(matches):
        name = m.group("name")
        start = m.end()
        depth = 1
        end = start
        for idx in range(start, len(source)):
            c = source[idx]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        chunks.append((name, start, end))

    # switch dispatch
    for method_name, s, e in chunks:
        body = source[s:e]
        for sw in _JAVA_SWITCH_RE.finditer(body):
            key = sw.group("key")
            inner = body[sw.end():]
            for case in _JAVA_CASE_RE.finditer(inner):
                value = case.group("value")
                callee_body = case.group("body")
                callee_body_stripped = re.sub(r"^\s*\{?\s*", "", callee_body)
                callee_match = re.search(r"([A-Za-z_][\w.]*)\s*\(", callee_body_stripped)
                if not callee_match:
                    continue
                callee = callee_match.group(1)
                edges.append(_per_lang_dispatch_edge(
                    file_path=file_path, func=method_name, key=key, value=value,
                    callee=callee, language="java",
                ))
    # @RequestMapping style — extract method-level paths
    for m in _JAVA_REQUEST_RE.finditer(source):
        path = m.group("path")
        # find next method name
        tail = source[m.end():]
        nm = re.search(r"(?:public|private|protected)?\s*(?:static\s+)?[\w<>,\[\]\s]+\s+([A-Za-z_][\w]*)\s*\(", tail)
        if not nm:
            continue
        method_name = nm.group(1)
        full_path = base + path if base else path
        edges.append(_per_lang_dispatch_edge(
            file_path=file_path, func="<route>", key="path", value=full_path,
            callee=method_name, language="java",
        ))
    return edges


# Kotlin when expression
_KOTLIN_WHEN_RE = re.compile(
    r"""when\s*\(\s*(?P<key>[A-Za-z_][\w.]*)\s*\)\s*\{""",
)
_KOTLIN_WHEN_BRANCH_RE = re.compile(
    r"""["'](?P<value>[^"']+)["']\s*->\s*(?P<body>[^\n]+)""",
)


def extract_dispatches_from_kotlin(source: str, file_path: str) -> List[Dict]:
    edges: List[Dict] = []
    func_re = re.compile(
        r"""fun\s+(?P<name>[A-Za-z_][\w]*)\s*\([^)]*\)(?:\s*:\s*[^{]+)?\s*\{""",
        re.MULTILINE,
    )
    chunks: List[tuple] = []
    matches = list(func_re.finditer(source))
    for i, m in enumerate(matches):
        name = m.group("name")
        start = m.end()
        depth = 1
        end = start
        for idx in range(start, len(source)):
            c = source[idx]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        chunks.append((name, start, end))
    if not chunks:
        chunks = [("<module>", 0, len(source))]

    for func_name, s, e in chunks:
        body = source[s:e]
        for w in _KOTLIN_WHEN_RE.finditer(body):
            key = w.group("key")
            inner = body[w.end():]
            for branch in _KOTLIN_WHEN_BRANCH_RE.finditer(inner):
                value = branch.group("value")
                callee_body = branch.group("body")
                callee_body_stripped = re.sub(r"^\s*\{?\s*", "", callee_body)
                callee_match = re.search(r"([A-Za-z_][\w.]*)\s*\(", callee_body_stripped)
                if not callee_match:
                    continue
                callee = callee_match.group(1)
                edges.append(_per_lang_dispatch_edge(
                    file_path=file_path, func=func_name, key=key, value=value,
                    callee=callee, language="kotlin",
                ))
    return edges


def _per_lang_dispatch_edge(
    *, file_path: str, func: str, key: str, value: str,
    callee: str, language: str,
) -> Dict:
    """Build a dispatch edge dict in the same shape as the Python path.

    The caller in generate_relations.py reads `from_id`, `to_id`,
    `dispatch_key`, `dispatch_value`, `condition`. We populate them
    with the language-specific best-effort IDs and let project-wide
    resolve upgrade `to_id` later if the target anchor exists.
    """
    # Strip receiver prefix (this., self., obj.) so the to_id matches
    # the way cdd indexes the actual method name. cdd sees `this.foo`
    # as the method `foo` of the enclosing class — the receiver is
    # implicit. We don't know the class name from regex alone, so
    # leave the bare method name; project-wide resolve will pick up
    # any matching `<class>.method` anchor.
    bare = callee
    for prefix in ("this.", "self."):
        if bare.startswith(prefix):
            bare = bare[len(prefix):]
            break
    func_id = f"{file_path}::{func}"
    return {
        "from_id": func_id,
        "to_id": f"{file_path}::{bare}",
        "edge_type": "dispatch",
        "data_in": "string route",
        "data_out": "conditional call",
        "condition": f"{key} == {value!r}",
        "dispatch_key": key,
        "dispatch_value": value,
        "is_conditional": True,
        "language": language,
    }


# 入口分派表
_EXTRACTORS: Dict[str, Callable[[str, str], List[Dict]]] = {
    ".js": extract_dispatches_from_js,
    ".jsx": extract_dispatches_from_js,
    ".ts": extract_dispatches_from_js,
    ".tsx": extract_dispatches_from_js,
    ".go": extract_dispatches_from_go,
    ".java": extract_dispatches_from_java,
    ".kt": extract_dispatches_from_kotlin,
    ".kts": extract_dispatches_from_kotlin,
}


def extract_dispatches_for_path(file_path: str, root: str) -> List[Dict]:
    """Dispatch to the right language extractor based on file suffix.

    Returns [] on any error (file unreadable, regex mismatch, etc.)
    so the caller can treat this as best-effort.
    """
    import os
    from pathlib import Path

    fp = Path(file_path)
    ext = fp.suffix.lower()
    fn = _EXTRACTORS.get(ext)
    if fn is None:
        return []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
    except OSError:
        return []
    rel_path = os.path.relpath(file_path, root).replace("\\", "/")
    try:
        return fn(source, rel_path)
    except Exception:
        # best-effort: any regex / parse error -> no edges
        return []
