"""
test_string_dispatch.py — 字符串路由边提取测试
=============================================

测试用例：
- TEST-01: 简单 if
- TEST-02: elif 链
- TEST-03: await + return
- TEST-04: 非字符串比较不应命中
- TEST-05: 复杂布尔表达式先忽略
- TEST-06: 集成测试
"""

import ast
import tempfile
import os
import pytest

from parse.codeGenome.string_dispatch import (
    find_string_dispatches,
    extract_dispatches_from_file,
    extract_dispatches_from_function,
    _is_string_compare,
    _extract_compare_parts,
    _extract_called_symbols,
    _walk_if_chain,
)


# ── TEST-01: 简单 if ───────────────────────────────────────────────

def test_simple_if():
    """测试简单的 if 条件提取。"""
    code = '''
class Handler:
    async def handle_request(self, method, params):
        if method == "chat_message":
            await self._handle_chat_with_model(params)
'''
    tree = ast.parse(code)
    func = tree.body[0].body[0]  # handle_request
    edges = extract_dispatches_from_function(func, "handler.py", "Handler")
    
    assert len(edges) == 1
    assert edges[0]["dispatch_value"] == "chat_message"
    assert edges[0]["dispatch_key"] == "method"
    assert "_handle_chat_with_model" in edges[0]["to_id"]


# ── TEST-02: elif 链 ────────────────────────────────────────────────

def test_elif_chain():
    """测试 if/elif 链的多分支提取。"""
    code = '''
class Handler:
    def handle(self, method, params):
        if method == "scan":
            self._handle_scan()
        elif method == "query":
            self._handle_query()
'''
    tree = ast.parse(code)
    func = tree.body[0].body[0]  # handle
    edges = extract_dispatches_from_function(func, "handler.py", "Handler")
    
    assert len(edges) == 2
    
    # 验证两个分支都被提取
    dispatch_values = [e["dispatch_value"] for e in edges]
    assert "scan" in dispatch_values
    assert "query" in dispatch_values


# ── TEST-03: await + return ──────────────────────────────────────────

def test_await_return():
    """测试 await 和 return 组合调用提取。"""
    code = '''
class Service:
    async def process(self, action, data):
        if action == "save":
            return await self._save_data(data)
'''
    tree = ast.parse(code)
    func = tree.body[0].body[0]  # process
    edges = extract_dispatches_from_function(func, "service.py", "Service")
    
    assert len(edges) == 1
    assert "_save_data" in edges[0]["to_id"]


# ── TEST-04: 非字符串比较不应命中 ───────────────────────────────────

def test_non_string_compare():
    """非字符串比较不应生成 dispatch 边。"""
    code = '''
class Handler:
    def handle(self, count, data):
        if count == 3:
            self._handle_count()
'''
    tree = ast.parse(code)
    func = tree.body[0].body[0]  # handle
    edges = extract_dispatches_from_function(func, "handler.py", "Handler")
    
    assert len(edges) == 0


# ── TEST-05: 复杂布尔表达式先忽略 ───────────────────────────────────

def test_complex_boolean():
    """复杂布尔表达式（and/or）不应生成 dispatch 边。"""
    code = '''
class Handler:
    def handle(self, method, enabled):
        if method == "chat" and enabled:
            self._handle_chat()
'''
    tree = ast.parse(code)
    func = tree.body[0].body[0]  # handle
    edges = extract_dispatches_from_function(func, "handler.py", "Handler")
    
    # 当前不支持 and/or 组合条件
    assert len(edges) == 0


# ── TEST-06: 集成测试 ────────────────────────────────────────────────

def test_integration():
    """集成测试：完整文件扫描。"""
    code = '''
class LLMSchedulerServer:
    async def handle_request(self, method, params):
        if method == "chat_message":
            await self._handle_chat_with_model(params)
        elif method == "scan":
            await self._handle_scan(params)
        elif method == "query":
            return await self._handle_query(params)
    
    async def _handle_chat_with_model(self, params):
        pass
    
    async def _handle_scan(self, params):
        pass
    
    async def _handle_query(self, params):
        pass
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        temp_path = f.name
    
    try:
        edges = extract_dispatches_from_file(temp_path, ".")
        
        assert len(edges) == 3
        
        # 验证 dispatch_value
        dispatch_values = [e["dispatch_value"] for e in edges]
        assert "chat_message" in dispatch_values
        assert "scan" in dispatch_values
        assert "query" in dispatch_values
        
        # 验证 edge_type
        for e in edges:
            assert e["edge_type"] == "dispatch"
            assert e["is_conditional"] == True
        
    finally:
        os.unlink(temp_path)


# ── 辅助函数测试 ────────────────────────────────────────────────────

def test_is_string_compare():
    """测试字符串比较条件判断。"""
    # 正确的字符串比较
    code1 = 'if method == "chat_message": pass'
    tree1 = ast.parse(code1)
    assert _is_string_compare(tree1.body[0].test) == True
    
    # 非字符串比较
    code2 = 'if count == 3: pass'
    tree2 = ast.parse(code2)
    assert _is_string_compare(tree2.body[0].test) == False


def test_extract_compare_parts():
    """测试条件信息提取。"""
    code = 'if method == "chat_message": pass'
    tree = ast.parse(code)
    test = tree.body[0].test
    
    key, value, condition = _extract_compare_parts(test)
    
    assert key == "method"
    assert value == "chat_message"
    assert condition == 'method == "chat_message"'


def test_extract_called_symbols():
    """测试调用目标提取。"""
    code = '''
if method == "chat":
    self._handle_chat()
    return self._save()
'''
    tree = ast.parse(code)
    body = tree.body[0].body
    
    symbols = _extract_called_symbols(body)
    
    assert "self._handle_chat" in symbols
    assert "self._save" in symbols


def test_object_method_target_keeps_context():
    """非 self 的方法调用应保留对象上下文。"""
    code = '''
class Handler:
    def handle(self, action, request):
        if action == "query":
            return handler.run(request)
'''
    tree = ast.parse(code)
    func = tree.body[0].body[0]

    edges = extract_dispatches_from_function(func, "handler.py", "Handler")

    assert len(edges) == 1
    assert edges[0]["to_id"] == "handler.py::handler.run"


def test_walk_if_chain():
    """测试 if/elif 链展开。"""
    code = '''
if method == "a":
    pass
elif method == "b":
    pass
elif method == "c":
    pass
'''
    tree = ast.parse(code)
    if_node = tree.body[0]
    
    chain = _walk_if_chain(if_node)
    
    assert len(chain) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
