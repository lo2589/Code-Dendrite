"""
integration_test.py — 端到端集成测试

验证完整链路：
    代码库 → 锚点 → 压缩地图 → AI 导航 → 路径追踪 → 节点替换

用法：
    python integration_test.py --project /path/to/project
    python integration_test.py --project . --quick   # 只跑冒烟测试
"""

import sys
import json
import time
import argparse
from pathlib import Path

# 把模块路径加入
_MODULES_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_MODULES_ROOT))
sys.path.insert(0, str(_MODULES_ROOT / "codedendrite"))
sys.path.insert(0, str(_MODULES_ROOT / "codedendrite_ext"))


def test_calls_extractor(project_root: str, verbose: bool = False) -> bool:
    """测试 calls_extractor 能正确补全 metadata.calls。"""
    print("\n[测试 1] calls_extractor — 补全 metadata.calls")
    try:
        from codeGenome_patch.calls_extractor import extract_calls_python

        # 用一段已知代码测试
        sample = '''
def handle_request(request):
    user = validate_user(request.user_id)
    result = process_action(user, request.action)
    return format_response(result)
'''
        calls = extract_calls_python(sample)
        expected = {"validate_user", "process_action", "format_response"}
        missing = expected - set(calls)

        if missing:
            print(f"  ✗ 未提取到: {missing}")
            return False

        print(f"  ✓ 提取调用: {calls}")
        return True

    except Exception as e:
        print(f"  ✗ 异常: {e}")
        return False


