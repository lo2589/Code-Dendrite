"""跳公式 parse：识别"大的纯数据/公式表达式"(只有算术/调用/字面量，无 def/控制流)，
遍历时不下钻进去。用来挡住 sympy rubi 那种 753KB / 几十万节点的符号公式表——
它的 sqrt/S 不是调用关系，是数据，逐节点 walk 纯属浪费且产生噪声。

按【内容 + 规模】判定，不是按文件体积。判定用有界扫描，O(min_nodes)，正常代码近乎零开销。
"""
import ast
from collections import deque

# 表达式型节点：公式/数据的构成
_EXPR_TYPES = (
    ast.Call, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.Constant, ast.Name, ast.Attribute, ast.Subscript,
    ast.Tuple, ast.List, ast.Dict, ast.Set, ast.Starred, ast.Slice,
    ast.keyword, ast.IfExp, ast.JoinedStr, ast.FormattedValue,
)
# 出现这些 = 有逻辑/定义/推导，就不是纯公式，别跳
_NON_DATA = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
    ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.AsyncWith,
    ast.Try, ast.Return, ast.Assign, ast.AugAssign, ast.AnnAssign,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
    ast.comprehension, ast.Await, ast.Yield, ast.YieldFrom, ast.NamedExpr,
)


def _maybe_big(node) -> bool:
    """O(1) 粗筛：源码跨度大才值得细查（避免对海量小节点做细判）。"""
    try:
        if node.end_lineno is None:
            return False
        if node.end_lineno - node.lineno >= 3:
            return True
        return (node.end_lineno == node.lineno
                and (node.end_col_offset - node.col_offset) >= 300)
    except AttributeError:
        return False


def is_opaque_data_expr(node, min_nodes: int = 400) -> bool:
    """node 是个大的纯数据/公式表达式吗？有界扫描：碰到逻辑节点立刻判否；
    全是数据且规模到阈值即判是（不扫完，O(min_nodes)）。"""
    if not isinstance(node, _EXPR_TYPES):
        return False
    count = 0
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, _NON_DATA):
            return False
        count += 1
        if count >= min_nodes:
            return True
        stack.extend(ast.iter_child_nodes(n))
    return False


def should_skip(node, min_nodes: int = 400) -> bool:
    """粗筛 + 细判：是否把这棵子树当不透明公式跳过。"""
    return _maybe_big(node) and is_opaque_data_expr(node, min_nodes)


def walk_skip_formula(node, min_nodes: int = 400):
    """像 ast.walk（BFS），但遇到公式子树不展开（连节点本身也不 yield，它只是数据）。"""
    todo = deque([node])
    while todo:
        n = todo.popleft()
        yield n
        for c in ast.iter_child_nodes(n):
            if should_skip(c, min_nodes):
                continue
            todo.append(c)
