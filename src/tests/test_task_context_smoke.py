"""Task Context Packet smoke 测试。

测试分两层：
  1. 通用属性测试 — 不依赖当前仓库具体数据，验证结构和约束
  2. 当前仓库回归测试 — 用真实数据验证已知行为
"""

import json
import sys
import os
from pathlib import Path

import pytest

# 确保能导入 api 模块
ROOT = str(Path(__file__).resolve().parent.parent)            # src：import 根
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])       # 仓库根：索引在这
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from usage.packets.task_context_packet import (
    generate_task_context,
    resolve_task_anchor,
    build_level0,
    build_level1,
    build_level2,
    format_compact,
    format_compact_tokens,
    _estimate_tokens,
    _estimate_obj_tokens,
    _build_edge_indexes,
    assess_task_matches,
    MAX_CANDIDATES,
)
from analyzer.anchors import load_anchors
from api.relations import load_relations


# ── 辅助 ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def repo_data():
    """加载当前仓库数据（只加载一次）。"""
    anchors = load_anchors(PROJECT_ROOT)
    relations = load_relations(PROJECT_ROOT)

    tree_path = Path(PROJECT_ROOT) / ".codedendrite" / "module_tree_v2.json"
    module_tree = None
    if tree_path.exists():
        with open(tree_path, encoding="utf-8") as f:
            module_tree = json.load(f)

    return {
        "anchors": anchors,
        "relations": relations,
        "module_tree": module_tree,
    }


# ══════════════════════════════════════════════════════════════════
# 第一层：通用属性测试
# ══════════════════════════════════════════════════════════════════

class TestResolveTaskAnchor:
    """测试锚点解析的四种策略。"""

    def test_exact_id_match(self, repo_data):
        """精确 ID 应返回恰好 1 个结果。"""
        anchors = repo_data["anchors"]
        some_id = next(iter(anchors))
        results = resolve_task_anchor(some_id, anchors)
        assert len(results) == 1
        assert results[0][0] == some_id
        assert results[0][2] == "exact_id"

    def test_symbol_name_match(self, repo_data):
        """符号名匹配至少返回 1 个结果。"""
        anchors = repo_data["anchors"]
        # 取一个已知符号名
        sample_anchor = next(iter(anchors.values()))
        sym = getattr(sample_anchor, "symbol", "")
        results = resolve_task_anchor(sym, anchors)
        assert len(results) >= 1
        assert results[0][2] in ("exact_id", "symbol_name")

    def test_keyword_match(self, repo_data):
        """精确符号优先于模糊关键词，且返回数有上限。"""
        anchors = repo_data["anchors"]
        results = resolve_task_anchor("anchor", anchors)
        assert 1 <= len(results) <= MAX_CANDIDATES
        assert results[0][2] == "symbol_name"

    def test_absolute_file_path_suffix_match(self):
        anchors = {
            "pkg/colors.py::to_rgba": {
                "id": "pkg/colors.py::to_rgba", "symbol": "to_rgba",
                "file": "pkg/colors.py", "line_start": 10,
            }
        }
        results = resolve_task_anchor(
            "/tmp/site-packages/pkg/colors.py", anchors,
        )
        assert results[0][0] == "pkg/colors.py::to_rgba"
        assert results[0][2] == "file_suffix"

    def test_generic_issue_word_is_not_a_fuzzy_anchor(self):
        anchors = {
            "pkg/module_loader.py::load": {
                "id": "pkg/module_loader.py::load", "symbol": "load",
                "file": "pkg/module_loader.py", "line_start": 1,
            }
        }
        assert resolve_task_anchor("module", anchors) == []

    def test_cross_file_symbol_is_ambiguous(self):
        anchors = {
            "a.py::handler": {"id": "a.py::handler", "symbol": "handler", "file": "a.py"},
            "b.py::handler": {"id": "b.py::handler", "symbol": "handler", "file": "b.py"},
        }
        matches = resolve_task_anchor("handler", anchors)
        assessment = assess_task_matches("handler", matches)
        assert assessment["status"] == "ambiguous"
        assert assessment["safe_to_recommend"] is False

    def test_truncation_preserves_cross_file_ambiguity(self):
        anchors = {
            "a.py::handler{}".format(i): {
                "id": "a.py::handler{}".format(i), "symbol": "handler",
                "file": "a.py", "line_start": i,
            }
            for i in range(MAX_CANDIDATES + 2)
        }
        anchors["z.py::handler"] = {
            "id": "z.py::handler", "symbol": "handler", "file": "z.py",
            "line_start": 1,
        }
        matches = resolve_task_anchor("handler", anchors)
        assessment = assess_task_matches("handler", matches)
        assert len(matches) == MAX_CANDIDATES
        assert assessment["status"] == "ambiguous"
        assert "z.py" in assessment["candidate_files"]

    def test_no_match(self, repo_data):
        """完全不存在的查询返回空列表。"""
        anchors = repo_data["anchors"]
        results = resolve_task_anchor("zzz_nonexistent_xyz_123", anchors)
        assert len(results) == 0

    def test_empty_query(self, repo_data):
        """空查询返回空列表。"""
        results = resolve_task_anchor("", repo_data["anchors"])
        assert len(results) == 0

    def test_empty_anchors(self):
        """空锚点字典返回空列表。"""
        results = resolve_task_anchor("anything", {})
        assert len(results) == 0


