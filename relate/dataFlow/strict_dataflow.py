"""
strict_dataflow.py - 严谨数据流边提取
================================================================================

只保留真实的数据移动，剔除"调用即数据流"的伪边。

判定规则（对 caller f 中的一处对 callee g 的调用）：

  arg    f -> g   调用参数携带 f 的数据（变量/属性/表达式，非纯字面量），
                  或非 self 的 receiver 对象传入方法。
  return g -> f   g 的返回值被 f 实际消费（赋值后被读取、参与表达式、被 return），
                  裸语句调用 `g()` 不算。
  relay  p -> g   f 的局部变量携带着 producer p 的产出（x = p() 或由其派生），
                  随后作为参数传入 g —— p 的数据经 f 流进 g。
  state  w -> r   同一个类的方法之间，w 写入的 self.attr 被 r 读取。

剔除：仅控制流经过（无参/纯字面量参数且返回值未消费）、纯 relay 函数。
Python 用 AST 精确分析；其他语言退化为源码文本启发式（不支持 state）。
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ─────────────────────────────────────────────
# 调用现场信息
# ─────────────────────────────────────────────

@dataclass
class CallFact:
    line: int                     # 源码行号（1 起始；0 = 未知）
    name: str                     # 被调用的名字（foo / obj.method 的 method）
    args_data: bool = False       # 参数/receiver 是否携带数据
    arg_vars: Set[str] = field(default_factory=set)   # 参数中引用到的局部变量
    consumed: bool = False        # 返回值是否被调用者消费


@dataclass
class FuncFacts:
    calls: List[CallFact] = field(default_factory=list)
    producers: Dict[str, Set[int]] = field(default_factory=dict)  # var -> calls 下标
    self_writes: Set[str] = field(default_factory=set)
    self_reads: Set[str] = field(default_factory=set)


# ─────────────────────────────────────────────
# Python AST 分析
# ─────────────────────────────────────────────

def _is_literal_expr(node) -> bool:
    """是否为纯字面量表达式（常量 / 仅含字面量的容器）"""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_literal_expr(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (k is None or _is_literal_expr(k)) and _is_literal_expr(v)
            for k, v in zip(node.keys, node.values)
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
        return _is_literal_expr(node.operand)
    return False


def _expr_names(node) -> Set[str]:
    """表达式中引用到的所有名字（含属性基对象）"""
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            names.add(sub.id)
    return names


def _find_func_node(tree: ast.AST, symbol: str, line_start: int,
                    hint_lines: Optional[List[int]] = None):
    """按 symbol 末段名 + 行号在 AST 中定位函数节点。

    anchor 可能漂移（源码改了但没重建），优先用 call-site 行号投票：
    哪个同名函数的区间覆盖了最多 hint 行就选哪个。
    """
    name = symbol.split(".")[-1]
    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if not candidates:
        return None
    if hint_lines:
        def _score(node) -> int:
            lo, hi = node.lineno, node.end_lineno or node.lineno
            return sum(1 for ln in hint_lines if lo <= ln <= hi)
        best = max(candidates, key=_score)
        if _score(best) > 0:
            return best
    for node in candidates:
        if node.lineno == line_start:
            return node
    # 装饰器会让 anchor 行号落在 def 之前，给少量容忍
    for node in candidates:
        if 0 <= node.lineno - line_start <= 5:
            return node
    return candidates[0] if len(candidates) == 1 else None


def _analyze_python(tree: ast.AST, symbol: str, line_start: int,
                    hint_lines: Optional[List[int]] = None) -> Optional[FuncFacts]:
    func = _find_func_node(tree, symbol, line_start, hint_lines)
    if func is None:
        return None

    # 父指针：判断调用是否为裸语句
    parents: Dict[int, ast.AST] = {}
    for node in ast.walk(func):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    call_nodes = [n for n in ast.walk(func) if isinstance(n, ast.Call)]
    call_index = {id(n): i for i, n in enumerate(call_nodes)}

    facts = FuncFacts()
    read_names: Set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            read_names.add(node.id)

    for call in call_nodes:
        if isinstance(call.func, ast.Name):
            name = call.func.id
            receiver = None
        elif isinstance(call.func, ast.Attribute):
            name = call.func.attr
            receiver = call.func.value.id if isinstance(call.func.value, ast.Name) else None
        else:
            name = ""
            receiver = None

        arg_exprs = list(call.args) + [kw.value for kw in call.keywords]
        args_data = any(not _is_literal_expr(a) for a in arg_exprs)
        # 非 self/cls 的 receiver 本身就是传入方法的数据
        if receiver and receiver not in ("self", "cls"):
            args_data = True
        arg_vars: Set[str] = set()
        for a in arg_exprs:
            arg_vars |= _expr_names(a)
        arg_vars.discard("self")
        arg_vars.discard("cls")

        # 返回值是否被消费：穿透 Await/Starred 后父节点不是裸 Expr；
        # 赋值给简单名字时，要求该名字之后真的被读取
        consumed = True
        node = call
        parent = parents.get(id(node))
        while isinstance(parent, (ast.Await, ast.Starred)):
            node, parent = parent, parents.get(id(parent))
        if isinstance(parent, ast.Expr):
            consumed = False
        elif isinstance(parent, ast.Assign):
            targets = [t for t in parent.targets if isinstance(t, ast.Name)]
            if targets and len(parent.targets) == len(targets):
                consumed = any(t.id in read_names for t in targets if t.id != "_")

        facts.calls.append(CallFact(
            line=call.lineno,
            name=name,
            args_data=args_data,
            arg_vars=arg_vars,
            consumed=consumed,
        ))

    # 局部变量 producers：x = f() / x = <含已产出变量的表达式>
    assigns = [n for n in ast.walk(func) if isinstance(n, (ast.Assign, ast.AnnAssign))]
    assigns.sort(key=lambda n: n.lineno)
    for node in assigns:
        value = node.value
        if value is None:  # x: T 纯声明
            continue
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        else:
            targets = [node.target]
        rhs_calls = {
            call_index[id(sub)] for sub in ast.walk(value)
            if isinstance(sub, ast.Call) and id(sub) in call_index
        }
        inherited: Set[int] = set()
        for var in _expr_names(value):
            inherited |= facts.producers.get(var, set())
        for target in targets:
            for tname in _expr_names(target):
                if rhs_calls:
                    facts.producers.setdefault(tname, set()).update(rhs_calls)
                if inherited:
                    facts.producers.setdefault(tname, set()).update(inherited)

    # self.attr 写 / 读
    for node in ast.walk(func):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in ("self", "cls"):
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    facts.self_writes.add(node.attr)
                elif isinstance(node.ctx, ast.Load):
                    facts.self_reads.add(node.attr)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Attribute):
            t = node.target
            if isinstance(t.value, ast.Name) and t.value.id in ("self", "cls"):
                facts.self_writes.add(t.attr)
    # 方法名调用不算状态读取（self.foo() 的 foo 不是数据属性）——保留无害，由写侧收口
    return facts


# ─────────────────────────────────────────────
# 非 Python 文本启发式
# ─────────────────────────────────────────────

_LITERAL_JS = re.compile(
    r"^\s*(-?[\d.]+|'[^']*'|\"[^\"]*\"|`[^`]*`|true|false|null|undefined|\[\s*\]|\{\s*\})\s*$"
)
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_ASSIGN_JS = re.compile(
    r"(?:\b(?:const|let|var)\s+)?([A-Za-z_$][\w$]*)\s*=\s*(?:new\s+)?(?:await\s+)?([A-Za-z_$][\w$.]*)\s*\("
)
_CONSUMED_PREFIX = re.compile(
    r"(=|=>|return|&&|\|\||!|\?|:|\(|,|\[|\+|-|\*|/|<|>)\s*$"
)


def _split_top_level(text: str) -> List[str]:
    """按深度 0 的逗号切分参数文本"""
    parts, depth, buf = [], 0, []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closers = set(pairs.values())
    stack: List[str] = []
    quote = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == "\\":
                if i + 1 < len(text):
                    buf.append(text[i + 1])
                    i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
            buf.append(ch)
        elif ch in pairs:
            stack.append(pairs[ch])
            buf.append(ch)
        elif ch in closers:
            if stack and stack[-1] == ch:
                stack.pop()
            buf.append(ch)
        elif ch == "," and not stack:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _extract_paren_text(lines: List[str], line_idx: int, start_col: int) -> str:
    """从 ( 之后开始跨行扫描，返回括号内文本"""
    depth = 1
    buf: List[str] = []
    quote = None
    li, ci = line_idx, start_col
    while li < len(lines):
        line = lines[li]
        while ci < len(line):
            ch = line[ci]
            if quote:
                if ch == "\\":
                    ci += 1
                elif ch == quote:
                    quote = None
            elif ch in "'\"`":
                quote = ch
            elif ch == "(":
                depth += 1
                buf.append(ch)
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return "".join(buf)
                buf.append(ch)
            elif ch == "/" and ci + 1 < len(line) and line[ci + 1] == "/":
                break  # 行注释
            else:
                buf.append(ch)
            ci += 1
        li += 1
        ci = 0
    return "".join(buf)


def _analyze_text(lines: List[str], symbol: str, line_start: int, line_end: int,
                  call_refs: List[dict]) -> FuncFacts:
    """JS 等非 Python 语言的启发式分析：按 call site 行号定位调用文本"""
    facts = FuncFacts()
    lo = max(0, (line_start or 1) - 1)
    hi = min(len(lines), line_end or len(lines))

    # relay 跟踪：函数体内的简单赋值
    name_producers: Dict[str, Set[str]] = {}
    for line in lines[lo:hi]:
        m = _ASSIGN_JS.search(line)
        if m:
            name_producers.setdefault(m.group(1), set()).add(m.group(2).split(".")[-1])

    for ref in call_refs:
        lineno = int(ref.get("line") or 0)
        if lineno <= 0 or lineno > len(lines):
            continue
        raw = ref.get("raw_target") or ref.get("target") or ""
        name = str(raw).split("::")[-1].split(".")[-1]
        if not name or not _IDENT.fullmatch(name):
            continue
        src_line = lines[lineno - 1]
        col = int(ref.get("column") or 0)
        search_from = max(0, col - 1)
        pos = src_line.find(name, search_from)
        if pos < 0:
            pos = src_line.find(name)
        if pos < 0:
            continue
        paren = src_line.find("(", pos + len(name))
        if paren < 0:
            continue

        arg_text = _extract_paren_text(lines, lineno - 1, paren + 1)
        arg_parts = [a for a in _split_top_level(arg_text) if a.strip()]
        args_data = any(not _LITERAL_JS.match(a) for a in arg_parts)
        arg_vars = set()
        for a in arg_parts:
            arg_vars |= {t for t in _IDENT.findall(a) if t not in ("true", "false", "null", "undefined")}

        prefix = src_line[:pos].strip()
        consumed = bool(prefix) and not prefix.endswith(";") \
            and prefix not in ("await", "yield") \
            and bool(_CONSUMED_PREFIX.search(prefix))

        facts.calls.append(CallFact(
            line=lineno, name=name,
            args_data=args_data, arg_vars=arg_vars, consumed=consumed,
        ))
        # 文本模式 relay：producer 用被调名字暂存，resolve 阶段再映射
        if not hasattr(facts, "relay_names"):
            facts.relay_names = {}  # type: ignore[attr-defined]
        for var in arg_vars:
            for prod_name in name_producers.get(var, ()):
                facts.relay_names.setdefault(var, set()).add(prod_name)  # type: ignore[attr-defined]

    return facts


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def _norm(node_id: str) -> str:
    return node_id.replace("\\", "/")


def _iter_call_refs(anchor) -> List[dict]:
    sites = list(getattr(anchor, "call_sites", []) or [])
    if sites:
        return [s for s in sites if isinstance(s, dict)]
    return [
        {"target": raw, "seq": idx}
        for idx, raw in enumerate(getattr(anchor, "callees", []) or [])
    ]


def compute_strict_dataflow(
    root: str,
    anchors: dict,
    skip_pairs: Optional[Set[Tuple[str, str]]] = None,
) -> List[dict]:
    """计算严谨数据流边。

    返回: [{from_id, to_id, kinds, seq, condition, data_in, data_out, evidence}, ...]
    """
    root_path = Path(root)
    skip_pairs = skip_pairs or set()
    id_index = {_norm(a.id): a for a in anchors.values()}

    file_cache: Dict[str, Optional[object]] = {}   # py 文件 -> AST
    text_cache: Dict[str, List[str]] = {}          # 任意文件 -> 行
    facts_cache: Dict[str, Optional[FuncFacts]] = {}  # anchor.id -> FuncFacts

    def _file_lines(rel_file: str) -> Optional[List[str]]:
        if rel_file in text_cache:
            return text_cache[rel_file]
        path = root_path / rel_file
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            lines = None
        if lines is None:
            text_cache[rel_file] = []
            return None
        text_cache[rel_file] = lines
        return lines

    def _analyze(anchor, refs: List[dict]) -> Optional[FuncFacts]:
        key = _norm(anchor.id)
        if key in facts_cache:
            return facts_cache[key]
        facts: Optional[FuncFacts] = None
        rel_file = getattr(anchor, "file", "")
        if rel_file.endswith(".py"):
            if rel_file not in file_cache:
                path = root_path / rel_file
                try:
                    file_cache[rel_file] = ast.parse(
                        path.read_text(encoding="utf-8", errors="ignore")
                    )
                except (SyntaxError, OSError, UnicodeDecodeError):
                    file_cache[rel_file] = None
            tree = file_cache[rel_file]
            if tree is not None:
                hints = [int(r.get("line") or 0) for r in refs if isinstance(r, dict)]
                facts = _analyze_python(tree, anchor.symbol, anchor.line_start,
                                        [h for h in hints if h > 0])
        else:
            lines = _file_lines(rel_file)
            if lines:
                facts = _analyze_text(lines, anchor.symbol,
                                      anchor.line_start, anchor.line_end, refs)
        facts_cache[key] = facts
        return facts

    def _match_call(facts: FuncFacts, ref: dict) -> Optional[int]:
        """把 call site 匹配到分析出的 CallFact（行号优先，唯一名字兜底）"""
        lineno = int(ref.get("line") or 0)
        target = str(ref.get("raw_target") or ref.get("target") or "")
        name = target.split("::")[-1].split(".")[-1]
        for i, c in enumerate(facts.calls):
            if lineno and c.line != lineno:
                continue
            if name and c.name and c.name != name:
                continue
            return i
        if lineno:
            for i, c in enumerate(facts.calls):
                if c.line == lineno:
                    return i
        # 行号漂移兜底：同名调用唯一时直接采用
        if name:
            named = [i for i, c in enumerate(facts.calls) if c.name == name]
            if len(named) == 1:
                return named[0]
        return None

    # (from_id, to_id, condition) -> 累积
    acc: Dict[Tuple[str, str, Optional[str]], dict] = {}

    def _emit(from_id: str, to_id: str, kind: str, seq: int,
              condition: Optional[str], detail: str) -> None:
        if from_id == to_id:
            return
        key = (from_id, to_id, condition)
        entry = acc.get(key)
        if entry is None:
            entry = acc[key] = {
                "from_id": from_id,
                "to_id": to_id,
                "kinds": set(),
                "seq": [],
                "condition": condition,
                "details": [],
            }
        entry["kinds"].add(kind)
        if seq not in entry["seq"]:
            entry["seq"].append(seq)
        if detail:
            entry["details"].append(detail)

    for anchor in anchors.values():
        if getattr(anchor, "is_virtual", False):
            continue
        if getattr(anchor, "symbol_type", "") not in ("function", "method"):
            continue
        refs = _iter_call_refs(anchor)
        if not refs:
            continue
        caller_id = _norm(anchor.id)

        # 只保留能解析到真实 anchor 的调用
        resolved = []  # (ref, callee_anchor)
        for ref in refs:
            target = ref.get("target") or ""
            if not target or "::" not in _norm(str(target)):
                continue
            callee = id_index.get(_norm(str(target)))
            if not callee or getattr(callee, "is_virtual", False):
                continue
            if (caller_id, _norm(callee.id)) in skip_pairs:
                continue
            resolved.append((ref, callee))
        if not resolved:
            continue

        facts = _analyze(anchor, refs)
        if facts is None:
            continue  # 无法分析 caller 源码时不产生 dataflow 边

        # 名字 -> callee anchor id（文本模式 relay 解析用）
        name_to_callee: Dict[str, str] = {}
        for ref, callee in resolved:
            raw = str(ref.get("raw_target") or ref.get("target") or "")
            name_to_callee.setdefault(raw.split("::")[-1].split(".")[-1], _norm(callee.id))

        relay_names = getattr(facts, "relay_names", {})

        for ref, callee in resolved:
            callee_id = _norm(callee.id)
            seq = int(ref.get("seq") or 0)
            conds = ref.get("conds")
            condition = None
            if conds and conds != ["nocond"]:
                import json as _json
                condition = _json.dumps(conds, ensure_ascii=False, separators=(",", ":"))
            elif ref.get("condition"):
                condition = ref.get("condition")

            idx = _match_call(facts, ref)
            if idx is None:
                continue  # 调用现场定位失败，宁缺毋滥
            call = facts.calls[idx]

            # arg: caller 的数据作为参数进 callee
            if call.args_data:
                _emit(caller_id, callee_id, "arg", seq, condition,
                      ",".join(sorted(call.arg_vars))[:120])

            # return: callee 的产出被 caller 消费
            if call.consumed:
                _emit(callee_id, caller_id, "return", seq, condition, "")

            # relay: producer 的产出经 caller 局部变量进 callee
            for var in call.arg_vars:
                for prod_idx in facts.producers.get(var, set()):
                    if prod_idx < 0 or prod_idx >= len(facts.calls):
                        continue
                    prod_name = facts.calls[prod_idx].name
                    prod_id = name_to_callee.get(prod_name)
                    if prod_id and prod_id not in (caller_id, callee_id):
                        _emit(prod_id, callee_id, "relay", seq, condition, var)
                for prod_name in relay_names.get(var, set()):
                    prod_id = name_to_callee.get(prod_name)
                    if prod_id and prod_id not in (caller_id, callee_id):
                        _emit(prod_id, callee_id, "relay", seq, condition, var)

    # state: 同类方法间 self.attr 写 -> 读
    class_methods: Dict[Tuple[str, str], list] = {}
    for anchor in anchors.values():
        if getattr(anchor, "is_virtual", False):
            continue
        if getattr(anchor, "symbol_type", "") != "method":
            continue
        symbol = getattr(anchor, "symbol", "") or ""
        if "." not in symbol:
            continue
        facts = _analyze(anchor, _iter_call_refs(anchor))
        if facts is None or not (facts.self_writes or facts.self_reads):
            continue
        key = (getattr(anchor, "file", ""), symbol.rsplit(".", 1)[0])
        class_methods.setdefault(key, []).append((_norm(anchor.id), facts))

    for members in class_methods.values():
        for writer_id, w_facts in members:
            for reader_id, r_facts in members:
                if writer_id == reader_id:
                    continue
                shared = w_facts.self_writes & r_facts.self_reads
                if shared:
                    _emit(writer_id, reader_id, "state", 0, None,
                          ",".join(sorted(shared))[:120])

    results = []
    for (from_id, to_id, condition), entry in acc.items():
        kinds = sorted(entry["kinds"])
        results.append({
            "from_id": from_id,
            "to_id": to_id,
            "kinds": kinds,
            "seq": sorted(entry["seq"]),
            "condition": condition,
            "data_in": ";".join(sorted(set(entry["details"])))[:200],
            "data_out": "+".join(kinds),
            "evidence": "strict-dataflow:{}".format("+".join(kinds)),
        })
    return results


__all__ = ["compute_strict_dataflow"]
