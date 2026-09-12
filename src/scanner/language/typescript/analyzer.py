"""
TypeScript/JavaScript 代码分析器
增强版：支持 UI 事件提取和数据流分析
"""
import os
import re
from dataclasses import dataclass
from typing import List, Set, Optional, Dict
from scanner.language.base import BaseAnalyzer, FunctionInfo, ModuleInfo, ProjectInfo


_JS_WORD_EXCLUDES = {
    'if', 'for', 'while', 'switch', 'catch', 'class', 'function',
    'constructor', 'return', 'throw', 'new', 'typeof', 'instanceof',
    'delete', 'void', 'await', 'else', 'case', 'default', 'break',
    'continue', 'yield', 'var', 'let', 'const', 'import', 'export',
}


def _line_at(source: str, offset: int) -> int:
    return source.count('\n', 0, max(0, offset)) + 1


def _mask_non_code(source: str) -> str:
    """Blank comments, strings, templates and regex literals, preserving lines."""
    chars = list(source)
    out = list(source)
    state = 'code'
    quote = ''
    escaped = False
    regex_class = False
    previous_code = ''
    index = 0
    while index < len(chars):
        char = chars[index]
        nxt = chars[index + 1] if index + 1 < len(chars) else ''
        if state == 'code':
            if char == '/' and nxt == '/':
                out[index] = out[index + 1] = ' '
                state = 'line-comment'; index += 2; continue
            if char == '/' and nxt == '*':
                out[index] = out[index + 1] = ' '
                state = 'block-comment'; index += 2; continue
            if char in {'\'', '"', '`'}:
                quote = char; out[index] = ' '; state = 'string'; escaped = False
                index += 1; continue
            if char == '/' and previous_code in {'', '=', '(', '[', '{', ',', ':', ';', '!', '&', '|', '?'}:
                out[index] = ' '; state = 'regex'; escaped = False; regex_class = False
                index += 1; continue
            if not char.isspace():
                previous_code = char
            index += 1; continue
        if char != '\n':
            out[index] = ' '
        if state == 'line-comment':
            if char == '\n': state = 'code'
        elif state == 'block-comment':
            if char == '*' and nxt == '/':
                out[index] = out[index + 1] = ' '; index += 1; state = 'code'
        elif state == 'string':
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                state = 'code'
        elif state == 'regex':
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '[':
                regex_class = True
            elif char == ']':
                regex_class = False
            elif char == '/' and not regex_class:
                state = 'code'
        index += 1
    return ''.join(out)


