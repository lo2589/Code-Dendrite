"""
query.py — CodeDendrite 查询 CLI
================================
用法:
    python api/query.py edges <keyword>          # 过滤边
    python api/query.py count                    # 统计边类型
    python api/query.py expand <node_id>         # 展开节点
    python api/query.py anchors <keyword>        # 过滤锚点
    python api/query.py fileanchors <file>       # 列出单个文件内的 anchors
    python api/query.py graph [focus] [radius]   # 生成交互式关系图
    python api/query.py timeline <entry> [depth]  # 生成调用链时间线
    python api/query.py codemap                  # 生成代码地图
"""
import sys
import os

from api.query.rank_anchor_matches import _rank_anchor_matches

def _ensure_path():
    api_dir = os.path.dirname(os.path.abspath(__file__))
    codedendrite_root = os.path.dirname(api_dir)
    codedendrite_parent = os.path.dirname(os.path.dirname(codedendrite_root))
    for p in (codedendrite_parent, codedendrite_root):
        if p not in sys.path:
            sys.path.insert(0, p)

def cmd_edges(keyword: str, root: str = "."):
    from api.relations import filter_edges_by_keyword
    edges = filter_edges_by_keyword(keyword, root)
    print(f"Found {len(edges)} edges with keyword '{keyword}':")
    for e in edges[:20]:
        src = e['from_id'].split('::')[-1]
        dst = e['to_id'].split('::')[-1]
        etype = e.get('edge_type', '?')
        print(f"  {src} --[{etype}]--> {dst}")
    if len(edges) > 20:
        print(f"  ... and {len(edges) - 20} more")
    if not edges:
        from analyzer.anchors import resolve_anchor_candidates
        from api.inspector import find_attribute_call_sites

        methods = [
            anchor
            for anchor in resolve_anchor_candidates(keyword, root)
            if anchor.symbol_type == "method" or "." in anchor.symbol
        ]
        if methods:
            print("\nCoverage warning: 0 indexed edges does not prove this method is unused.")
            print("Calls through variables (obj.method(...)) may be statically unresolved.")
            if len(methods) > 1:
                print("Matching method definitions:")
                for anchor in sorted(methods, key=lambda item: item.id):
                    print(f"  {anchor.id}  {anchor.file}:{anchor.line_start}")
            sites = find_attribute_call_sites(keyword.rsplit(".", 1)[-1], root)
            if sites:
                print(f"Possible unresolved attribute calls ({len(sites)} shown):")
                for site in sites:
                    print(
                        "  {file}:{line}  {receiver}.{method}(...)".format(
                            method=keyword.rsplit(".", 1)[-1],
                            **site,
                        )
                    )

def cmd_count(root: str = "."):
    from api.relations import count_edge_types
    counts = count_edge_types(root)
    print("Edge type counts:")
    for etype, count in sorted(counts.items()):
        print(f"  {etype}: {count}")

def cmd_expand(node_id: str, root: str = "."):
    from api.relations import expand_node
    result = expand_node(node_id, root, radius=1)
    print(f"Node: {result.get('id', '?')}")
    edges = result.get('edges', [])
    print(f"Related edges: {len(edges)}")
    for e in edges[:20]:
        target = e.get('target', {})
        tid = target.get('id', '?')
        etype = e.get('edge_type', '?')
        direction = e.get('direction', '?')
        print(f"  [{direction}] --[{etype}]--> {tid}")
    if len(edges) > 20:
        print(f"  ... and {len(edges) - 20} more")

def cmd_anchors(keyword: str, root: str = "."):
    from analyzer.anchors import load_anchors
    matches = _rank_anchor_matches(load_anchors(root), keyword)
    print(f"Found {len(matches)} anchors matching symbol or file '{keyword}':")
    for aid, a in matches[:20]:
        sym = a.symbol if hasattr(a, 'symbol') else a.get('symbol', '?')
        ftype = a.symbol_type if hasattr(a, 'symbol_type') else a.get('symbol_type', '?')
        fpath = (a.file if hasattr(a, 'file') else a.get('file', '')).replace('\\', '/')
        line = a.line_start if hasattr(a, 'line_start') else a.get('line_start', '')
        print(f"  [{aid}] {ftype:8s} {sym:40s} {fpath}:{line}")
    if len(matches) > 20:
        print(f"  ... and {len(matches) - 20} more")

