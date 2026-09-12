"""
Module Tree V2 Smoke 测试
========================
分两层:
  1. 通用性质测试 — 不依赖当前仓库，用 fixture 验证结构规则
  2. 当前仓库回归测试 — 用真实数据验证已知错误不复发

运行:
    cd tools/CodeDendrite
    PYTHONPATH=. python -m pytest tests/test_module_tree_v2_smoke.py -v
    # 或直接运行
    PYTHONPATH=. python tests/test_module_tree_v2_smoke.py
"""

import json
import sys
import os
from pathlib import Path

# 确保 CodeDendrite 根目录在 sys.path
_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from usage.path_policy import (
    PathPolicy,
    load_path_policy,
    classify_path_role,
    normalize_project_path,
)
from usage.structure.capability_candidates import build_capability_candidates
from usage.structure.module_tree_v2 import generate_module_tree_v2, save_module_tree_v2


# ══════════════════════════════════════════════════════════════════
# 第一层: 通用性质测试
# ══════════════════════════════════════════════════════════════════

class TestPathPolicyProperties:
    """path_policy 通用性质测试。"""

    def test_classify_deterministic(self):
        """同一路径多次分类结果稳定。"""
        policy = load_path_policy(".")
        for _ in range(10):
            assert classify_path_role("api/module_tree.py", policy) == "normal"
            assert classify_path_role("tests/test_foo.py", policy) == "reference_only"
            assert classify_path_role(".codedendrite/anchors.json", policy) == "exclude"

    def test_exclude_patterns(self):
        """已知排除路径正确分类。"""
        policy = load_path_policy(".")
        excludes = [
            "__pycache__/foo.pyc",
            "node_modules/bar/index.js",
            ".git/objects/abc",
            ".codedendrite/anchors.json",
        ]
        for p in excludes:
            assert classify_path_role(p, policy) == "exclude", f"{p} should be exclude"

    def test_reference_only_patterns(self):
        """测试/示例路径正确分类为 reference_only。"""
        policy = load_path_policy(".")
        refs = [
            "tests/test_foo.py",
            "test_something.py",
            "examples/demo.py",
        ]
        for p in refs:
            assert classify_path_role(p, policy) == "reference_only", f"{p} should be reference_only"

    def test_normal_is_default(self):
        """普通源码路径默认为 normal。"""
        policy = load_path_policy(".")
        normals = [
            "api/module_tree.py",
            "codeTree/anchor_engine_v2.py",
            "shared/types.py",
        ]
        for p in normals:
            assert classify_path_role(p, policy) == "normal", f"{p} should be normal"


class TestCandidateProperties:
    """capability_candidates 通用性质测试。"""

    def setup_method(self):
        self.result = build_capability_candidates(".")

    def test_output_structure(self):
        """输出结构符合协议。"""
        assert "version" in self.result
        assert "candidates" in self.result
        assert "summary" in self.result
        assert self.result["version"] == "capability_candidates_v1"

    def test_no_exclude_in_candidates(self):
        """exclude 路径不出现在候选中。"""
        policy = load_path_policy(".")
        for cand in self.result["candidates"]:
            for f in cand.get("files", []):
                role = classify_path_role(f, policy)
                assert role != "exclude", f"exclude file {f} leaked into candidate {cand['id']}"

    def test_reference_only_not_top_candidate(self):
        """reference_only 不能成为顶层候选主来源。"""
        for cand in self.result["candidates"]:
            # reference_only 候选的 policy 字段不应为 reference_only
            assert cand.get("policy") != "reference_only", \
                f"reference_only candidate: {cand['id']}"

    def test_low_distinctiveness_not_top_name(self):
        """低区分度名字不应成为顶层候选名。"""
        bad_names = {"from_dict", "to_dict", "execute", "run", "__init__"}
        for cand in self.result["candidates"]:
            name = cand.get("name_candidate", "")
            # 名字本身不能是纯低区分度名
            assert name not in bad_names, \
                f"low distinctiveness name as top candidate: {name}"