def test_context_builder(project_root: str, verbose: bool = False) -> bool:
    """测试 context_builder 能生成有效的压缩地图。"""
    print("\n[测试 2] context_builder — 生成压缩地图")
    try:
        from context_builder import ContextBuilder, SymbolExpander

        cb = ContextBuilder(project_root=project_root, max_tokens=1000)
        t0 = time.time()
        map_text = cb.build_map()
        elapsed_ms = int((time.time() - t0) * 1000)

        # 检查地图包含基本结构
        checks = [
            ("## Entry Points" in map_text or "## Module" in map_text, "包含地图节"),
            (len(map_text) > 50, "地图非空"),
            (elapsed_ms < 5000, f"生成速度 {elapsed_ms}ms < 5000ms"),
        ]

        all_pass = True
        for ok, desc in checks:
            status = "✓" if ok else "✗"
            print(f"  {status} {desc}")
            if not ok:
                all_pass = False

        if verbose:
            print("\n  地图预览（前 300 字符）:")
            print("  " + map_text[:300].replace("\n", "\n  "))

        # 测试 expander
        expander = SymbolExpander(project_root=project_root)
        stats = cb.get_stats()
        print(f"  ✓ 锚点总数: {stats.get('total_anchors', 0)}")

        return all_pass

    except Exception as e:
        print(f"  ✗ 异常: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return False


def test_path_tracer(project_root: str, verbose: bool = False) -> bool:
    """测试 pathTracer 链式接口。"""
    print("\n[测试 3] pathTracer — 路径追踪")
    try:
        from pathTracer import PathTracer
        from pathTracer.node import PipelineNode

        tracer = PathTracer(project_root=project_root, max_depth=5)

        # 测试 get_pipeline（即使锚点 calls 为空也应该返回至少入口节点）
        nodes = tracer.get_pipeline("analyze_error")
        print(f"  ✓ get_pipeline 返回 {len(nodes)} 个节点")

        # 测试链式接口
        result = (
            tracer
            .from_entry("analyze_error")
            .given("error_type", "ImportError")
            .run()
        )

        checks = [
            (len(result.nodes) >= 0, "run() 正常返回"),
            (result.entry == "analyze_error", "入口设置正确"),
            (result.conditions == {"error_type": "ImportError"}, "条件保留"),
        ]

        all_pass = True
        for ok, desc in checks:
            status = "✓" if ok else "✗"
            print(f"  {status} {desc}")
            if not ok:
                all_pass = False

        # 测试 Mermaid 输出
        mermaid = result.to_mermaid()
        print(f"  ✓ to_mermaid() 返回 {len(mermaid)} 字符")

        # 测试 Pipeline JSON
        pipeline = result.to_pipeline()
        data = json.loads(pipeline)
        print(f"  ✓ to_pipeline() 包含 {len(data['nodes'])} 节点, {len(data['edges'])} 边")

        return all_pass

    except Exception as e:
        print(f"  ✗ 异常: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return False


def test_anchor_memory(project_root: str, verbose: bool = False) -> bool:
    """测试 anchorMemory 积累机制。"""
    print("\n[测试 4] anchorMemory — 情节记忆")
    try:
        import tempfile
        import os
        from anchorMemory import AnchorMemory

        # 用临时目录，避免污染真实项目
        with tempfile.TemporaryDirectory() as tmp:
            mem = AnchorMemory(project_root=tmp)
            anchor_id = "test.Module.func"

            # 测试 pending 积累
            r1 = mem.observe(anchor_id, "观察1", source="ai_single", confidence=0.7)
            r2 = mem.observe(anchor_id, "观察2", source="ai_single", confidence=0.75)
            # 前两次不应固化
            assert not r1, "第1次不应固化"
            assert not r2, "第2次不应固化"
            print(f"  ✓ pending 积累机制正常")

            # 第3次应固化
            r3 = mem.observe(anchor_id, "观察3", source="ai_single", confidence=0.72)
            assert r3, "第3次应固化"
            print(f"  ✓ 第3次观察固化成功")

            # 测试 human 直接固化
            mem.observe(anchor_id, "人类描述", source="human", confidence=1.0)
            conf = mem.get_confidence(anchor_id)
            assert conf > 0.5, f"human 固化后 confidence 应 > 0.5，实际: {conf}"
            print(f"  ✓ human 直接固化，confidence: {conf:.2f}")

            # 测试 milestone
            mem.record_milestone(anchor_id, "bug_fix", "修复边界条件")
            entry = mem.get(anchor_id)
            assert entry.bug_count == 1
            assert len(entry.milestones) == 1
            print(f"  ✓ milestone 记录正常")

            # 测试 behavior_pattern
            mem.add_behavior_pattern(anchor_id, "admin", "跳过验证", confidence=0.9)
            entry = mem.get(anchor_id)
            assert len(entry.behavior_patterns) == 1
            print(f"  ✓ behavior_pattern 记录正常")

            # 测试保存和加载
            mem.save()
            mem2 = AnchorMemory(project_root=tmp)
            entry2 = mem2.get(anchor_id)
            assert entry2 is not None
            assert entry2.bug_count == 1
            print(f"  ✓ 持久化保存和加载正常")

            # 测试 summary
            summary = mem.get_summary(anchor_id)
            assert anchor_id in summary or "记忆" in summary
            print(f"  ✓ summary 生成正常")

        return True

    except AssertionError as e:
        print(f"  ✗ 断言失败: {e}")
        return False
    except Exception as e:
        print(f"  ✗ 异常: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return False


def test_smart_analyzer_v2(project_root: str, verbose: bool = False) -> bool:
    """测试 SmartCodeAnalyzerV2 集成。"""
    print("\n[测试 5] SmartCodeAnalyzerV2 — 完整集成")
    try:
        from smartAnalyzer_patch.smart_analyzer_patch import SmartCodeAnalyzerV2

        analyzer = SmartCodeAnalyzerV2(project_root=project_root)

        # 测试 get_ai_context
        ctx = analyzer.get_ai_context(budget_tokens=500, include_memory=False)
        print(f"  ✓ get_ai_context() 返回 {len(ctx)} 字符")

        # 测试 search_symbol
        results = analyzer.search_symbol("analyze")
        print(f"  ✓ search_symbol('analyze') 找到 {len(results)} 个候选")

        # 测试 trace_path
        path = analyzer.trace_path("analyze_error", output="text")
        print(f"  ✓ trace_path() 返回 {len(path)} 字符")

        # 测试 get_pipeline
        pipeline = analyzer.get_pipeline("analyze_error")
        print(f"  ✓ get_pipeline() 返回 {len(pipeline)} 个节点")

        # 测试 analyze_error
        report = analyzer.analyze_error(
            "AttributeError: 'NoneType' object has no attribute 'name'",
        )
        print(f"  ✓ analyze_error() 返回 {len(report)} 字符")

        # 测试 observe
        solidified = analyzer.observe("analyze_error", "测试观察", source="ai_single")
        print(f"  ✓ observe() 执行完成，固化: {solidified}")

        # 测试 get_cache_stats
        stats = analyzer.get_cache_stats()
        assert "project_stats" in stats
        print(f"  ✓ get_cache_stats() 正常")

        return True

    except Exception as e:
        print(f"  ✗ 异常: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        return False


def run_all_tests(project_root: str, quick: bool = False, verbose: bool = False):
    """运行所有测试，输出汇总报告。"""
    print(f"\n{'='*60}")
    print(f"CodeDendrite 集成测试")
    print(f"项目: {project_root}")
    print(f"{'='*60}")

    tests = [
        ("calls_extractor", test_calls_extractor),
        ("context_builder", test_context_builder),
        ("pathTracer", test_path_tracer),
        ("anchorMemory", test_anchor_memory),
    ]

    if not quick:
        tests.append(("SmartCodeAnalyzerV2", test_smart_analyzer_v2))

    results = {}
    for name, test_fn in tests:
        try:
            results[name] = test_fn(project_root, verbose=verbose)
        except Exception as e:
            print(f"\n[{name}] 未捕获异常: {e}")
            results[name] = False

    print(f"\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, ok in results.items():
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status}  {name}")

    print(f"\n{passed}/{total} 通过")
    return passed == total


def main():
    parser = argparse.ArgumentParser(description="CodeDendrite 集成测试")
    parser.add_argument("--project", default=".", help="项目根目录")
    parser.add_argument("--quick", action="store_true", help="只运行冒烟测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    project_root = str(Path(args.project).resolve())
    success = run_all_tests(project_root, quick=args.quick, verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
