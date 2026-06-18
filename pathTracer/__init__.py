"""
pathTracer — 管线路径追踪器

核心理念（ComfyUI 管线思维）：
  代码不是文本，是数据流过节点的管线。
  每个函数是一个节点：输入插槽 → 处理 → 输出插槽。
  PathTracer 从入口出发，按已知条件剪枝，追踪到目标出口。

用法：
    from pathTracer import PathTracer, PipelineNode

    tracer = PathTracer(project_root="/path/to/project")
    result = (
        tracer
        .from_entry("handle_request")
        .given("request.type", "A")
        .given("user.is_admin", False)
        .until("db.save")
        .run()
    )

    print(result.path)          # 调用链节点列表
    print(result.to_pipeline()) # 管线 JSON，可接可视化
    result.replace_node("validate_user", "validate_user_lite")
"""

from .tracer import PathTracer
from .node import PipelineNode
from .replacer import NodeReplacer
from .compatibility import check_compatibility

__all__ = ["PathTracer", "PipelineNode", "NodeReplacer", "check_compatibility"]
