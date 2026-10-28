"""扫描层共用的底层模块：数据类型、身份哈希、忽略规则。

它们原来放在 analyzer/shared 下，scanner 只好反向 import analyzer。
搬到最底层后，依赖只剩一个方向：scanner → analyzer → api → usage / view。
"""