def cmd_fileanchors(file_path: str, root: str = ".", include_virtual: bool = False):
    from analyzer.anchors import list_anchors_in_file

    anchors = list_anchors_in_file(file_path, root=root, include_virtual=include_virtual)
    items = sorted(
        anchors.items(),
        key=lambda item: (
            getattr(item[1], "line_start", item[1].get("line_start", 0) if isinstance(item[1], dict) else 0),
            getattr(item[1], "symbol", item[1].get("symbol", "") if isinstance(item[1], dict) else ""),
        ),
    )

    print(f"Anchors in file '{file_path}' ({len(items)} total):")
    for aid, anchor in items:
        sym = anchor.symbol if hasattr(anchor, "symbol") else anchor.get("symbol", "?")
        stype = anchor.symbol_type if hasattr(anchor, "symbol_type") else anchor.get("symbol_type", "?")
        line = anchor.line_start if hasattr(anchor, "line_start") else anchor.get("line_start", "")
        extra = ""
        if (anchor.is_virtual if hasattr(anchor, "is_virtual") else anchor.get("is_virtual", False)):
            extra = " [virtual]"
        print(f"  {line:>4}  {stype:12s}  {sym}{extra}")

    if items:
        print("\nCut on demand:")
        for aid, _ in items[:10]:
            print(f"  python api/query.py expand \"{aid}\" {root}")

def cmd_map(mode: str = "compact", root: str = "."):
    """生成模块依赖缩略图。
    
    mode: 'compact' - 压缩态（模块名+边数）
         'full' - 全态（包含功能描述）
    """
    from analyzer.anchors import load_anchors
    from api.relations import load_relations
    from collections import defaultdict
    
    relations = load_relations(root)
    edges = relations.get('edges', [])
    anchors = load_anchors(root)
    
    # 按文件统计边数
    file_edges = defaultdict(lambda: {'in': 0, 'out': 0})
    for e in edges:
        from_file = e['from_id'].split('/')[0] if '/' in e['from_id'] else e['from_id'].split('\\')[0]
        to_file = e['to_id'].split('/')[0] if '/' in e['to_id'] else e['to_id'].split('\\')[0]
        file_edges[from_file]['out'] += 1
        file_edges[to_file]['in'] += 1
    
    # 排序
    sorted_files = sorted(file_edges.items(), key=lambda x: x[1]['out'] + x[1]['in'], reverse=True)
    
    print(f"模块依赖缩略图 (mode={mode}, {len(sorted_files)} 模块, {len(edges)} 边)")
    print("=" * 70)
    
    if mode == "compact":
        for fname, counts in sorted_files[:15]:
            total = counts['in'] + counts['out']
            print(f"  {fname}: {total}边 (in={counts['in']}, out={counts['out']})")
    else:
        # full mode: 包含锚点数量
        for fname, counts in sorted_files[:15]:
            anchor_count = sum(1 for a in anchors.values() if fname in (a.file if hasattr(a, 'file') else a.get('file', '')))
            total = counts['in'] + counts['out']
            print(f"  {fname}: {total}边, {anchor_count}锚点 (in={counts['in']}, out={counts['out']})")

def cmd_graph(focus: str = None, root: str = ".", radius: int = 2):
    """生成交互式关系图 HTML"""
    from view.relations import generate_relation_graph
    output = generate_relation_graph(root, focus=focus, radius=radius)
    print(f"Open in browser: {output}")

def cmd_timeline(entry: str, root: str = ".", depth: int = 5, error: str = None):
    """生成调用链时间线 HTML"""
    from view.timeline import generate_call_timeline
    output = generate_call_timeline(root, entry, max_depth=depth, error_symbol=error)
    print(f"Open in browser: {output}")

def cmd_codemap(root: str = "."):
    """生成代码地图 HTML"""
    from view.code_map import generate_code_map
    output = generate_code_map(root)
    print(f"Open in browser: {output}")

