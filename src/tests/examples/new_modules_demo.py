"""
CodeDendrite 新模块使用示例
演示三个核心模块：context_builder、pathTracer、anchorMemory
"""

import sys
from pathlib import Path

# 添加路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "tools" / "CodeDendrite"))

print("=" * 80)
print("🔍 CodeDendrite 新模块演示")
print("=" * 80)

# ═══════════════════════════════════════════════════════════
# 1. context_builder - 压缩地图
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("📦 模块 1: context_builder（压缩地图）")
print("=" * 80)

try:
    from usage.structure.context_builder.builder import build_context
    from usage.structure.context_builder.expander import expand_symbol
    
    print("\n✅ 导入成功")
    print("\n📖 使用方式:")
    print("""
    # 第一步：生成压缩地图（200行）
    context = build_context(
        project_root="/path/to/project",
        token_budget=8000,
        sections=["entry_points", "module_responsibilities", "hot_spots"]
    )
    
    print(context.summary)  # 200 行压缩地图
    print(f"锚点数: {context.total_anchors}")
    print(f"Token 使用: {context.token_count}")
    
    # 第二步：AI 说"我要看这个符号" → 精准展开
    detail = expand_symbol(
        project_root="/path/to/project",
        symbol="handle_request",
        include_code=True
    )
    
    print(detail.code)  # 完整代码
    print(detail.calls)  # 调用关系
    """)
    
except Exception as e:
    print(f"❌ 导入失败: {e}")

# ═══════════════════════════════════════════════════════════
# 2. pathTracer - 管线追踪
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("📦 模块 2: pathTracer（管线追踪）")
print("=" * 80)

try:
    from analyzer.path.tracer import PathTracer, trace_path
    
    print("\n✅ 导入成功")
    print("\n📖 使用方式:")
    print("""
    # 链式接口：条件剪枝，不穷举路径
    tracer = PathTracer(project_root="/path/to/project")
    
    result = tracer.from_entry("handle_request") \\
                  .given("request.type", "A") \\
                  .until("db.save") \\
                  .run()
    
    print(result.summary)  # 路径摘要
    print(result.to_mermaid())  # Mermaid 图
    
    # 节点替换兼容性检查
    from analyzer.path.replacer import replace_node
    
    plan = replace_node(
        project_root="/path/to/project",
        old_node="old_function",
        new_node="new_function"
    )
    
    print(f"风险等级: {plan.risk_level}")
    print(f"兼容: {plan.compatible}")
    """)
    
except Exception as e:
    print(f"❌ 导入失败: {e}")

# ═══════════════════════════════════════════════════════════
# 3. anchorMemory - 情节记忆
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("📦 模块 3: anchorMemory（情节记忆）")
print("=" * 80)

try:
    from analyzer.repair.anchor_memory.memory import AnchorMemory, record_observation
    
    print("\n✅ 导入成功")
    print("\n📖 使用方式:")
    print("""
    # 记录观察（不会每次都写，有写入条件控制）
    record_observation(
        anchor_id="main.handle_request",
        event_type="access_pattern",
        data={"frequency": 42, "avg_latency": 120}
    )
    
    # 自动积累观察，计算 confidence
    memory = AnchorMemory(project_root="/path/to/project")
    entry = memory.get("main.handle_request")
    
    print(f"Confidence: {entry.confidence}")
    print(f"Milestones: {entry.milestones}")
    print(f"Patterns: {entry.behavior_patterns}")
    
    # 状态机：不是 log，是情节记忆
    # low_confidence → accumulating → stable → verified
    """)
    
except Exception as e:
    print(f"❌ 导入失败: {e}")

# ═══════════════════════════════════════════════════════════
# 4. SmartCodeAnalyzerV2 - 集成入口
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("📦 模块 4: SmartCodeAnalyzerV2（统一入口）")
print("=" * 80)

try:
    from usage.analyze.smart_analyzer.smart_analyzer_patch import SmartCodeAnalyzerV2
    
    print("\n✅ 导入成功")
    print("\n📖 使用方式:")
    print("""
    analyzer = SmartCodeAnalyzerV2("/path/to/project")
    
    # 生成压缩地图
    context = analyzer.get_ai_context(task="分析项目源码")
    print(context)  # 200 行地图
    
    # 按需展开符号
    detail = analyzer.expand_symbol("handle_request")
    print(detail)  # 精准代码
    
    # 路径追踪
    path = analyzer.trace_path(
        from_node="handle_request",
        to_node="db.save",
        output_format="mermaid"
    )
    print(path)  # Mermaid 图
    
    # 节点替换
    plan = analyzer.replace_node("old_func", "new_func")
    print(f"风险: {plan.risk_level}")
    
    # 错误分析（增强版）
    report = analyzer.analyze_error(
        error="TypeError: 'NoneType'",
        file="main.py",
        severity="high"
    )
    print(report.suggestions)  # L1-L4 渐进诊断
    """)
    
except Exception as e:
    print(f"❌ 导入失败: {e}")

# ═══════════════════════════════════════════════════════════
# 5. 完整工作流示例
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("🚀 完整工作流示例")
print("=" * 80)

print("""
# 步骤 1: 先跑 calls_extractor.py 补全调用图数据
# bash
# python codeGenome/calls_extractor.py --project /your/project --dry-run
# python codeGenome/calls_extractor.py --project /your/project

# 步骤 2: 跑集成测试验证
# bash
# python integration_test.py --project /your/project

# 步骤 3: 在实际中使用
from tools.CodeDendrite import SmartCodeAnalyzerV2

analyzer = SmartCodeAnalyzerV2("/path/to/project")

# AI 第一步：获取压缩地图
context = analyzer.get_ai_context("分析项目源码")
# → 返回 200 行地图，包含入口点、模块职责、热点

# AI 第二步：需要看某个符号的细节
detail = analyzer.expand_symbol("handle_request")
# → 精准返回代码和调用关系

# AI 第三步：追踪数据流
path = analyzer.trace_path(
    from_node="handle_request",
    given={"request.type": "A"},
    until="db.save"
)
# → 返回条件剪枝后的路径

# AI 第四步：发现需要替换节点
plan = analyzer.replace_node("old_auth", "new_auth")
# → 自动检查兼容性，生成替换方案，记录到 memory
""")

print("=" * 80)
print("✅ 所有新模块已整合完成！")
print("=" * 80)
