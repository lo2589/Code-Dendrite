"""
路径策略分类器
========================
统一整个 Module Tree v2 链路中的路径参与级别判定。

角色分类:
  exclude         - 生成产物/第三方依赖/缓存，不参与候选生成
  reference_only  - 测试/示例/样本，只能提供证据，不能主导模块
  normal          - 默认源码，可参与候选生成和模块合并

用法:
    from usage.path_policy import load_path_policy, classify_path_role

    policy = load_path_policy("/path/to/project")
    role = classify_path_role("api/module_tree.py", policy)
    # -> "normal"
"""

import json
import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional


# ── 默认模式 ──────────────────────────────────────────────────

# 生成产物 / 缓存 / 第三方依赖 → exclude
_DEFAULT_EXCLUDE_PATTERNS = [
    # VCS & 缓存
    "**/.git/**",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    # 依赖 & 构建
    "**/node_modules/**",
    "**/site-packages/**",
    "**/dist/**",
    "**/build/**",
    "**/.venv/**",
    "**/venv/**",
    "**/vendor/**",
    "**/external/**",
    "**/third_party/**",
    # 生成产物 & 索引
    "**/.codedendrite/**",
    "**/.code_genome_db.json",
    "**/.code_anchors.json",
    "**/.code_hash_db.json",
    # IDE & 编辑器
    "**/.vscode/**",
    "**/.idea/**",
    # 常见结果/产出目录
    "**/htmlcov/**",
    "**/out/**",
    "**/.coverage",
]

# 测试 / 示例 / 样本 → reference_only
_DEFAULT_REFERENCE_ONLY_PATTERNS = [
    "**/tests/**",
    "**/test/**",
    "**/test_*.py",
    "**/*_test.py",
    "**/*_smoke.py",
    "**/examples/**",
    "**/fixtures/**",
    "**/samples/**",
    "**/debug/**",
]


# ── 数据结构 ────────────────────────────────────────────────────

@dataclass
class PathPolicy:
    """路径策略对象，在一次生成流程中全局唯一复用。"""

    exclude_patterns: list = field(default_factory=list)
    reference_only_patterns: list = field(default_factory=list)
    role_markers: dict = field(default_factory=dict)
    root: str = "."

    # ── 缓存（避免对同一路径重复匹配）──
    _cache: dict = field(default_factory=dict, repr=False)

    def classify(self, path: str) -> str:
        """分类单个路径，返回 exclude / reference_only / normal。"""
        return classify_path_role(path, self)

    def is_excluded(self, path: str) -> bool:
        return self.classify(path) == "exclude"

    def is_reference_only(self, path: str) -> bool:
        return self.classify(path) == "reference_only"


# ── 路径归一化 ──────────────────────────────────────────────────

def normalize_project_path(path: str, root: str = ".") -> str:
    """将路径归一化为相对于 root 的 POSIX 风格路径。

    - 绝对路径会被转换为相对路径
    - Windows 反斜杠统一转 /
    - 去除开头的 ./ 和结尾的 /
    """
    p = Path(path)
    r = Path(root).resolve()

    # 如果是绝对路径，尝试转为相对
    if p.is_absolute():
        try:
            p = p.relative_to(r)
        except ValueError:
            pass  # 不在 root 下，保持原样

    result = p.as_posix()

    # 去除开头 ./
    if result.startswith("./"):
        result = result[2:]

    # 去除结尾 /
    result = result.rstrip("/")

    return result


# ── 模式匹配 ────────────────────────────────────────────────────

def _match_any_pattern(path: str, patterns: list) -> bool:
    """检查路径是否匹配任意一个 glob 模式。

    支持两种匹配策略:
    1. fnmatch 直接匹配完整路径
    2. 对路径的每一层前缀做匹配（处理 **/xxx/** 这类模式）
    """
    for pattern in patterns:
        # 直接匹配
        if fnmatch(path, pattern):
            return True

        # 如果模式以 **/ 开头，去掉前缀后对路径的每个子段匹配
        clean_pattern = pattern
        if clean_pattern.startswith("**/"):
            clean_pattern = clean_pattern[3:]

        # 对路径的每个可能起点做匹配
        parts = path.split("/")
        for i in range(len(parts)):
            sub_path = "/".join(parts[i:])
            if fnmatch(sub_path, clean_pattern):
                return True

    return False


# ── 分类核心 ────────────────────────────────────────────────────

def classify_path_role(path: str, policy: "PathPolicy") -> str:
    """分类单个路径角色。

    优先级: exclude > reference_only > normal

    返回: "exclude" / "reference_only" / "normal"
    """
    normalized = normalize_project_path(path, policy.root)

    # 查缓存
    if normalized in policy._cache:
        return policy._cache[normalized]

    role = "normal"

    # 1. 检查 exclude
    if _match_any_pattern(normalized, policy.exclude_patterns):
        role = "exclude"
    # 2. 检查 reference_only
    elif _match_any_pattern(normalized, policy.reference_only_patterns):
        role = "reference_only"

    policy._cache[normalized] = role
    return role


# ── 策略构建 ────────────────────────────────────────────────────

