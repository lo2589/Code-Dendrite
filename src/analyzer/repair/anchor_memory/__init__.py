"""
anchorMemory — Anchor 情节记忆系统

核心理念：
  代码锚点不只是"书签"，而是有历史的知识单元。
  每次 AI 分析、人类修改、测试覆盖，都积累到对应的锚点上。
  随着使用次数增加，锚点对这段代码的理解越来越准确。

设计原则（防止屎山）：
  - 不是 append log，而是状态机（当前状态持续更新）
  - 只在代码实际变更、重大发现时写入 milestone
  - confidence 机制：多次一致观察才固化
  - 写入权重分层：人类 > 测试 > AI 多次一致 > 单次AI推断

用法：
    from analyzer.repair.anchor_memory import AnchorMemory

    mem = AnchorMemory(project_root="/path/to/project")
    mem.observe("validate_user", "admin用户跳过IP检查", source="ai", confidence=0.7)
    mem.record_milestone("validate_user", event="bug_fix", detail="边界条件修复")
    info = mem.get("validate_user")
    print(info.confidence)  # 随观察次数提升
"""

from analyzer.repair.anchor_memory.memory import AnchorMemory
from analyzer.shared.legacy.anchorMemory.types import MemoryEntry, Milestone, Observation, RiskLevel

__all__ = ["AnchorMemory", "MemoryEntry", "Milestone", "Observation", "RiskLevel"]