def _matching_brace(masked: str, opening: int) -> int:
    if opening < 0:
        return opening
    depth = 0
    for index in range(opening, len(masked)):
        char = masked[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return index
    return len(masked) - 1


# A return type may itself be an object literal, and the tail after it is still
# type syntax. Only an inline tail counts: a newline before the next brace means
# the declaration is over and the brace belongs to something else entirely.
# Worth 16 of the 1205 symbols in a 200-file sample and 20 of the empty call
# sets — measured, after an A/B run that appeared to show it worth nothing
# turned out to have patched a different copy of this module.
_TYPE_TAIL = ' \t|&[],<>.?'
_TYPE_TAIL_MAX = 40


def _skip_type_object(masked: str, opening: int) -> int:
    """Step past an object literal that is a return type, not a body.

    ``function f(): { server: Server } {`` reaches the annotation's brace first.
    The body is the next one, and the run between them is type syntax only.
    """
    if opening < 0:
        return opening
    for _ in range(4):
        index = _matching_brace(masked, opening) + 1
        limit = min(len(masked), index + _TYPE_TAIL_MAX)
        while index < limit and masked[index] != '{':
            char = masked[index]
            if char not in _TYPE_TAIL and not (char.isalnum() or char in '_$'):
                return opening
            index += 1
        if index >= limit or masked[index] != '{':
            return opening
        opening = index
    return opening


def _body_opening(masked: str, match) -> int:
    """The brace that opens the body, never one out of the signature.

    Every pattern that reaches here ends at the literal body brace, so the
    match's own last character is it. Taking the *first* brace in the match
    instead meant that for ``f({ a, b }: Props)`` it was the destructuring
    pattern and for ``f(x: { t: string })`` the parameter's inline object type —
    the body then "closed" on the signature line. Measured over 200 harness
    .ts/.tsx files: 17.8% of symbols came out one line long and 25.7% reported
    no calls at all, because the calls sat in the remainder that was cut away.
    """
    opening = match.end() - 1
    if opening < 0 or masked[opening] != '{':
        opening = masked.find('{', match.start(), match.end())
    return _skip_type_object(masked, opening)


@dataclass
class _FunctionCandidate:
    name: str
    params: str
    start: int
    opening: int
    closing: int
    kind: str
    class_name: str = ''
    parent: Optional['_FunctionCandidate'] = None
    qualified: str = ''


class TypeScriptAnalyzer(BaseAnalyzer):
    """TypeScript/JavaScript 代码分析器"""

    SUPPORTED_EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']

    def __init__(self, root_path: str):
        super().__init__(root_path)
        self.ui_events: List[Dict] = []
        self.message_commands: Dict[str, int] = {}

    @property
    def language_name(self) -> str:
        return "typescript"

    def is_supported_file(self, file_path: str) -> bool:
        return any(file_path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def analyze_file(self, file_path: str) -> ModuleInfo:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        module_name = os.path.basename(file_path)
        module_info = ModuleInfo(name=module_name, file_path=file_path, line_number=1)

        module_info.imports = self._extract_imports(source)
        class_infos = self._extract_class_infos(source)
        module_info.classes = [item['name'] for item in class_infos]
        module_info.class_infos = class_infos
        functions = self._extract_functions(source, file_path, class_infos)
        module_info.functions.extend(functions)

        self._extract_ui_events(source, file_path)
        self._extract_postmessage_commands(source)

        return module_info

    def _extract_imports(self, source: str) -> List[str]:
        imports = []
        patterns = [
            r'import\s+.*?from\s+[\'"](.+?)[\'"]',
            r'import\s+[\'"](.+?)[\'"]',
            r'require\([\'"](.+?)[\'"]\)',
        ]
        for pattern in patterns:
            imports.extend(re.findall(pattern, source))
        return imports

    def _extract_classes(self, source: str) -> List[str]:
        return [item['name'] for item in self._extract_class_infos(source)]

    def _extract_class_infos(self, source: str) -> List[dict]:
        masked = _mask_non_code(source)
        rows = []
        seen = set()
        patterns = (
            r'\bclass\s+([A-Za-z_$][\w$]*)[^\n{]*\{',
            r'\b([A-Za-z_$][\w$]*)\s*=\s*class(?:\s+[A-Za-z_$][\w$]*)?[^\n{]*\{',
        )
        for pattern in patterns:
            for match in re.finditer(pattern, masked):
                name = match.group(1)
                opening = _body_opening(masked, match)
                if opening < 0 or (name, opening) in seen:
                    continue
                seen.add((name, opening))
                closing = _matching_brace(masked, opening)
                rows.append({
                    'name': name,
                    'start_line': _line_at(source, match.start()),
                    'end_line': _line_at(source, closing),
                    '_start': match.start(), '_opening': opening, '_closing': closing,
                })
        return sorted(rows, key=lambda item: item['_start'])

    def _extract_ui_events(self, source: str, file_path: str):
        inline_pattern = r'(onclick|onchange|onsubmit|oninput|onkeydown|onkeyup|onfocus|onblur)\s*=\s*["\']?([^"\';\s]+)["\']?'
        for match in re.finditer(inline_pattern, source):
            event_type = match.group(1)
            handler = match.group(2).replace('()', '')
            line_num = source[:match.start()].count('\n') + 1
            self.ui_events.append({
                'event': event_type,
                'handler': handler,
                'file': file_path,
                'line': line_num,
                'type': 'inline'
            })

        add_event_pattern = r'(?:getElementById|querySelector)[^;]*?\.addEventListener\([\'"]([\w]+)[\'"]\s*,\s*(\w+)'
        for match in re.finditer(add_event_pattern, source):
            event_type = match.group(1)
            handler = match.group(2)
            line_num = source[:match.start()].count('\n') + 1
            self.ui_events.append({
                'event': event_type,
                'handler': handler,
                'file': file_path,
                'line': line_num,
                'type': 'addEventListener'
            })

    def _extract_postmessage_commands(self, source: str):
        pattern = r'vscode\.postMessage\s*\(\s*\{[^}]*command\s*:\s*[\'"]?(\w+)'
        for match in re.finditer(pattern, source):
            cmd = match.group(1)
            self.message_commands[cmd] = self.message_commands.get(cmd, 0) + 1

    def _extract_functions(self, source: str, file_path: str, class_infos=None) -> List[FunctionInfo]:
        masked = _mask_non_code(source)
        classes = class_infos if class_infos is not None else self._extract_class_infos(source)
        candidates: List[_FunctionCandidate] = []
        seen_openings = set()

        patterns = (
            ('function', r'(?m)\b(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^()]*)\)[^\n{]*\{'),
            ('function-expr', r'(?m)\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function(?:\s+[A-Za-z_$][\w$]*)?\s*\(([^()]*)\)[^\n{]*\{'),
            ('arrow', r'(?m)\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(([^()]*)\)\s*(?::[^\n=]+)?=>\s*\{'),
            ('property-arrow', r'(?m)\b([A-Za-z_$][\w$]*)\s*:\s*(?:async\s+)?\(([^()]*)\)\s*=>\s*\{'),
            ('method', r'(?m)^\s*(?:(?:public|private|protected|static|async|get|set|readonly|abstract|override)\s+)*([A-Za-z_$][\w$]*)\s*\(([^()]*)\)\s*(?::[^\n{]+)?\{'),
        )
        for kind, pattern in patterns:
            for match in re.finditer(pattern, masked):
                name = match.group(1)
                if name in _JS_WORD_EXCLUDES:
                    continue
                opening = _body_opening(masked, match)
                if opening < 0 or opening in seen_openings:
                    continue
                seen_openings.add(opening)
                candidates.append(_FunctionCandidate(
                    name=name, params=match.group(2) if match.re.groups >= 2 else '',
                    start=match.start(), opening=opening,
                    closing=_matching_brace(masked, opening), kind=kind,
                ))

        # Named anonymous callbacks are essential execution nodes for HTTP,
        # Worker and React chains. They carry no name of their own, so one has to
        # be made — and what it is made of decides whether the anchor survives an
        # edit. A line number does not: inserting a blank line anywhere above
        # renames every callback below it, and everything keyed to those names —
        # saved positions, pins, a session's own trace — points at nothing.
        # The name is instead its position among its SIBLINGS, assigned below
        # once the nesting is known, so it moves only when the code around it
        # actually reorders.
        callback_patterns = (
            r'(?m)([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\([^\n{}]{0,120}?,\s*(?:async\s+)?\(([^()]*)\)\s*=>\s*\{',
            r'(?m)([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\(\s*(?:async\s+)?function(?:\s+[A-Za-z_$][\w$]*)?\s*\(([^()]*)\)\s*\{',
        )
        for pattern in callback_patterns:
            for match in re.finditer(pattern, masked):
                opening = _body_opening(masked, match)
                if opening < 0 or opening in seen_openings:
                    continue
                seen_openings.add(opening)
                leaf = match.group(1).rsplit('.', 1)[-1]
                if leaf not in {
                    'useEffect', 'effect', 'on', 'once', 'addEventListener',
                    'setInterval', 'setTimeout', 'then', 'catch', 'finally',
                    'register', 'subscribe', 'listen',
                }:
                    continue
                candidates.append(_FunctionCandidate(
                    name=leaf, params=match.group(2) or '',
                    start=match.start(), opening=opening,
                    closing=_matching_brace(masked, opening), kind='callback',
                ))

        candidates.sort(key=lambda item: (item.start, -(item.closing - item.start)))
        for candidate in candidates:
            containers = [item for item in candidates if item is not candidate
                          and item.opening < candidate.start < item.closing]
            candidate.parent = min(containers, key=lambda item: item.closing - item.opening) if containers else None
            if candidate.parent is None:
                owning_classes = [item for item in classes
                                  if item['_opening'] < candidate.start < item['_closing']]
                if owning_classes:
                    candidate.class_name = min(
                        owning_classes, key=lambda item: item['_closing'] - item['_opening'],
                    )['name']

        # Repeated object properties such as three route `handler` callbacks need
        # distinct names. They are numbered by their order among siblings of the
        # same name under the same parent — `useEffect#2` is the second useEffect
        # in that component, which is both stable under unrelated edits and means
        # something to a reader. A unique name keeps no suffix at all.
        sibling_groups = {}
        for candidate in candidates:
            owner_key = id(candidate.parent) if candidate.parent is not None else candidate.class_name
            sibling_groups.setdefault((owner_key, candidate.name), []).append(candidate)
        for siblings in sibling_groups.values():
            if len(siblings) < 2:
                continue
            for index, candidate in enumerate(sorted(siblings, key=lambda item: item.start)):
                candidate.name += '#{}'.format(index + 1)

        def qualify(candidate: _FunctionCandidate) -> str:
            if candidate.qualified:
                return candidate.qualified
            if candidate.parent is not None:
                candidate.qualified = qualify(candidate.parent) + '.' + candidate.name
            elif candidate.class_name:
                candidate.qualified = candidate.class_name + '.' + candidate.name
            else:
                candidate.qualified = candidate.name
            return candidate.qualified

        for candidate in candidates:
            qualify(candidate)

        aliases = self._import_aliases(source)
        factories = self._factory_aliases(masked)
        functions: List[FunctionInfo] = []
        by_candidate = {}
        for candidate in candidates:
            body_start = candidate.opening + 1
            body_end = candidate.closing
            body_mask = list(masked[body_start:body_end])
            for child in candidates:
                if child is candidate or not (body_start <= child.start and child.closing <= body_end):
                    continue
                lo = max(0, child.start - body_start)
                hi = min(len(body_mask), child.closing + 1 - body_start)
                for index in range(lo, hi):
                    if body_mask[index] != '\n':
                        body_mask[index] = ' '
            sites = self._extract_call_sites(
                ''.join(body_mask), source[body_start:body_end],
                _line_at(source, body_start), aliases, factories,
            )
            params = [item.strip().split(':')[0].strip() for item in candidate.params.split(',') if item.strip()]
            info = FunctionInfo(
                name=candidate.name, file_path=file_path,
                line_number=_line_at(source, candidate.start),
                line_end=_line_at(source, candidate.closing),
                parameters=params, is_method=bool(candidate.class_name),
                class_name=candidate.class_name or None,
                parent_function=qualify(candidate.parent) if candidate.parent is not None else None,
                calls=list(dict.fromkeys(site['target'] for site in sites)),
                call_sites=sites,
            )
            functions.append(info)
            by_candidate[id(candidate)] = info

        # A callback is a real deferred branch of the enclosing function. An
        # object-property arrow (for example ``handler: async (...) =>``) is
        # likewise handed to the API that receives the object.  Keep both as
        # lexical execution branches; ordinary nested declarations remain
        # declarations until an actual call site references them.
        for candidate in candidates:
            if candidate.kind not in {'callback', 'property-arrow'} or candidate.parent is None:
                continue
            parent = by_candidate.get(id(candidate.parent))
            child = by_candidate.get(id(candidate))
            if not parent or not child:
                continue
            site = {
                'target': child.full_name, 'raw_target': child.full_name,
                'call_kind': 'callback', 'receiver': '',
                'line': child.line_number, 'column': 0, 'seq': len(parent.call_sites),
                'conds': ['nocond'], 'resolution': 'lexical', 'evidence': 'lexical-callback',
            }
            parent.call_sites.append(site)
            if child.full_name not in parent.calls:
                parent.calls.append(child.full_name)
        return functions

    @staticmethod
    def _import_aliases(source: str) -> Dict[str, dict]:
        aliases: Dict[str, dict] = {}
        for match in re.finditer(r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)', source):
            aliases[match.group(1)] = {'module': match.group(2), 'imported': '*'}
        for match in re.finditer(r'\bimport\s+\*\s+as\s+([A-Za-z_$][\w$]*)\s+from\s+[\'\"]([^\'\"]+)[\'\"]', source):
            aliases[match.group(1)] = {'module': match.group(2), 'imported': '*'}
        for match in re.finditer(r'\bimport\s+([A-Za-z_$][\w$]*)\s+from\s+[\'\"]([^\'\"]+)[\'\"]', source):
            aliases[match.group(1)] = {'module': match.group(2), 'imported': 'default'}
        for match in re.finditer(r'\bimport\s*\{([^}]+)\}\s*from\s*[\'\"]([^\'\"]+)[\'\"]', source):
            for item in match.group(1).split(','):
                parts = re.split(r'\s+as\s+', item.strip())
                if parts and parts[0]:
                    aliases[parts[-1]] = {'module': match.group(2), 'imported': parts[0]}
        # `const { a, b: c } = require('spec')` — the CJS spelling of a named
        # import, and the one a bundler's output uses.
        for match in re.finditer(
            r'\b(?:const|let|var)\s*\{([^}]+)\}\s*=\s*require\(\s*[\'\"]([^\'\"]+)[\'\"]\s*\)',
            source,
        ):
            for item in match.group(1).split(','):
                parts = [p.strip() for p in item.split(':')]
                if parts and parts[0]:
                    aliases[parts[-1]] = {'module': match.group(2), 'imported': parts[0]}
        # `var routeOrtho = ns.routeOrtho` where `ns` is already an alias for a
        # whole module. Without this the chain breaks at the second hop: the
        # namespace is known to come from somewhere, the name taken off it is
        # not, and every call through it reads as a call to nothing. This is how
        # a module system's own output is written, so it is the common case, not
        # an exotic one. Repeated until it settles, because one re-binding can
        # feed the next.
        member = re.compile(
            r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*'
            r'([A-Za-z_$][\w$]*)\s*\.\s*([A-Za-z_$][\w$]*)\s*(?:[;\n]|$)'
        )
        for _ in range(4):
            grew = False
            for match in member.finditer(source):
                local, namespace, name = match.group(1), match.group(2), match.group(3)
                origin = aliases.get(namespace)
                if origin is None or origin.get('imported') != '*':
                    continue
                bound = {'module': origin['module'], 'imported': name}
                if aliases.get(local) != bound:
                    aliases[local] = bound
                    grew = True
            if not grew:
                break
        return aliases

    @staticmethod
    def _factory_aliases(masked_source: str) -> Dict[str, str]:
        return {
            match.group(1): match.group(2)
            for match in re.finditer(
                r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*\(',
                masked_source,
            )
        }

    def _extract_call_sites(self, masked_body: str, actual_body: str, base_line: int,
                            aliases: Dict[str, dict], factories=None) -> List[dict]:
        factories = factories or {}
        sites = []
        pattern = re.compile(r'(?:(?P<receiver>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\.\s*)?(?P<name>[A-Za-z_$][\w$]*)\s*\(')
        for match in pattern.finditer(masked_body):
            name = match.group('name')
            if name in _JS_WORD_EXCLUDES:
                continue
            receiver = match.group('receiver') or ''
            line = base_line + actual_body.count('\n', 0, match.start())
            column = match.start() - actual_body.rfind('\n', 0, match.start()) - 1
            site = {
                'target': name, 'raw_target': name,
                'call_kind': 'attribute' if receiver else 'name',
                'receiver': receiver, 'line': line, 'column': column,
                'seq': len(sites), 'conds': ['nocond'],
                'resolution': 'unresolved', 'evidence': 'source-call',
            }
            root_receiver = receiver.split('.', 1)[0] if receiver else ''
            if root_receiver in aliases:
                site['module_ref'] = dict(aliases[root_receiver])
            elif not receiver and name in aliases and aliases[name].get('imported') != '*':
                site['module_ref'] = dict(aliases[name])
            if root_receiver in factories:
                site['factory_ref'] = factories[root_receiver]
            sites.append(site)
        return sites

    def _extract_function_body(self, source: str, start: int) -> str:
        masked = _mask_non_code(source)
        opening = start if start < len(masked) and masked[start] == '{' else masked.find('{', start)
        if opening < 0:
            return ''
        return source[opening:_matching_brace(masked, opening) + 1]

    def _extract_calls(self, body: str) -> List[str]:
        masked = _mask_non_code(body)
        return list(dict.fromkeys(
            site['target'] for site in self._extract_call_sites(masked, body, 1, {}, {})
        ))

    def analyze(self) -> ProjectInfo:
        project_info = super().analyze()
        project_info.ui_events = self.ui_events
        project_info.message_commands = self.message_commands
        return project_info


def analyze_typescript_project(root_path: str) -> ProjectInfo:
    analyzer = TypeScriptAnalyzer(root_path)
    return analyzer.analyze()
