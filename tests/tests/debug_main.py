"""调试 dispatch 边提取"""
import ast
import sys
sys.path.insert(0, '.')
from parse.codeGenome.string_dispatch import extract_dispatches_from_file

# 直接测试 backend/main.py
file_path = '../backend/main.py'
edges = extract_dispatches_from_file(file_path, '..')
print(f'Found {len(edges)} dispatch edges in main.py')

for e in edges[:10]:
    print(f"  {e['from_id']}")
    print(f"    --[{e['dispatch_key']} == \"{e['dispatch_value']}\"]-->")
    print(f"    {e['to_id']}")
    print()
