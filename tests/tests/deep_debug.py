"""深度调试 dispatch 边提取"""
import ast
import sys
sys.path.insert(0, '.')

# 读取 backend/main.py
with open('D:/workspace/code/parallm/para-llm-for-vscode/backend/main.py', 'r', encoding='utf-8') as f:
    source = f.read()

tree = ast.parse(source)

# 找所有函数
for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef):
        if 'handle_request' in node.name:
            print(f"Found function: {node.name}")
            
            # 遍历 if 语句
            for stmt in node.body:
                if isinstance(stmt, ast.If):
                    print(f"  Found if statement")
                    # 检查条件
                    test = stmt.test
                    print(f"  Test type: {type(test).__name__}")
                    
                    if isinstance(test, ast.Compare):
                        print(f"    Compare ops: {[type(o).__name__ for o in test.ops]}")
                        if test.ops and isinstance(test.ops[0], ast.Eq):
                            left = test.left
                            right = test.comparators[0]
                            print(f"    Left: {type(left).__name__}")
                            print(f"    Right: {type(right).__name__}, value: {getattr(right, 'value', 'N/A')}")
                            
                            # 检查 body
                            print(f"    Body has {len(stmt.body)} statements")
                            for b in stmt.body[:2]:
                                print(f"      Body stmt: {type(b).__name__}")
                                if isinstance(b, ast.Expr) and isinstance(b.value, ast.Await):
                                    print(f"        Await found!")
                                    if isinstance(b.value.value, ast.Call):
                                        call = b.value.value
                                        print(f"        Call func type: {type(call.func).__name__}")
                                        if isinstance(call.func, ast.Attribute):
                                            print(f"        Attr: {call.func.attr}")
            break
