"""
smart_analyzer_patch.py — smartAnalyzer 集成补丁

将 context_builder / pathTracer / anchorMemory 集成到
SmartCodeAnalyzer，补全原有空壳方法，新增 AI 导航接口。

使用方式：
    把本文件的内容合并到 smartAnalyzer/smart_analyzer.py
    或直接 import 使用增强版：

    from smartAnalyzer_patch.smart_analyzer_patch import SmartCodeAnalyzerV2
    analyzer = SmartCodeAnalyzerV2(project_root="/path/to/project")
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

# 把父级路径加入，确保能找到各模块
_HERE = Path(__file__).parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


class SmartCodeAnalyzerV2:
    """
    增强版智能代码分析器。

    在原 SmartCodeAnalyzer 基础上集成：
      - context_builder  → get_ai_context(), expand_symbol()
      - pathTracer       → trace_path(), get_pipeline()
      - anchorMemory     → observe(), get_memory_summary()

    所有模块懒加载，不影响冷启动速度。
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self._cache: dict = {}

        # 懒加载的模块实例
        self._context_builder = None
        self._expander = None
        self._tracer = None
        self._memory = None

    # ── 懒加载属性 ────────────────────────────────────────────

    @property
    def context_builder(self):
        if self._context_builder is None:
            from usage.structure.context_builder import ContextBuilder
            self._context_builder = ContextBuilder(str(self.project_root))
        return self._context_builder

    @property
    def expander(self):
        if self._expander is None:
            from usage.structure.context_builder import SymbolExpander
            self._expander = SymbolExpander(str(self.project_root))
        return self._expander

    @property
    def tracer(self):
        if self._tracer is None:
            from analyzer.path import PathTracer
            self._tracer = PathTracer(str(self.project_root))
        return self._tracer

    @property
    def memory(self):
        if self._memory is None:
            from usage.repair.anchor_memory import AnchorMemory
            self._memory = AnchorMemory(str(self.project_root))
        return self._memory

    # ══════════════════════════════════════════════════════════
    # AI 上下文接口
    # ══════════════════════════════════════════════════════════

    def get_ai_context(
        self,
        budget_tokens: int = 2000,
        include_memory: bool = True,
        output_format: str = "markdown",
    ) -> str:
        """
        生成 AI 可用的项目导航地图。

        这是 AI 调用的第一步：拿到地图，按需再查细节。

        参数：
            budget_tokens:  输出 token 预算
            include_memory: 是否附加高置信度锚点记忆
            output_format:  "markdown" | "compact" | "json"

        返回：
            压缩的项目地图文本，适合放入 system prompt
        """
        from usage.structure.context_builder import format_map

        t0 = time.time()
        map_text = self.context_builder.build_map(budget_tokens)

        if include_memory:
            mem_summary = self.memory.get_all_summaries(min_confidence=0.6)
            if mem_summary:
                map_text += "\n\n## Anchor Memory (高置信度)\n" + mem_summary

        result = format_map(map_text, output_format)
        elapsed = time.time() - t0
        self._cache["last_context_build_ms"] = int(elapsed * 1000)
        return result

    def expand_symbol(self, symbol_name: str, with_context: bool = False) -> str:
        """
        精准展开某个符号的代码。

        AI 拿到地图后，需要看具体实现时调用此方法。
        比直接搜文件快，因为走的是锚点索引。

        参数：
            symbol_name:  函数/类/方法名
            with_context: 是否包含前后 5 行上下文
        """
        # 记录 AI 访问（不写 memory，只更新计数）
        self._record_access(symbol_name)

        if with_context:
            return self.expander.expand_with_context(symbol_name, lines_around=5)
        return self.expander.expand(symbol_name)

    def search_symbol(self, keyword: str, top_n: int = 5) -> list[dict]:
        """
        搜索符号，返回候选列表。

        参数：
            keyword: 关键词（支持模糊匹配）
            top_n:   返回候选数量
        """
        return self.expander.search(keyword, top_n)

    # ══════════════════════════════════════════════════════════
    # 管线追踪接口
    # ══════════════════════════════════════════════════════════

    def trace_path(
        self,
        entry: str,
        target: Optional[str] = None,
        conditions: Optional[dict] = None,
        output: str = "text",
    ) -> str:
        """
        追踪从入口函数到目标函数的调用路径。

        参数：
            entry:      入口函数名
            target:     目标函数名（None 则追踪完整链路）
            conditions: 已知条件字典，用于剪枝分支
                        示例: {"request.type": "A", "is_admin": False}
            output:     输出格式 "text" | "mermaid" | "json"

        返回：
            调用路径的文字/图形描述
        """
        t = self.tracer.from_entry(entry)

        if conditions:
            for k, v in conditions.items():
                t = t.given(k, v)

        if target:
            t = t.until(target)

        result = t.run()

        if output == "mermaid":
            return result.to_mermaid()
        if output == "json":
            return result.to_pipeline()
        return str(result)

    def get_pipeline(self, entry: str) -> list[dict]:
        """
        获取入口函数的完整管线节点列表（不剪枝）。
        用于可视化展示。

        返回：
            节点字典列表，每个包含 name/file/inputs/outputs/depth
        """
        nodes = self.tracer.get_pipeline(entry)
        return [n.to_dict() for n in nodes]

    def replace_node(
        self,
        entry: str,
        original: str,
        replacement: str,
        conditions: Optional[dict] = None,
    ) -> str:
        """
        在追踪路径中提出节点替换方案。

        返回可读的替换分析报告，包含：
          - 类型兼容性
          - 语义差异
          - 风险等级
          - 替换后的管线（若兼容）
        """
        t = self.tracer.from_entry(entry)
        if conditions:
            for k, v in conditions.items():
                t = t.given(k, v)
        result = t.run()

        proposal = result.replace_node(original, replacement)

        # 记录替换尝试到 memory
        anchor_id = self._find_anchor_id(original)
        if anchor_id:
            self.memory.record_milestone(
                anchor_id,
                event="replacement_attempt",
                detail=f"尝试替换为 {replacement}，风险: {proposal.risk_level}",
            )
            self.memory.save()

        return str(proposal)

    # ══════════════════════════════════════════════════════════
    # 错误诊断（原有功能增强版）
    # ══════════════════════════════════════════════════════════

    def analyze_error(
        self,
        error_msg: str,
        file_path: Optional[str] = None,
        traceback_str: Optional[str] = None,
    ) -> str:
        """
        5 层渐进错误诊断。

        L1: 符号定位    — 从错误信息提取符号，锚点精准定位
        L2: 继承链检查  — 方法解析顺序是否正确
        L3: 数据流追踪  — 出问题的变量从哪来
        L4: 路径分析    — 错误发生在哪条调用路径上
        L5: 全局扫描    — 在整个项目中找相似错误

        参数：
            error_msg:     错误消息字符串
            file_path:     发生错误的文件（可选，提高精度）
            traceback_str: 完整 traceback（可选）

        返回：
            诊断报告文本
        """
        report = [f"# 错误诊断报告\n\n错误: {error_msg}\n"]

        # L1: 从错误信息提取符号名
        symbols = self._parse_error_symbols(error_msg, traceback_str)
        if symbols:
            report.append("## L1 · 符号定位")
            for sym in symbols[:3]:
                code = self.expander.expand(sym)
                loc = self.expander.get_anchor_info(sym)
                if loc:
                    report.append(
                        f"  {sym}  {loc.get('file')}:L{loc.get('line_start')}"
                    )
                    # 记录 AI 访问到 memory
                    aid = self._find_anchor_id(sym)
                    if aid:
                        self.memory.observe(
                            aid,
                            content=f"在错误诊断中被访问: {error_msg[:50]}",
                            source="ai_single",
                            confidence=0.4,
                            context=error_msg,
                        )
            report.append("")

        # L2: 检查继承链（如果是 AttributeError）
        if "AttributeError" in error_msg or "has no attribute" in error_msg:
            report.append("## L2 · 继承链检查")
            class_name = self._extract_class_from_error(error_msg)
            if class_name:
                report.append(f"  检查 {class_name} 的继承链...")
                report.append(
                    f"  提示: 使用 trace_inheritance('{class_name}', 'method_name') 查看完整 MRO"
                )
            report.append("")

        # L3: 数据流（如果有 traceback 中的变量）
        if traceback_str:
            report.append("## L3 · 调用路径")
            # 从 traceback 提取调用栈顶
            top_func = self._extract_top_function(traceback_str)
            if top_func:
                path = self.trace_path(top_func, output="text")
                report.append(f"  入口: {top_func}")
                report.append(path[:500])  # 截断避免过长
            report.append("")

        # L4: 全局上下文
        report.append("## L4 · 相关符号")
        if symbols:
            callers = self.expander.get_callers(symbols[0])
            if callers:
                report.append(f"  调用 {symbols[0]} 的函数:")
                for c in callers[:5]:
                    report.append(f"    - {c}")

        # 保存 memory
        self.memory.save()

        return "\n".join(report)

    # ══════════════════════════════════════════════════════════
    # 记忆接口
    # ══════════════════════════════════════════════════════════

    def observe(
        self,
        symbol_name: str,
        content: str,
        source: str = "ai_single",
        confidence: float = 0.7,
    ) -> bool:
        """
        记录对某个符号的观察（积累到阈值才固化）。

        source 可选值：
          "human"       — 人类工程师，直接固化，权重最高
          "test"        — 测试用例覆盖，直接固化
          "ai_consensus"— AI 多次一致，中权重
          "ai_single"   — 单次 AI 推断，低权重（默认）
        """
        anchor_id = self._find_anchor_id(symbol_name)
        if not anchor_id:
            anchor_id = symbol_name  # 用名字作 ID
        result = self.memory.observe(anchor_id, content, source, confidence)
        self.memory.save()
        return result

    def get_memory_summary(self, symbol_name: str) -> str:
        """获取某个符号的记忆摘要（适合放入 AI 上下文）。"""
        anchor_id = self._find_anchor_id(symbol_name) or symbol_name
        return self.memory.get_summary(anchor_id)

    def get_stale_knowledge(self) -> list[str]:
        """返回置信度低的符号列表（需要重新学习）。"""
        return self.memory.get_low_confidence_anchors(threshold=0.4)

    # ══════════════════════════════════════════════════════════
    # 缓存和统计
    # ══════════════════════════════════════════════════════════

    def get_cache_stats(self) -> dict:
        """返回缓存统计信息。"""
        return {
            "last_context_build_ms": self._cache.get("last_context_build_ms", 0),
            "access_counts": self._cache.get("access_counts", {}),
            "project_stats": self.context_builder.get_stats(),
        }

    def on_files_changed(self, changed_files: list[str]):
        """
        文件变更回调。

        当文件发生变更时调用此方法：
          1. 重置相关锚点的 context_builder 缓存
          2. 记录变更 milestone 到 memory
          3. 触发 anchorRepair（若可用）

        参数：
            changed_files: 变更的文件路径列表
        """
        # 重置 context_builder 缓存
        self._context_builder = None

        # 找受影响的锚点，记录 milestone
        affected = self._find_anchors_in_files(changed_files)
        for anchor_id in affected:
            self.memory.record_milestone(
                anchor_id,
                event="code_changed",
                detail=f"文件变更: {', '.join(changed_files[:3])}",
                author="system",
            )

        self.memory.save()

        # 尝试触发 anchorRepair
        try:
            from usage.repair.anchor_repair import check_all_anchors
            stale = check_all_anchors(str(self.project_root))
            return {"affected_anchors": len(affected), "stale_anchors": len(stale)}
        except ImportError:
            return {"affected_anchors": len(affected)}

    # ══════════════════════════════════════════════════════════
    # 私有工具方法
    # ══════════════════════════════════════════════════════════

    def _record_access(self, symbol_name: str):
        counts = self._cache.setdefault("access_counts", {})
        counts[symbol_name] = counts.get(symbol_name, 0) + 1

    def _find_anchor_id(self, symbol_name: str) -> Optional[str]:
        """在锚点库中找 anchor_id。"""
        if not self.expander._loaded:
            self.expander._ensure_loaded()
        for k, v in self.expander._anchors.items():
            if v.get("name") == symbol_name or k.endswith(f".{symbol_name}"):
                return k
        return None

    def _find_anchors_in_files(self, files: list[str]) -> list[str]:
        """找属于指定文件的所有锚点 ID。"""
        if not self.expander._loaded:
            self.expander._ensure_loaded()
        result = []
        for k, v in self.expander._anchors.items():
            if v.get("file", "") in files:
                result.append(k)
        return result

    def _parse_error_symbols(
        self, error_msg: str, traceback_str: Optional[str] = None
    ) -> list[str]:
        """从错误信息中提取相关符号名。"""
        import re
        symbols = []

        # 常见模式: "name 'xxx' is not defined"
        m = re.findall(r"name ['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", error_msg)
        symbols.extend(m)

        # "object has no attribute 'xxx'"
        m = re.findall(r"attribute ['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", error_msg)
        symbols.extend(m)

        # "module 'xxx' has no attribute 'yyy'"
        m = re.findall(r"['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", error_msg)
        symbols.extend(m)

        # 从 traceback 提取函数名
        if traceback_str:
            m = re.findall(r"in ([a-zA-Z_][a-zA-Z0-9_]*)\s*$", traceback_str, re.M)
            symbols.extend(m)

        # 去重，过滤关键字
        seen = set()
        result = []
        for s in symbols:
            if s not in seen and len(s) > 2:
                seen.add(s)
                result.append(s)
        return result

    def _extract_class_from_error(self, error_msg: str) -> Optional[str]:
        """从 AttributeError 中提取类名。"""
        import re
        m = re.search(r"'([A-Z][a-zA-Z0-9_]*)' object", error_msg)
        if m:
            return m.group(1)
        return None

    def _extract_top_function(self, traceback_str: str) -> Optional[str]:
        """从 traceback 中提取最顶层的用户函数。"""
        import re
        matches = re.findall(r"in ([a-zA-Z_][a-zA-Z0-9_]*)\s*$", traceback_str, re.M)
        # 过滤内置函数和测试函数
        for m in reversed(matches):
            if not m.startswith("test_") and m not in ("main", "<module>"):
                return m
        return matches[-1] if matches else None
