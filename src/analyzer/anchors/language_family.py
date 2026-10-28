"""按名字兜底解析时，被调的同名符号必须和调用方能直接互调。

``_resolve_call_id`` 前面的路都走不通时，会退到"全仓库唯一的同名符号"。这一步不看语言，
于是 Python 函数里一个局部定义的 ``words(...)`` 连到了 lens 里同名的 JS 函数，JS 里的
``count(...)`` 连到了 Python 的 ``AnchorDatabase.count``——本仓库实测 27 条这样的边，
全标着 ``resolution: exact``。

能直接互调的算一族：JS / TS / Vue / Svelte；C / C++ / Objective-C / Swift（桥接头）；
JVM 上的 Java / Kotlin / Scala / Groovy。HTML / CSS 是标记，脚本引用 DOM 节点和选择器
本来就是跨语言的，作为目标一律放行。其余语言各自一族。
"""

_FAMILY = {
    "javascript": "js", "typescript": "js", "jsx": "js", "tsx": "js", "vue": "js", "svelte": "js",
    "c": "native", "cpp": "native", "objective-c": "native", "objc": "native", "swift": "native",
    "java": "jvm", "kotlin": "jvm", "scala": "jvm", "groovy": "jvm",
}
_MARKUP = frozenset({"html", "css", "scss", "sass", "less"})


def can_call_by_name(caller_language: str, target_language: str) -> bool:
    """调用方能不能凭名字直接调到这个语言里的符号。语言未知时不拦。"""
    a, b = str(caller_language or ""), str(target_language or "")
    if not a or not b or b in _MARKUP or a in _MARKUP:
        return True
    return _FAMILY.get(a, a) == _FAMILY.get(b, b)