def cmd_chain(symbol: str, root: str = ".", depth: int = 10, direction: str = "down",
              yaml_path: str = None):
    """从 symbol 出发输出完整调用链 anchor 列表。

    用法：
      python -m serve.api.query chain <symbol> <root> [--depth N] [--direction down|up] [--yaml FILE]
    """
    from analyzer.anchors import resolve_anchor_candidates
    from api.inspector import (
        find_attribute_call_sites,
        get_downward_chain,
        get_upward_chain,
    )

    candidates = [
        anchor
        for anchor in resolve_anchor_candidates(symbol, root)
        if not anchor.is_virtual
    ]
    if not candidates:
        print("No anchor found for: {}".format(symbol), file=sys.stderr)
        return 1
    unique = {anchor.id: anchor for anchor in candidates}
    if len(unique) > 1:
        print(
            "Ambiguous symbol '{}'; no chain was guessed. Use a full anchor ID:".format(symbol),
            file=sys.stderr,
        )
        for anchor_id in sorted(unique):
            anchor = unique[anchor_id]
            print(
                "  {}  {}:{}".format(anchor_id, anchor.file, anchor.line_start),
                file=sys.stderr,
            )
        return 2

    entry_anchor = next(iter(unique.values()))
    canonical_symbol = entry_anchor.id

    active_keys = None
    profile = None
    if yaml_path:
        from analyzer.anchors import load_anchors
        from usage.profiles.yaml_profile import active_registered_keys, load_yaml_profile, yaml_component_graph
        try:
            indexed_anchors = load_anchors(root)
            profile = load_yaml_profile(yaml_path, root, indexed_anchors)
        except (OSError, ValueError) as exc:
            print("YAML profile error: {}".format(exc), file=sys.stderr)
            return 3
        active_keys = active_registered_keys(indexed_anchors, profile)
        yaml_components = yaml_component_graph(indexed_anchors, profile)
    else:
        yaml_components = []

    if direction == "up":
        chain = get_upward_chain(canonical_symbol, root, max_depth=depth)
    else:
        chain = get_downward_chain(
            canonical_symbol,
            root,
            max_depth=depth,
            active_registry_keys=active_keys,
            yaml_profile=profile,
        )

    if not chain:
        print("No chain found for: {}".format(symbol))
        return 1

    print("Chain from '{}' ({} entries, direction={}):\n".format(symbol, len(chain), direction))
    if profile is not None:
        print("YAML profile: {} via {} ({} active registry keys)\n".format(
            profile["path"], profile["loader"], len(active_keys or ()),
        ))
        print("YAML selected: {}\n".format(", ".join(sorted(active_keys or ())) or "(none)"))
        if yaml_components:
            print("YAML component graph ({} layers):".format(len(yaml_components)))
            for component in yaml_components:
                target = component.get("anchor_id") or "<{}>".format(component["resolution"])
                print("  [Y{}] {} x{} <- {}  {}  [YAML → {}]".format(
                    component["index"],
                    component["component"] + "*",
                    component["repeats"],
                    component["from"],
                    target,
                    component["path"],
                ))
            print()
    for entry in chain:
        indent = "  " * entry.get("depth", 0)
        file_loc = "{}:{}".format(entry.get("file") or "?", entry.get("line") or "?")
        yaml_marker = ""
        display_symbol = entry["symbol"]
        if entry.get("yaml_selected"):
            display_symbol += "*"
            yaml_marker = "  [YAML → {}]".format(entry.get("registry_key"))
        # 基础节点：被足够多的东西调用，是公共底座而不是业务链的中间环节，
        # 上行到此为止。这里标出来，省得看的人以为链断了。
        base_marker = ""
        if entry.get("is_base"):
            base_marker = "  [基础节点 ← 被 {} 处调用，不再上行]".format(
                entry.get("caller_count", 0),
            )
        print("{}[{}] {}  {}{}{}".format(
            indent, entry.get("depth", 0), display_symbol, file_loc,
            yaml_marker, base_marker,
        ))

    is_method = entry_anchor.symbol_type == "method" or "." in entry_anchor.symbol
    if direction == "up" and is_method:
        print("\nCoverage: statically resolved callers only; calls through variables may be missing.")
        if len(chain) == 1:
            print("No statically resolved callers. This does not prove the method is unused.")
            method_name = entry_anchor.symbol.rsplit(".", 1)[-1]
            sites = find_attribute_call_sites(method_name, root)
            if sites:
                print(f"Possible unresolved attribute calls ({len(sites)} shown):")
                for site in sites:
                    print(
                        "  {file}:{line}  {receiver}.{method}(...)".format(
                            method=method_name,
                            **site,
                        )
                    )
    return 0

def cmd_registered(root: str = ".", decorator: str = None):
    """列出所有有 registered_as 的 anchor。

    每行格式：
      decorator_name  registered_key  file:line  symbol

    用法：
      python -m serve.api.query registered <root>
      python -m serve.api.query registered <root> --decorator register_io
    """
    from analyzer.anchors import load_anchors

    anchors = load_anchors(root)
    results = []
    for anchor in anchors.values():
        decs = anchor.block_metadata.get("decorators", [])
        entries = [
            (str(item.get("name") or "?"), str(item.get("key") or ""))
            for item in decs
            if isinstance(item, dict) and item.get("key")
        ]
        if anchor.registered_as and not any(key == anchor.registered_as for _, key in entries):
            entries.append(("?", anchor.registered_as))
        for dec_name, registered_key in entries:
            if decorator and dec_name != decorator:
                continue
            results.append((
                dec_name, registered_key, anchor.file, anchor.line_start, anchor.symbol,
            ))

    results.sort(key=lambda r: (r[0], r[2], r[3]))
    print("{:<20} {:<30} {}".format("decorator", "registered_as", "location  symbol"))
    print("-" * 80)
    for dec_name, reg_as, file, line, symbol in results:
        print("{:<20} {:<30} {}:{} {}".format(dec_name, reg_as, file, line, symbol))
    print("\nTotal: {}".format(len(results)))