def _build_default_policy_dict() -> dict:
    """构建默认策略字典。"""
    return {
        "exclude_paths": list(_DEFAULT_EXCLUDE_PATTERNS),
        "reference_only_paths": list(_DEFAULT_REFERENCE_ONLY_PATTERNS),
        "role_markers": {
            "generated_artifact": [
                "**/.codedendrite/**",
                "**/.code_genome_db.json",
                "**/htmlcov/**",
            ],
            "dependency_or_vendor": [
                "**/node_modules/**",
                "**/site-packages/**",
                "**/vendor/**",
                "**/external/**",
                "**/third_party/**",
            ],
            "vcs_or_cache": [
                "**/.git/**",
                "**/__pycache__/**",
                "**/.pytest_cache/**",
            ],
            "test_or_example_reference": [
                "**/tests/**",
                "**/test_*.py",
                "**/*_test.py",
                "**/examples/**",
                "**/fixtures/**",
            ],
        },
    }


def _read_policy_config(config_path: Optional[str], root: str = ".") -> Optional[dict]:
    """读取外部配置文件。不存在时返回 None。"""
    if config_path:
        p = Path(config_path)
    else:
        p = Path(root) / ".codedendrite" / "path_policy.json"

    if not p.exists():
        return None

    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _merge_policy_layers(
    defaults: dict,
    config: Optional[dict],
    overrides: Optional[dict],
) -> dict:
    """合并三层策略: 默认 < 配置文件 < 显式覆盖。

    合并方式: 列表取并集，不去重（fnmatch 多匹配无害）。
    """
    result = {
        "exclude_paths": list(defaults.get("exclude_paths", [])),
        "reference_only_paths": list(defaults.get("reference_only_paths", [])),
        "role_markers": dict(defaults.get("role_markers", {})),
    }

    for layer in [config, overrides]:
        if layer is None:
            continue
        if "exclude_paths" in layer:
            result["exclude_paths"].extend(layer["exclude_paths"])
        if "reference_only_paths" in layer:
            result["reference_only_paths"].extend(layer["reference_only_paths"])
        if "role_markers" in layer:
            for key, patterns in layer["role_markers"].items():
                if key in result["role_markers"]:
                    result["role_markers"][key].extend(patterns)
                else:
                    result["role_markers"][key] = list(patterns)

    return result


def load_path_policy(
    root: str = ".",
    config_path: Optional[str] = None,
    overrides: Optional[dict] = None,
) -> PathPolicy:
    """加载路径策略。

    三层合并: 默认规则 < 配置文件 < 显式覆盖

    Args:
        root: 项目根目录
        config_path: 可选的配置文件路径
        overrides: 可选的显式覆盖字典

    Returns:
        PathPolicy 对象，全局唯一复用
    """
    defaults = _build_default_policy_dict()
    config = _read_policy_config(config_path, root)
    merged = _merge_policy_layers(defaults, config, overrides)

    return PathPolicy(
        exclude_patterns=merged["exclude_paths"],
        reference_only_patterns=merged["reference_only_paths"],
        role_markers=merged["role_markers"],
        root=str(Path(root).resolve()),
    )


# ── 便捷工具函数 ────────────────────────────────────────────────

def dump_default_policy() -> dict:
    """导出默认策略字典，供 CLI --dump-default 使用。"""
    return _build_default_policy_dict()


def classify_with_detail(path: str, policy: "PathPolicy") -> dict:
    """分类路径并返回详细信息，供 CLI / 调试使用。"""
    normalized = normalize_project_path(path, policy.root)
    role = classify_path_role(path, policy)

    # 找到匹配的模式
    matched_rule = "default:normal"
    if role == "exclude":
        for p in policy.exclude_patterns:
            if _match_any_pattern(normalized, [p]):
                matched_rule = f"exclude:{p}"
                break
    elif role == "reference_only":
        for p in policy.reference_only_patterns:
            if _match_any_pattern(normalized, [p]):
                matched_rule = f"reference_only:{p}"
                break

    return {
        "normalized_path": normalized,
        "role": role,
        "matched_rule": matched_rule,
    }


# ── 主入口（直接运行时的快速测试）────────────────────────────────

if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else "."
    policy = load_path_policy(root)

    # 快速验证几个路径
    test_paths = [
        ".codedendrite/anchors.json",
        ".codedendrite/relations.json",
        "api/module_tree.py",
        "api/path_policy.py",
        "tests/test_module_tree_smoke.py",
        "debug/test_extract_body2.py",
        "codeTree/anchor_engine_v2.py",
        "examples/demo.py",
        "node_modules/foo/bar.js",
        "__pycache__/foo.pyc",
    ]

    print(f"root: {policy.root}")
    print(f"exclude 模式数: {len(policy.exclude_patterns)}")
    print(f"reference_only 模式数: {len(policy.reference_only_patterns)}")
    print()

    for p in test_paths:
        detail = classify_with_detail(p, policy)
        print(f"  {detail['role']:16s} {detail['normalized_path']}")
        if detail['role'] != 'normal':
            print(f"  {'':16s} matched: {detail['matched_rule']}")