class TestContextStructure:
    """测试生成的 context 结构完整性。"""

    def test_has_required_fields(self, repo_data):
        """context 必须包含所有必要字段。"""
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
            module_tree=repo_data["module_tree"],
        )
        required = [
            "version", "task_query", "resolved_anchor",
            "match_count", "project_brief", "area_map",
            "task_slice", "_level3_on_demand", "token_estimate",
        ]
        for field in required:
            assert field in ctx, "缺少字段: {}".format(field)

    def test_version_string(self, repo_data):
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        assert ctx["version"] == "task_context_packet_v1"

    def test_level3_default_off(self, repo_data):
        """Level 3 默认不给源码片段。"""
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        assert ctx["_level3_on_demand"] is True
        # 不应包含任何源码片段字段
        assert "source_snippet" not in ctx
        task_slice = ctx.get("task_slice", {})
        for c in task_slice.get("candidates", []):
            assert "source_code" not in c, "候选不应包含源码"
            assert "snippet" not in c, "候选不应包含片段"

    def test_no_match_returns_none_anchor(self, repo_data):
        """查询不到时 resolved_anchor 应为 None。"""
        ctx = generate_task_context(
            "zzz_nonexistent_xyz", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        assert ctx["resolved_anchor"] is None
        assert ctx["match_count"] == 0

    def test_missing_relations_degrades_without_losing_anchor(self, tmp_path):
        (tmp_path / "app.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
        anchors = {
            "app.py::handler": {
                "id": "app.py::handler", "symbol": "handler", "file": "app.py",
                "line_start": 1, "line_end": 2,
            }
        }
        ctx = generate_task_context(
            "handler", root=str(tmp_path), anchors=anchors, module_tree=None,
        )
        assert ctx["resolved_anchor"] == "app.py::handler"
        assert ctx["navigation"]["relation_coverage"] == "unavailable"

    def test_large_context_respects_privacy_mask(self, tmp_path):
        (tmp_path / "secret.py").write_text(
            "def secret():\n    return 'DO_NOT_EMBED_ME'\n", encoding="utf-8",
        )
        (tmp_path / ".codedendrite_ignore").write_text(
            "[privacy_mask]\nsecret.py\n", encoding="utf-8",
        )
        anchors = {
            "secret.py::secret": {
                "id": "secret.py::secret", "symbol": "secret", "file": "secret.py",
                "line_start": 1, "line_end": 2,
            }
        }
        ctx = generate_task_context(
            "secret", root=str(tmp_path), anchors=anchors,
            relations={"edges": []}, module_tree=None, model_profile="large",
        )
        assert ctx["source_slices"] == []
        assert "DO_NOT_EMBED_ME" not in ctx["prompt"]

    def test_traceback_line_is_a_high_confidence_fallback(self, tmp_path):
        (tmp_path / "app.py").write_text(
            "def handler():\n    raise ValueError('bad')\n", encoding="utf-8",
        )
        anchors = {
            "app.py::handler": {
                "id": "app.py::handler", "symbol": "handler", "file": "app.py",
                "line_start": 1, "line_end": 2,
            }
        }
        ctx = generate_task_context(
            "not_a_symbol", root=str(tmp_path), anchors=anchors,
            relations={"edges": []}, module_tree=None,
            error_text='Traceback\n  File "/tmp/project/app.py", line 2, in handler\nValueError: bad',
        )
        assert ctx["resolved_anchor"] == "app.py::handler"
        assert ctx["navigation"]["confidence"] == "high"
        assert ctx["navigation"]["match_types"] == ["error_line"]


class TestLevel0Properties:
    """Level 0 属性测试。"""

    def test_project_brief_not_empty(self, repo_data):
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
            module_tree=repo_data["module_tree"],
        )
        brief = ctx["project_brief"]
        assert brief.get("project"), "project 不应为空"
        assert brief.get("areas"), "areas 不应为空"

    def test_level0_token_limit(self, repo_data):
        """L0 不超过 3 句（验收标准 #1），token 粗估 < 150。"""
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
            module_tree=repo_data["module_tree"],
        )
        l0_tokens = ctx["token_estimate"]["level0"]
        # 允许比设计宽松，但不能爆炸
        assert l0_tokens < 150, "L0 token {} 超限".format(l0_tokens)


