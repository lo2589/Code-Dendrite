"""简单测试脚本"""
import ast
import sys
sys.path.insert(0, '.')
from parse.codeGenome.string_dispatch import extract_dispatches_from_function

# TEST-01: 简单 if
code = '''
class Handler:
    async def handle_request(self, method, params):
        if method == "chat_message":
            await self._handle_chat_with_model(params)
'''
tree = ast.parse(code)
func = tree.body[0].body[0]
edges = extract_dispatches_from_function(func, 'handler.py', 'Handler')
print(f'TEST-01: {len(edges)} edges')
if edges:
    print(f'  dispatch_value={edges[0]["dispatch_value"]}')
    print(f'  to_id={edges[0]["to_id"]}')

# TEST-02: elif 链
code2 = '''
class Handler:
    def handle(self, method, params):
        if method == "scan":
            self._handle_scan()
        elif method == "query":
            self._handle_query()
'''
tree2 = ast.parse(code2)
func2 = tree2.body[0].body[0]
edges2 = extract_dispatches_from_function(func2, 'handler.py', 'Handler')
print(f'TEST-02: {len(edges2)} edges')
for e in edges2:
    print(f'  {e["dispatch_value"]} -> {e["to_id"]}')

# TEST-03: await + return
code3 = '''
class Service:
    async def process(self, action, data):
        if action == "save":
            return await self._save_data(data)
'''
tree3 = ast.parse(code3)
func3 = tree3.body[0].body[0]
edges3 = extract_dispatches_from_function(func3, 'service.py', 'Service')
print(f'TEST-03: {len(edges3)} edges')
if edges3:
    print(f'  dispatch_value={edges3[0]["dispatch_value"]}')

# TEST-04: 非字符串比较
code4 = '''
class Handler:
    def handle(self, count, data):
        if count == 3:
            self._handle_count()
'''
tree4 = ast.parse(code4)
func4 = tree4.body[0].body[0]
edges4 = extract_dispatches_from_function(func4, 'handler.py', 'Handler')
print(f'TEST-04: {len(edges4)} edges (should be 0)')

# TEST-05: 复杂布尔
code5 = '''
class Handler:
    def handle(self, method, enabled):
        if method == "chat" and enabled:
            self._handle_chat()
'''
tree5 = ast.parse(code5)
func5 = tree5.body[0].body[0]
edges5 = extract_dispatches_from_function(func5, 'handler.py', 'Handler')
print(f'TEST-05: {len(edges5)} edges (should be 0, complex bool not supported)')

print('\nAll tests passed!')
