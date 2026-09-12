# CodeDendrite：基于 AST 的代码因果导航系统

**用静态分析替代向量搜索。**

检索找的是「长得像的代码」，导航要的是「连得上的代码」。一个调用你函数的函数，跟你的函数在文本上一点都不像——这正是相似度在调用链问题上必然失手的地方。CodeDendrite 不猜相似度，它把仓库解析成一张有因果边的图，然后让你顺着边走。

---

## 当前状态

| 项 | 值 |
|---|---|
| 结构 | `src/` 下五层，`mcp/`、`skills/` 与 `src/` 同层 |
| 索引 | **9336 个 anchor / 12223 条因果边** |
| 边构成 | call 6594 · dataflow 5185 · impact 291 · inherit 92 · dispatch 61 |
| 测试 | 233 passed / 4 failed（4 个是历史遗留，与目录结构无关） |

---

## 目录

| 路径 | 内容 |
|---|---|
| `src/scanner/` | **语言扫描器**：源码 → 符号 / 行号 / 导入 / 调用点。`language/`（24 种语言路由 + 各语言适配器）、`calls/`、`hashing/`、`project/`、`store/`、`structure/` |
| `src/analyzer/` | **分析器**：符号 → 锚点身份 + 因果边。`identity/`（结构哈希与漂移）、`anchors/`、`inherit/`、`dataflow/`、`dynamic/`、`path/`、`control_flow/`、`ui/`、`shared/` |
| `src/api/` | **对外查询面**：`inspector/`、`navigator/`、`query/`、`relations/` |
| `src/usage/` | **使用面**：`cli/`、`packets/`、`workflow/`、`profiles/`、`tools/`、`repair/`、`structure/`、`analyze/` |
| `src/view/` | **可视化**：`browser/`、`code_map/`、`relations/`、`timeline/`、`module_tree/`、`pipeline/`、`html/`，以及 DSH 插件 `lens/` 与并行分支 `lens-pcb/` |
| `mcp/` | MCP 服务器：把上面几层暴露成工具 |
| `skills/` | agent skills（预留位） |
| `src/tests/` | 测试与夹具 |

依赖单向：`scanner` → `analyzer` → `api` → `usage` / `view`。

---

## 入口 → 打穿

入口是 `mcp/server.py::call_tool`。一条命令把它打穿到实现层：

```bash
python src/usage/cli/cdd chain "mcp/server.py::call_tool" --depth 5
```

输出 **55 个节点**，穿透 mcp → usage → analyzer 三层（`mcp/` 16 个、`src/usage/` 36 个、`src/analyzer/` 4 个）：

```
Chain from 'mcp/server.py::call_tool' (55 entries, direction=down):

[0] call_tool  mcp/server.py:294
  [1] tool_context  mcp/server.py:84
    [2] _anchors  mcp/server.py:47
      [3] load_anchors  src/analyzer/anchors/core_load.py:33
    [2] _relations  mcp/server.py:54
    [2] _module_tree  mcp/server.py:62
    [2] resolve_task_anchor  src/usage/packets/task_context_packet/anchor.py:113
      [3] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _bounded_matches  src/usage/packets/task_context_packet/anchor.py:78
      [3] _match_sort_key  src/usage/packets/task_context_packet/anchor.py:68
    [2] build_level0  src/usage/packets/task_context_packet/anchor.py:275
    [2] build_level1  src/usage/packets/task_context_packet/anchor.py:336
    [2] build_level2  src/usage/packets/task_context_packet/anchor.py:422
```

**这条链是索引现场算出来的，不是手抄的**：跑同一条命令应当得到同一个起点、同一组文件名，数字随代码变。

---

## 命令

`cdd` 的实体是 `src/usage/cli/cdd`（无扩展名的 Python 脚本，靠 shebang 执行）。

```bash
cd <repo>
python src/usage/cli/cdd status                  # 索引位置、数量、时间
python src/usage/cli/cdd rebuild . --virtual     # 全量重建（本仓库约 35 秒）
python src/usage/cli/cdd update .                # 增量更新
python src/usage/cli/cdd peek <文件>             # 现场解析一个文件，不需要索引
python src/usage/cli/cdd chain <anchor> --depth 12
python src/usage/cli/cdd callers <anchor>        # 上行：谁在用它
python src/usage/cli/cdd chain2context <anchor> --budget 40000 --output ctx.md
python src/usage/cli/cdd draw                    # 生成浏览器版目录浏览器
python src/usage/cli/cdd modules <关键词>        # 语义模块
```

`chain2context` 把一条链上所有 anchor 连源码组装成可投喂的上下文；超预算的 anchor 单列一栏，不静默丢。

---

## 五种因果关系

本仓库自身实测（`cdd count`）：

| 类型 | 数量 | 含义 |
|------|------:|------|
| `call` | 6594 | A 调用 B |
| `dataflow` | 5185 | A 的输出流入 B 的输入 |
| `impact` | 291 | ≥2 个模块依赖同一目标，改它会波及这些模块 |
| `inherit` | 92 | 子类继承父类 |
| `dispatch` | 61 | 注册表 / 装饰器 / HTTP 路由分发 |

边一律**静态可解析才建**。解析不到的不会编一个出来——`cdd callers` 对方法零结果时会提示未解析的候选调用点，而不是报告「没人用」。

---

## 测试

```bash
cd <repo>
PYTHONPATH=src python -m pytest src/tests src/tests/tests -q \
  --ignore=src/tests/test_integration.py --ignore=src/tests/test_backend_dispatch.py
```

被 ignore 的两个测试要读写 `../backend`（工作区外的兄弟项目），放权后可一并跑。

---

## 生成物

这些是产物，不手改，改了要用 `cdd rebuild` 重生：

- `.codedendrite/` — anchors.json / relations.json / module_tree*.json / 各种 .html
- `.code_genome_db.json`、`.code_hash_db.json`（带 `.lock`）

`.codedendrite_ignore` 控制扫描排除范围（当前排除 `.cache/`、`backup/`，以及 lens 的打包产物 `lib/`、设计稿、playwright 产物）。
