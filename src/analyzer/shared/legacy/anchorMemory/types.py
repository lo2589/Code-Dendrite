"""
types.py — anchorMemory 数据结构定义
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    """观察来源，决定写入权重。"""
    HUMAN = "human"          # 人类工程师修改代码  权重最高
    TEST = "test"            # 测试用例覆盖的行为  高权重
    AI_CONSENSUS = "ai_consensus"  # AI 多次一致观察  中权重
    AI_SINGLE = "ai_single"  # 单次 AI 推断        低权重


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Observation:
    """
    一次观察记录（未固化的原始数据）。

    观察积累到一定阈值后，才写入 MemoryEntry.semantic。
    防止单次 AI 推断污染锚点记忆。
    """
    content: str
    source: SourceType
    confidence: float          # 0.0 – 1.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    context: str = ""          # 触发此观察的问题/场景


@dataclass
class Milestone:
    """
    关键事件记录（代码经历了什么）。

    只在以下情况写入：
      - 代码结构发生实质变化（hash 变了）
      - 发现 bug 并修复
      - 被成功/失败替换
      - 性能或安全特性发现
    """
    event: str                 # "refactor" | "bug_fix" | "replaced" | "perf_found" | ...
    detail: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    old_hash: str = ""
    new_hash: str = ""
    author: str = ""           # "human" | "ai:{model}"


@dataclass
class MemoryEntry:
    """
    一个锚点的完整记忆状态。

    设计为"状态机"而非"log"：
      semantic 是当前最佳理解（持续被更新，不是追加）
      milestones 只记录关键事件（不记录每次 AI 访问）
      stats 是统计摘要（不是原始记录）
    """
    anchor_id: str

    # 当前状态（持续更新）
    semantic: str = ""                     # 对这段代码的最佳语义描述
    confidence: float = 0.0               # 0.0=未知, 1.0=高度确定
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    # 关键事件历史（精简，非完整 log）
    milestones: list[Milestone] = field(default_factory=list)

    # 待固化的观察池（积累到阈值才写入 semantic）
    pending_observations: list[Observation] = field(default_factory=list)

    # 统计摘要
    ai_access_count: int = 0
    human_modified_count: int = 0
    bug_count: int = 0
    replacement_attempts: int = 0
    replacement_successes: int = 0

    # 已知行为模式（高置信度的场景→行为映射）
    behavior_patterns: list[dict] = field(default_factory=list)
    # 示例: [{"scenario": "admin用户", "behavior": "跳过IP检查", "confidence": 0.9}]

    # 相关锚点（语义关联，不只是调用关系）
    semantic_links: list[dict] = field(default_factory=list)
    # 示例: [{"target": "validate_lite", "relation": "语义等价，少了IP检查"}]

    def to_dict(self) -> dict:
        return {
            "anchor_id": self.anchor_id,
            "semantic": self.semantic,
            "confidence": self.confidence,
            "last_updated": self.last_updated,
            "milestones": [
                {
                    "event": m.event,
                    "detail": m.detail,
                    "timestamp": m.timestamp,
                    "old_hash": m.old_hash,
                    "new_hash": m.new_hash,
                    "author": m.author,
                }
                for m in self.milestones[-10:]  # 只保留最近 10 个 milestone
            ],
            "stats": {
                "ai_access_count": self.ai_access_count,
                "human_modified_count": self.human_modified_count,
                "bug_count": self.bug_count,
                "replacement_attempts": self.replacement_attempts,
                "replacement_successes": self.replacement_successes,
            },
            "behavior_patterns": self.behavior_patterns,
            "semantic_links": self.semantic_links,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        entry = cls(anchor_id=data["anchor_id"])
        entry.semantic = data.get("semantic", "")
        entry.confidence = data.get("confidence", 0.0)
        entry.last_updated = data.get("last_updated", "")

        stats = data.get("stats", {})
        entry.ai_access_count = stats.get("ai_access_count", 0)
        entry.human_modified_count = stats.get("human_modified_count", 0)
        entry.bug_count = stats.get("bug_count", 0)
        entry.replacement_attempts = stats.get("replacement_attempts", 0)
        entry.replacement_successes = stats.get("replacement_successes", 0)

        entry.behavior_patterns = data.get("behavior_patterns", [])
        entry.semantic_links = data.get("semantic_links", [])

        for m in data.get("milestones", []):
            entry.milestones.append(Milestone(
                event=m.get("event", ""),
                detail=m.get("detail", ""),
                timestamp=m.get("timestamp", ""),
                old_hash=m.get("old_hash", ""),
                new_hash=m.get("new_hash", ""),
                author=m.get("author", ""),
            ))

        return entry
