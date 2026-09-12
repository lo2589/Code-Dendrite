"""
compatibility.py — 节点替换兼容性检查

独立函数，可以在替换前快速检查是否物理可连接。
"""
from __future__ import annotations

from typing import Optional


def check_compatibility(
    original_anchor: dict,
    replacement_anchor: dict,
) -> dict:
    """
    检查两个锚点对应的函数是否可以互相替换。

    返回：
    {
      "compatible": bool,
      "input_compatible": bool,
      "output_compatible": bool,
      "issues": [str],          # 不兼容原因
      "warnings": [str],        # 兼容但有风险
    }
    """
    issues = []
    warnings = []

    orig_meta = original_anchor.get("metadata", {})
    repl_meta = replacement_anchor.get("metadata", {})

    orig_params = orig_meta.get("parameters", [])
    repl_params = repl_meta.get("parameters", [])

    orig_return = orig_meta.get("return_type", None)
    repl_return = repl_meta.get("return_type", None)

    # 输入检查
    input_compatible = _check_params(orig_params, repl_params, issues, warnings)

    # 输出检查
    output_compatible = _check_return(orig_return, repl_return, issues, warnings)

    # 语言检查（跨语言替换警告）
    orig_lang = original_anchor.get("language", "")
    repl_lang = replacement_anchor.get("language", "")
    if orig_lang and repl_lang and orig_lang != repl_lang:
        warnings.append(f"跨语言替换: {orig_lang} → {repl_lang}，需要额外适配层")

    compatible = len(issues) == 0

    return {
        "compatible": compatible,
        "input_compatible": input_compatible,
        "output_compatible": output_compatible,
        "issues": issues,
        "warnings": warnings,
    }


def _check_params(orig: list, repl: list, issues: list, warnings: list) -> bool:
    if len(orig) != len(repl):
        issues.append(
            f"参数数量不匹配: 原始 {len(orig)} 个，替换 {len(repl)} 个"
        )
        return False

    # 如果有类型信息，检查类型
    for i, (o, r) in enumerate(zip(orig, repl)):
        o_name = o if isinstance(o, str) else o.get("name", "")
        r_name = r if isinstance(r, str) else r.get("name", "")
        o_type = o.get("type", "") if isinstance(o, dict) else ""
        r_type = r.get("type", "") if isinstance(r, dict) else ""

        if o_type and r_type and o_type != r_type:
            issues.append(f"参数 {i} 类型不匹配: {o_type} vs {r_type}")
            return False
        if o_name != r_name:
            warnings.append(f"参数 {i} 名称不同: {o_name} → {r_name}（可能影响可读性）")

    return True


def _check_return(orig, repl, issues: list, warnings: list) -> bool:
    if orig is None or repl is None:
        return True  # 缺少类型信息，保守认为兼容

    orig_str = str(orig).lower()
    repl_str = str(repl).lower()

    if orig_str == repl_str:
        return True

    # None vs 有返回值
    if "none" in orig_str and "none" not in repl_str:
        warnings.append(f"原始函数无返回值，替换函数返回 {repl}，调用方可能收到意外返回值")
        return True

    if "none" not in orig_str and "none" in repl_str:
        issues.append(f"返回类型不兼容: 原始返回 {orig}，替换函数无返回值")
        return False

    # 类型不同但不确定是否兼容
    warnings.append(f"返回类型可能不同: {orig} vs {repl}，请人工确认")
    return True