_ensure_path()
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    root = "."

    if cmd == "edges" and len(sys.argv) >= 3:
        keyword = sys.argv[2]
        root = sys.argv[3] if len(sys.argv) >= 4 else "."
        cmd_edges(keyword, root)
    elif cmd == "count":
        root = sys.argv[2] if len(sys.argv) >= 3 else "."
        cmd_count(root)
    elif cmd == "expand" and len(sys.argv) >= 3:
        node_id = sys.argv[2]
        root = sys.argv[3] if len(sys.argv) >= 4 else "."
        cmd_expand(node_id, root)
    elif cmd == "anchors" and len(sys.argv) >= 3:
        keyword = sys.argv[2]
        root = sys.argv[3] if len(sys.argv) >= 4 else "."
        cmd_anchors(keyword, root)
    elif cmd == "fileanchors" and len(sys.argv) >= 3:
        file_path = sys.argv[2]
        root = "."
        include_virtual = False
        positional = []
        for arg in sys.argv[3:]:
            if arg == "--with-virtual":
                include_virtual = True
            else:
                positional.append(arg)
        if positional:
            root = positional[0]
        cmd_fileanchors(file_path, root, include_virtual)
    elif cmd == "map":
        mode = sys.argv[2] if len(sys.argv) >= 3 else "compact"
        root = sys.argv[3] if len(sys.argv) >= 4 else "."
        cmd_map(mode, root)
    elif cmd == "graph":
        focus = None
        root = "."
        radius = 2
        args = iter(sys.argv[2:])
        for arg in args:
            if arg == "--radius":
                radius = int(next(args))
            elif arg == "--root":
                root = next(args)
            elif not arg.startswith("--") and focus is None:
                focus = arg
        cmd_graph(focus, root, radius)
    elif cmd == "timeline" and len(sys.argv) >= 3:
        entry = sys.argv[2]
        root = sys.argv[3] if len(sys.argv) >= 4 and not sys.argv[3].startswith("--") else "."
        depth = 5
        error = None
        for i, a in enumerate(sys.argv):
            if a == "--depth" and i + 1 < len(sys.argv):
                depth = int(sys.argv[i + 1])
            if a == "--error" and i + 1 < len(sys.argv):
                error = sys.argv[i + 1]
        cmd_timeline(entry, root, depth, error)
    elif cmd == "codemap":
        root = sys.argv[2] if len(sys.argv) >= 3 else "."
        cmd_codemap(root)
    elif cmd == "chain" and len(sys.argv) >= 3:
        symbol = sys.argv[2]
        root = "."
        depth = 10
        direction = "down"
        yaml_path = None
        positional = []
        for i, a in enumerate(sys.argv[3:], 3):
            if a == "--depth" and i + 1 < len(sys.argv):
                depth = int(sys.argv[i + 1])
            elif a == "--direction" and i + 1 < len(sys.argv):
                direction = sys.argv[i + 1]
            elif a == "--yaml" and i + 1 < len(sys.argv):
                yaml_path = sys.argv[i + 1]
            elif not a.startswith("--") and sys.argv[i - 1] not in ("--depth", "--direction", "--yaml"):
                positional.append(a)
        if positional:
            root = positional[0]
        sys.exit(cmd_chain(symbol, root, depth, direction, yaml_path))
    elif cmd == "chain2context" and len(sys.argv) >= 3:
        symbol = sys.argv[2]
        root = "."
        depth = 6
        direction = "down"
        budget = 60000
        output = None
        context_lines = 0
        flags = {"--depth", "--direction", "--budget", "--output", "--context"}
        positional = []
        for i, a in enumerate(sys.argv[3:], 3):
            if a == "--depth" and i + 1 < len(sys.argv):
                depth = int(sys.argv[i + 1])
            elif a == "--direction" and i + 1 < len(sys.argv):
                direction = sys.argv[i + 1]
            elif a == "--budget" and i + 1 < len(sys.argv):
                budget = int(sys.argv[i + 1])
            elif a == "--output" and i + 1 < len(sys.argv):
                output = sys.argv[i + 1]
            elif a == "--context" and i + 1 < len(sys.argv):
                context_lines = int(sys.argv[i + 1])
            elif not a.startswith("--") and sys.argv[i - 1] not in flags:
                positional.append(a)
        if positional:
            root = positional[0]
        from api.query.chain_context import cmd_chain_context
        sys.exit(cmd_chain_context(symbol, root, depth, direction, budget,
                                   output, context_lines))
    elif cmd == "registered":
        root = "."
        decorator = None
        positional = []
        for i, a in enumerate(sys.argv[2:], 2):
            if a == "--decorator" and i + 1 < len(sys.argv):
                decorator = sys.argv[i + 1]
            elif not a.startswith("--"):
                positional.append(a)
        if positional:
            root = positional[0]
        cmd_registered(root, decorator)
    else:
        print(__doc__)
        sys.exit(1)
