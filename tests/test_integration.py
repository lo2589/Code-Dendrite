"""集成测试 - 验证 dispatch 边生成"""
import sys
sys.path.insert(0, '.')
from relate.api.relations import generate_relations, load_relations, filter_edges_by_keyword, count_edge_types

# 对 backend 目录生成 relations
result = generate_relations('../backend')
print('Generate result:', result)

# 加载并检查 dispatch 边
data = load_relations('../backend')
dispatch_edges = [e for e in data['edges'] if e.get('edge_type') == 'dispatch']
print(f'Found {len(dispatch_edges)} dispatch edges')

# 显示前几条 dispatch 边
for e in dispatch_edges[:5]:
    print(f"  {e['from_id']} --[{e.get('dispatch_key')}={e.get('dispatch_value')}]--> {e['to_id']}")

# 统计
print('Edge types:', count_edge_types('../backend'))

# 测试 filter_edges_by_keyword
chat_edges = filter_edges_by_keyword('chat', '../backend')
print(f'Edges with "chat": {len(chat_edges)}')
