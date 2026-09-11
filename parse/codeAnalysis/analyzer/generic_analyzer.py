"""Dependency-free structural analyzers for the languages without a dedicated parser.

These adapters deliberately emit conservative function/class anchors.  Calls are
kept unresolved until the project-wide resolver can prove a unique target.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, List

from parse.codeAnalysis.analyzer.base import BaseAnalyzer, FunctionInfo, ModuleInfo


_CALL_EXCLUDES = {
    "if", "for", "foreach", "while", "switch", "catch", "return", "throw",
    "new", "sizeof", "typeof", "function", "class", "def", "func", "fn",
    "echo", "print", "printf", "println", "select", "from", "where", "values",
}


def _line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _matching_brace(source: str, opening: int) -> int:
    if opening < 0:
        return opening
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


def _calls(body: str, base_line: int) -> tuple[List[str], List[dict]]:
    names: List[str] = []
    sites: List[dict] = []
    pattern = re.compile(r"(?:(?P<receiver>[A-Za-z_$][\w$]*)\s*(?:\.|::|->)\s*)?(?P<name>[A-Za-z_$][\w$-]*)\s*\(")
    for seq, match in enumerate(pattern.finditer(body)):
        name = match.group("name")
        if name.lower() in _CALL_EXCLUDES:
            continue
        if name not in names:
            names.append(name)
        receiver = match.group("receiver") or ""
        sites.append({
            "target": name,
            "raw_target": name,
            "call_kind": "attribute" if receiver else "name",
            "receiver": receiver,
            "line": base_line + body.count("\n", 0, match.start()),
            "column": match.start() - body.rfind("\n", 0, match.start()) - 1,
            "seq": seq,
            "conds": ["nocond"],
            "resolution": "unresolved",
            "evidence": "source-call",
        })
    return names, sites


def _shell_calls(body: str, base_line: int) -> tuple[List[str], List[dict]]:
    """Extract shell command invocations without treating assignments as calls."""
    names: List[str] = []
    sites: List[dict] = []
    excluded = _CALL_EXCLUDES | {
        "then", "do", "done", "fi", "esac", "case", "in", "local",
        "declare", "export", "readonly", "unset", "shift", "break", "continue",
    }
    for line_offset, raw_line in enumerate(body.splitlines()):
        line = re.sub(r"#.*$", "", raw_line).strip()
        if not line:
            continue
        for fragment in re.split(r"(?:&&|\|\||;|\|)", line):
            fragment = fragment.strip()
            fragment = re.sub(r"^(?:if|then|elif|else|while|until|do)\s+", "", fragment)
            fragment = re.sub(r"^(?:[A-Za-z_]\w*=\S*\s+)+", "", fragment)
            match = re.match(r"(?:command\s+|builtin\s+)?([A-Za-z_][\w.-]*)\b", fragment)
            if not match:
                continue
            name = match.group(1)
            if name.lower() in excluded:
                continue
            if name not in names:
                names.append(name)
            sites.append({
                "target": name, "raw_target": name, "call_kind": "command",
                "receiver": "", "line": base_line + line_offset,
                "column": max(0, raw_line.find(name)), "seq": len(sites),
                "conds": ["nocond"], "resolution": "unresolved",
                "evidence": "shell-command",
            })
    return names, sites


class GenericLanguageAnalyzer(BaseAnalyzer):
    """Small structural parser used for C#, Scala, ObjC, shell and SQL families."""

    def __init__(self, root_path: str, language: str, extensions: Iterable[str]):
        super().__init__(root_path)
        self._language = language
        self._extensions = tuple(extensions)

    @property
    def language_name(self) -> str:
        return self._language

    def is_supported_file(self, file_path: str) -> bool:
        return os.path.splitext(file_path)[1].lower() in self._extensions

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
            source = handle.read()
        module = ModuleInfo(os.path.basename(file_path), file_path, 1)
        module.imports = self._imports(source)
        module.classes = self._classes(source)
        module.functions = self._functions(source, file_path, module.classes)
        return module

    def _imports(self, source: str) -> List[str]:
        patterns = {
            "csharp": r"^\s*using\s+([\w.]+)",
            "scala": r"^\s*import\s+([\w.{}_*]+)",
            "objective-c": r"^\s*#import\s+[<\"]([^>\"]+)",
            "shell": r"^\s*(?:source|\.)\s+([^\s;]+)",
            "powershell": r"^\s*(?:Import-Module|using\s+module)\s+([^\s;]+)",
        }
        pattern = patterns.get(self._language)
        return re.findall(pattern, source, re.MULTILINE) if pattern else []

    def _classes(self, source: str) -> List[str]:
        if self._language == "objective-c":
            return list(dict.fromkeys(
                name for _kind, name in re.findall(
                    r"@(interface|implementation)\s+([A-Za-z_]\w*)", source,
                )
            ))
        names = re.findall(r"\b(?:class|struct|interface|trait|object|enum)\s+([A-Za-z_]\w*)", source)
        return list(dict.fromkeys(names))

    def _functions(self, source: str, file_path: str, classes: List[str]) -> List[FunctionInfo]:
        if self._language == "shell":
            patterns = [r"(?m)^\s*(?:function\s+)?([A-Za-z_][\w-]*)\s*(?:\(\s*\))?\s*\{"]
        elif self._language == "powershell":
            patterns = [r"(?im)^\s*function\s+([A-Za-z_][\w-]*)\s*(?:\([^)]*\))?\s*\{"]
        elif self._language == "scala":
            patterns = [r"\bdef\s+([A-Za-z_]\w*)\s*(?:\[[^]]*\])?\s*\([^)]*\)[^{=]*(?:=\s*)?\{"]
        elif self._language == "objective-c":
            patterns = [r"(?m)^\s*[-+]\s*\([^)]*\)\s*([A-Za-z_]\w*)[^;{]*\{"]
        elif self._language == "sql":
            patterns = [r"(?is)\bcreate\s+(?:or\s+replace\s+)?(?:function|procedure)\s+([\w.]+)[^;]*?\bbegin\b"]
        else:  # C# and compatible brace languages
            patterns = [
                r"(?:(?:public|private|protected|internal|static|virtual|override|async|sealed|partial|extern|unsafe|new)\s+)*(?:[\w<>,.?\[\]]+\s+)+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
            ]
        functions: List[FunctionInfo] = []
        seen = set()
        for pattern in patterns:
            for match in re.finditer(pattern, source):
                name = match.group(1)
                if name.lower() in _CALL_EXCLUDES or (name, match.start()) in seen:
                    continue
                seen.add((name, match.start()))
                opening = source.find("{", match.start(), match.end() + 1)
                closing = _matching_brace(source, opening)
                start_line = _line(source, match.start())
                end_line = _line(source, closing)
                body = source[opening + 1:closing] if opening >= 0 else ""
                if self._language in {"shell", "powershell"}:
                    calls, sites = _shell_calls(body, _line(source, opening + 1))
                else:
                    calls, sites = _calls(body, _line(source, opening + 1))
                owner = self._owner_for_offset(source, classes, match.start())
                functions.append(FunctionInfo(
                    name=name,
                    file_path=file_path,
                    line_number=start_line,
                    line_end=end_line,
                    calls=calls,
                    call_sites=sites,
                    is_method=bool(owner),
                    class_name=owner,
                ))
        return functions

    @staticmethod
    def _owner_for_offset(source: str, classes: List[str], offset: int) -> str | None:
        owner = None
        owner_pos = -1
        for name in classes:
            match = re.search(r"\b(?:class|struct|interface|trait|object|implementation)\s+" + re.escape(name) + r"\b", source)
            if match and owner_pos < match.start() < offset:
                opening = source.find("{", match.end())
                if opening >= 0 and offset <= _matching_brace(source, opening):
                    owner, owner_pos = name, match.start()
        return owner
