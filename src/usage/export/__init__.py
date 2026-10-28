"""把 CodeDendrite 的索引导出成别的工具能直接吃的格式。

archify（agent skill，把 JSON IR 渲染成可交互的单文件 HTML）只校验版面，图上每条边是
agent 读代码时自己写的。这里反过来：边来自索引里静态证实的调用，节点带文件和行号，
再交给 archify 渲染和核对源码。
"""