class TestModuleTreeProperties:
    """module_tree_v2 通用性质测试。"""

    def setup_method(self):
        self.tree = generate_module_tree_v2(".")

    def test_output_structure(self):
        """输出结构符合协议。"""
        assert self.tree["version"] == "module_tree_v2"
        assert "modules" in self.tree
        assert "edges" in self.tree
        assert "summary" in self.tree
        assert "completeness" in self.tree

    def test_every_module_has_required_fields(self):
        """每个模块有必要字段。"""
        required = {"id", "name", "status", "confidence", "what", "how", "functions", "role"}
        for mod in self.tree["modules"]:
            for field in required:
                assert field in mod, f"module {mod.get('id', '?')} missing field: {field}"

    def test_status_values_valid(self):
        """status 值在允许范围内。"""
        valid = {"core_flow", "independent_capability", "support_utility", "dormant", "uncertain"}
        for mod in self.tree["modules"]:
            assert mod["status"] in valid, f"invalid status: {mod['status']}"

    def test_confidence_values_valid(self):
        """confidence 值在允许范围内。"""
        valid = {"A", "B", "C", "D"}
        for mod in self.tree["modules"]:
            assert mod["confidence"] in valid, f"invalid confidence: {mod['confidence']}"

    def test_every_module_has_evidence(self):
        """每个模块至少有 evidence 结构。"""
        for mod in self.tree["modules"]:
            assert "evidence" in mod, f"module {mod['id']} missing evidence"

    def test_completeness_has_area_coverage(self):
        """completeness 包含区域覆盖信息。"""
        comp = self.tree.get("completeness", {})
        assert "area_coverage" in comp

    def test_no_temp_fields_in_output(self):
        """最终输出不含临时字段（以 _ 开头）。"""
        for mod in self.tree["modules"]:
            temp_fields = [k for k in mod.keys() if k.startswith("_")]
            assert not temp_fields, f"module {mod['id']} has temp fields: {temp_fields}"


# ══════════════════════════════════════════════════════════════════
# 第二层: 当前仓库回归测试
# ══════════════════════════════════════════════════════════════════

class TestCurrentRepoRegression:
    """当前仓库的回归验证（validation labels，非训练规则）。"""

    def setup_method(self):
        self.tree = generate_module_tree_v2(".")

    def test_no_from_dict_top_module(self):
        """from_dict 不应成为顶层模块名。"""
        for mod in self.tree["modules"]:
            name = mod["name"].lower()
            assert "from_dict" not in name, f"from_dict leaked as module name: {mod['name']}"

    def test_no_generate_report_top_module(self):
        """generate_report 不应成为顶层模块名。"""
        for mod in self.tree["modules"]:
            name = mod["name"].lower()
            assert name != "generate_report", f"generate_report as module name"

    def test_modules_count_reasonable(self):
        """模块数量应在合理范围内（5-100）。"""
        count = len(self.tree["modules"])
        assert 5 <= count <= 100, f"module count {count} out of range"

    def test_has_core_flow_modules(self):
        """至少应有 core_flow 模块。"""
        core = [m for m in self.tree["modules"] if m["status"] == "core_flow"]
        assert len(core) >= 1, "no core_flow modules"

    def test_area_coverage_reasonable(self):
        """区域覆盖率应 >= 50%。"""
        comp = self.tree.get("completeness", {})
        ac = comp.get("area_coverage", {})
        total = ac.get("total_areas", 1)
        covered = ac.get("covered", 0)
        assert covered / total >= 0.5, f"area coverage too low: {covered}/{total}"


# ══════════════════════════════════════════════════════════════════
# 运行入口
# ══════════════════════════════════════════════════════════════════

def _run_tests():
    """简单的自执行测试运行器。"""
    import traceback

    test_classes = [
        TestPathPolicyProperties,
        TestCandidateProperties,
        TestModuleTreeProperties,
        TestCurrentRepoRegression,
    ]

    total = 0
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        print(f"\n── {cls.__name__} ──")
        instance = cls()
        for name in sorted(dir(instance)):
            if not name.startswith("test_"):
                continue
            total += 1
            if hasattr(instance, "setup_method"):
                try:
                    instance.setup_method()
                except Exception as e:
                    print(f"  SETUP_ERROR {name}: {e}")
                    failed += 1
                    errors.append((f"{cls.__name__}.{name}", str(e)))
                    continue

            try:
                getattr(instance, name)()
                print(f"  PASS {name}")
                passed += 1
            except AssertionError as e:
                print(f"  FAIL {name}: {e}")
                failed += 1
                errors.append((f"{cls.__name__}.{name}", str(e)))
            except Exception as e:
                print(f"  ERROR {name}: {e}")
                failed += 1
                errors.append((f"{cls.__name__}.{name}", traceback.format_exc()))

    print(f"\n{'='*50}")
    print(f"总计: {total}  通过: {passed}  失败: {failed}")
    if errors:
        print(f"\n失败详情:")
        for name, err in errors:
            print(f"  {name}: {err[:100]}")
    print(f"{'='*50}")

    return failed == 0


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[2])
    success = _run_tests()
    sys.exit(0 if success else 1)