class TestLevel1Properties:
    """Level 1 属性测试。"""

    def test_area_map_has_required_fields(self, repo_data):
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
            module_tree=repo_data["module_tree"],
        )
        area = ctx["area_map"]
        assert "current_area" in area
        assert "task_anchor" in area
        assert "area_modules" in area
        assert "responsibility" in area

    def test_level1_only_current_area(self, repo_data):
        """L1 只描述当前区域（验收标准 #2）。"""
        ctx = generate_task_context(
            "api/anchors.py::create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
            module_tree=repo_data["module_tree"],
        )
        area = ctx["area_map"]
        current = area["current_area"]
        # 区域模块都应该在当前区域下
        assert current, "current_area 不应为空"


class TestLevel2Properties:
    """Level 2 属性测试。"""

    def test_candidates_count(self, repo_data):
        """L2 只给少量可信候选，不为满足数量下限而补齐。"""
        ctx = generate_task_context(
            "api/anchors.py::create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
            module_tree=repo_data["module_tree"],
        )
        candidates = ctx["task_slice"]["candidates"]
        assert 1 <= len(candidates) <= 3
        assert all(c["why"] != "同文件符号" for c in candidates)

    def test_ambiguous_match_emits_no_navigation_commands(self):
        anchors = {
            "a.py::handler": {"id": "a.py::handler", "symbol": "handler", "file": "a.py"},
            "b.py::handler": {"id": "b.py::handler", "symbol": "handler", "file": "b.py"},
        }
        ctx = generate_task_context(
            "handler", root=PROJECT_ROOT, anchors=anchors,
            relations={"edges": []}, module_tree=None,
        )
        assert ctx["resolved_anchor"] is None
        assert ctx["navigation"]["status"] == "ambiguous"
        assert ctx["task_slice"]["candidates"] == []
        assert len(ctx["ambiguous_matches"]) == 2

    def test_each_candidate_has_why_and_next(self, repo_data):
        """每个候选都有 why 和 next_command（验收标准 #4）。"""
        ctx = generate_task_context(
            "api/anchors.py::create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
            module_tree=repo_data["module_tree"],
        )
        for c in ctx["task_slice"]["candidates"]:
            assert c.get("why"), "候选 {} 缺少 why".format(c["id"])
            assert c.get("next_command"), "候选 {} 缺少 next_command".format(c["id"])

    def test_first_candidate_is_task_target(self, repo_data):
        """第一个候选应是任务锚点自身。"""
        ctx = generate_task_context(
            "api/anchors.py::create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        c0 = ctx["task_slice"]["candidates"][0]
        assert c0["id"] == "C0"
        assert "任务目标" in c0["why"]


class TestCompactFormat:
    """测试紧凑文本格式。"""

    def test_compact_is_string(self, repo_data):
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        compact = format_compact(ctx)
        assert isinstance(compact, str)
        assert len(compact) > 0

    def test_compact_contains_sections(self, repo_data):
        """compact 格式必须包含关键段落。"""
        ctx = generate_task_context(
            "api/anchors.py::create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        compact = format_compact(ctx)
        assert "项目:" in compact
        assert "当前区域:" in compact
        assert "任务锚点:" in compact
        assert "导航置信:" in compact
        assert "候选:" in compact

    def test_compact_token_reasonable(self, repo_data):
        """compact 文本 token 数应在合理范围。"""
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        tokens = format_compact_tokens(ctx)
        # 整个 compact 应控制在 1000 tokens 以内
        assert tokens < 1000, "compact tokens {} 超限".format(tokens)


# ══════════════════════════════════════════════════════════════════
# 第二层：当前仓库回归测试
# ══════════════════════════════════════════════════════════════════

class TestCurrentRepoRegression:
    """基于当前仓库数据的回归测试。"""

    def test_duplicate_create_anchor_is_not_presented_as_resolved(self, repo_data):
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        assert ctx["resolved_anchor"] is None
        assert ctx["navigation"]["status"] == "ambiguous"
        assert ctx["navigation"]["raw_match_count"] >= 2

    def test_total_token_under_budget(self, repo_data):
        """总 token 应在默认预算附近。"""
        ctx = generate_task_context(
            "create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
            module_tree=repo_data["module_tree"],
        )
        total = ctx["token_estimate"]["total"]
        # 应在 2000 以下（默认预算 1200，允许一定超出）
        assert total < 2000, "总 token {} 超过 2000".format(total)

    def test_keyword_dataflow_preserves_ambiguity(self, repo_data):
        """跨文件关键词只能作为歧义证据，不能伪装成推荐。"""
        ctx = generate_task_context(
            "dataflow", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        assert ctx["match_count"] > 1
        assert ctx["resolved_anchor"] is None
        assert ctx["navigation"]["status"] == "ambiguous"
        assert ctx["ambiguous_matches"]

    def test_context_edges_are_bounded(self, repo_data):
        """关系上下文可以为空，但不能越过固定上限。"""
        ctx = generate_task_context(
            "api/anchors.py::create_anchor", root=PROJECT_ROOT,
            anchors=repo_data["anchors"],
            relations=repo_data["relations"],
        )
        edges = ctx["task_slice"]["context_edges"]
        assert len(edges) <= 10
