"""
memory.py — AnchorMemory 核心

管理锚点的情节记忆：观察积累、confidence 计算、milestone 记录。

写入条件（严格控制，防止屎山）：
  semantic 更新：新观察与当前 semantic 置信度差距 > 阈值
  milestone 写入：代码 hash 变化 / bug发现 / 替换事件
  pending 清理：定期合并相似观察，淘汰低置信度观察
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from analyzer.shared.legacy.anchorMemory.types import (
    MemoryEntry,
    Milestone,
    Observation,
    SourceType,
    RiskLevel,
)


# 权重配置
SOURCE_WEIGHTS = {
    SourceType.HUMAN: 1.0,
    SourceType.TEST: 0.85,
    SourceType.AI_CONSENSUS: 0.6,
    SourceType.AI_SINGLE: 0.25,
}

# 观察固化阈值（pending 中相似观察达到此数量才写入 semantic）
CONSENSUS_THRESHOLD = 3
CONFIDENCE_UPDATE_THRESHOLD = 0.15  # confidence 差距超过此值才更新 semantic


class AnchorMemory:
    """
    锚点情节记忆管理器。

    参数：
        project_root: 项目根目录
        memory_path:  记忆数据库路径（默认 .codedendrite/memory.json）
    """

    def __init__(self, project_root: str, memory_path: Optional[str] = None):
        self.root = Path(project_root)
        self.memory_path = Path(memory_path) if memory_path else (
            self.root / ".codedendrite" / "memory.json"
        )
        self._entries: dict[str, MemoryEntry] = {}
        self._loaded = False
        self._dirty = False

    # ── 核心写入接口 ─────────────────────────────────────────

    def observe(
        self,
        anchor_id: str,
        content: str,
        source: str = "ai_single",
        confidence: float = 0.5,
        context: str = "",
    ) -> bool:
        """
        记录一次对锚点的观察。

        返回 True 表示观察已固化到 semantic，False 表示进入 pending 等待积累。

        写入规则：
          - source=human：直接固化，权重最高
          - source=test：直接固化
          - source=ai_*：进入 pending，积累到阈值后固化
        """
        self._ensure_loaded()
        entry = self._get_or_create(anchor_id)

        source_type = SourceType(source) if source in SourceType._value2member_map_ else SourceType.AI_SINGLE
        weight = SOURCE_WEIGHTS[source_type]
        weighted_confidence = confidence * weight

        obs = Observation(
            content=content,
            source=source_type,
            confidence=weighted_confidence,
            context=context,
        )

        # 人类和测试来源：直接固化
        if source_type in (SourceType.HUMAN, SourceType.TEST):
            self._solidify(entry, obs)
            entry.ai_access_count += (0 if source_type == SourceType.HUMAN else 0)
            entry.human_modified_count += (1 if source_type == SourceType.HUMAN else 0)
            self._dirty = True
            return True

        # AI 来源：进入 pending
        entry.ai_access_count += 1
        entry.pending_observations.append(obs)

        # 检查是否达到固化阈值
        solidified = self._try_solidify_from_pending(entry)
        self._dirty = True
        return solidified

    def record_milestone(
        self,
        anchor_id: str,
        event: str,
        detail: str,
        old_hash: str = "",
        new_hash: str = "",
        author: str = "system",
    ):
        """
        记录关键事件（代码经历了什么）。

        应该在以下场景调用：
          - hash 检测到变更后
          - 发现并修复 bug 后
          - 节点替换成功/失败后
        """
        self._ensure_loaded()
        entry = self._get_or_create(anchor_id)

        milestone = Milestone(
            event=event,
            detail=detail,
            old_hash=old_hash,
            new_hash=new_hash,
            author=author,
        )
        entry.milestones.append(milestone)

        # 更新统计
        if event == "bug_fix":
            entry.bug_count += 1
        elif event == "replacement_attempt":
            entry.replacement_attempts += 1
        elif event == "replacement_success":
            entry.replacement_successes += 1

        # hash 变更时降低 confidence（代码变了，之前的理解可能过时）
        if event in ("refactor", "code_changed") and entry.confidence > 0.3:
            entry.confidence = max(0.3, entry.confidence - 0.2)

        entry.last_updated = datetime.now().isoformat()
        self._dirty = True

    def add_behavior_pattern(
        self,
        anchor_id: str,
        scenario: str,
        behavior: str,
        confidence: float = 0.8,
    ):
        """记录已知的行为模式（场景→行为映射）。"""
        self._ensure_loaded()
        entry = self._get_or_create(anchor_id)

        # 检查是否已有相同场景
        for pattern in entry.behavior_patterns:
            if pattern.get("scenario") == scenario:
                pattern["behavior"] = behavior
                pattern["confidence"] = max(pattern["confidence"], confidence)
                self._dirty = True
                return

        entry.behavior_patterns.append({
            "scenario": scenario,
            "behavior": behavior,
            "confidence": confidence,
        })
        self._dirty = True

    def add_semantic_link(
        self,
        anchor_id: str,
        target: str,
        relation: str,
    ):
        """记录语义关联（不只是调用关系）。"""
        self._ensure_loaded()
        entry = self._get_or_create(anchor_id)

        for link in entry.semantic_links:
            if link.get("target") == target:
                link["relation"] = relation
                self._dirty = True
                return

        entry.semantic_links.append({"target": target, "relation": relation})
        self._dirty = True

    # ── 读取接口 ─────────────────────────────────────────────

    def get(self, anchor_id: str) -> Optional[MemoryEntry]:
        """获取锚点记忆。"""
        self._ensure_loaded()
        return self._entries.get(anchor_id)

    def get_semantic(self, anchor_id: str) -> str:
        """快捷获取语义描述。"""
        entry = self.get(anchor_id)
        return entry.semantic if entry else ""

    def get_confidence(self, anchor_id: str) -> float:
        """快捷获取置信度。"""
        entry = self.get(anchor_id)
        return entry.confidence if entry else 0.0

    def get_low_confidence_anchors(self, threshold: float = 0.4) -> list[str]:
        """找出置信度低的锚点，需要重新验证。"""
        self._ensure_loaded()
        return [
            aid for aid, entry in self._entries.items()
            if entry.confidence < threshold and entry.semantic
        ]

    def get_summary(self, anchor_id: str) -> str:
        """
        生成锚点记忆的简要摘要（适合放入 AI 上下文）。
        """
        entry = self.get(anchor_id)
        if not entry or not entry.semantic:
            return ""

        lines = [f"[记忆] {anchor_id}"]
        lines.append(f"  语义: {entry.semantic}")
        lines.append(f"  置信度: {entry.confidence:.2f}")

        if entry.behavior_patterns:
            lines.append("  已知行为:")
            for p in entry.behavior_patterns[:3]:
                lines.append(f"    {p['scenario']} → {p['behavior']}")

        if entry.milestones:
            last = entry.milestones[-1]
            lines.append(f"  最近事件: {last.event} ({last.timestamp[:10]})")

        return "\n".join(lines)

    def get_all_summaries(self, min_confidence: float = 0.3) -> str:
        """
        生成所有高置信度锚点的摘要（用于 context_builder）。
        """
        self._ensure_loaded()
        summaries = []
        for aid, entry in self._entries.items():
            if entry.confidence >= min_confidence and entry.semantic:
                summaries.append(self.get_summary(aid))
        return "\n\n".join(summaries)

    # ── 持久化 ───────────────────────────────────────────────

    def save(self):
        """保存到磁盘（原子写入）。"""
        if not self._dirty:
            return

        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.memory_path.with_suffix(".tmp")

        data = {
            "version": "1.0",
            "updated": datetime.now().isoformat(),
            "entries": {
                aid: entry.to_dict()
                for aid, entry in self._entries.items()
            }
        }

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        os.replace(tmp, self.memory_path)
        self._dirty = False

    def cleanup(self, max_pending: int = 20, max_milestones: int = 10):
        """
        清理过期数据，防止无限膨胀。

        - 淘汰 pending 中低置信度的旧观察
        - 只保留最近 N 个 milestone
        """
        self._ensure_loaded()
        for entry in self._entries.values():
            # pending 超过限制：按置信度排序，保留最高的
            if len(entry.pending_observations) > max_pending:
                entry.pending_observations.sort(
                    key=lambda o: o.confidence, reverse=True
                )
                entry.pending_observations = entry.pending_observations[:max_pending]

            # milestone 超过限制：保留最新的
            if len(entry.milestones) > max_milestones:
                entry.milestones = entry.milestones[-max_milestones:]

        self._dirty = True

    # ── 私有 ─────────────────────────────────────────────────

    def _ensure_loaded(self):
        if self._loaded:
            return
        if self.memory_path.exists():
            with open(self.memory_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for aid, entry_data in data.get("entries", {}).items():
                self._entries[aid] = MemoryEntry.from_dict(entry_data)
        self._loaded = True

    def _get_or_create(self, anchor_id: str) -> MemoryEntry:
        if anchor_id not in self._entries:
            self._entries[anchor_id] = MemoryEntry(anchor_id=anchor_id)
        return self._entries[anchor_id]

    def _solidify(self, entry: MemoryEntry, obs: Observation):
        """将观察固化到 semantic。"""
        new_confidence = min(1.0, entry.confidence + obs.confidence * 0.3)

        # 只在置信度有显著提升时更新 semantic 文本
        if abs(new_confidence - entry.confidence) > CONFIDENCE_UPDATE_THRESHOLD or not entry.semantic:
            entry.semantic = obs.content
            entry.confidence = new_confidence
            entry.last_updated = datetime.now().isoformat()

    def _try_solidify_from_pending(self, entry: MemoryEntry) -> bool:
        """
        检查 pending 观察是否达到固化阈值。

        策略：找出内容相似的观察，若数量 >= CONSENSUS_THRESHOLD，固化。
        """
        if len(entry.pending_observations) < CONSENSUS_THRESHOLD:
            return False

        # 简化版：只检查最近 N 个观察的平均置信度
        recent = entry.pending_observations[-CONSENSUS_THRESHOLD:]
        avg_confidence = sum(o.confidence for o in recent) / len(recent)

        if avg_confidence >= 0.5:
            # 取置信度最高的观察内容
            best = max(recent, key=lambda o: o.confidence)
            self._solidify(entry, best)
            # 清空已固化的 pending
            entry.pending_observations = entry.pending_observations[:-CONSENSUS_THRESHOLD]
            return True

        return False
