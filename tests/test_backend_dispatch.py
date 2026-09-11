"""测试实际 backend 代码的 dispatch 边提取"""
import sys
sys.path.insert(0, '.')
from parse.codeGenome.string_dispatch import find_string_dispatches

# 对 backend 目录提取 dispatch 边
dispatches = find_string_dispatches('../backend')
print(f'Found {len(dispatches)} dispatch edges')

# 显示所有 dispatch 边
for d in dispatches[:20]:
    print(f"  {d['from_id']}")
    print(f"    --[{d['dispatch_key']} == \"{d['dispatch_value']}\"]-->")
    print(f"    {d['to_id']}")
    print()
