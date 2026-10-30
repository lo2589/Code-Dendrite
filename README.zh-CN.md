[English](README.md) | 简体中文

<h1 align="center">CodeDendrite</h1>
<h3 align="center">代码导航：图上的每一条边，都是代码里真实存在的调用。</h3>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=flat-square" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/python-%E2%89%A53.10-3776AB?style=flat-square" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/core-standard_library_only-64748b?style=flat-square" alt="核心只用标准库" />
  <a href="#一行安装然后交给-agent"><img src="https://img.shields.io/badge/skills_for-Claude_Code_%7C_Codex_%7C_Cursor_%7C_OpenCode-7C3AED?style=flat-square" alt="支持 Claude Code、Codex、Cursor、OpenCode 的 agent skill" /></a>
</p>

### 一行安装，然后交给 agent

```bash
npx skills add lo2589/Code-Dendrite        # 3 个 agent skill：understand · learn · rebuild
pip install git+https://github.com/lo2589/Code-Dendrite   # cdd 命令（Python ≥ 3.10，无依赖）
```

然后对 agent 说：

```text
Use cdd-understand to show me how <你的入口函数> works in this repo.
```

## CLI 演示：rg 与 cdd 同屏对比

![rg 与 cdd 的 CLI 动画对比：定位函数、打开源码、追踪调用关系](assets/cli-rg-vs-cdd.gif)

同一个 coding 任务，左侧用 `rg`，右侧用 `cdd`；打开 README 就能直接看到动画。

**用静态分析替代向量搜索。**

检索找的是「长得像的代码」，导航要的是「连得上的代码」。一个调用你函数的函数，跟你的函数在文本上一点都不像——这正是相似度在调用链问题上必然失手的地方。CodeDendrite 不猜相似度，它把仓库解析成一张有因果边的图，然后让你顺着边走。

---

## 当前状态

| 项 | 值 |
|---|---|
| 结构 | `src/` 下五层，`mcp/`、`skills/` 与 `src/` 同层 |
| 运行要求 | Python ≥ 3.10，核心只用标准库 |
| 解析方式 | Python 用标准库 `ast`；其余语言用不依赖第三方库的模式匹配适配器，符号和调用边是启发式的。各语言深度见 [README.md 的语言支持矩阵](README.md#language-support-matrix) |
| 索引 | 不进 git；克隆后先 `cdd rebuild`，数量用 `cdd count` / `cdd status` 看 |

---

## 安装

**方式一：源码直跑（不装）**

```bash
git clone https://github.com/lo2589/Code-Dendrite
cd Code-Dendrite
python3 src/usage/cli/cdd rebuild . --virtual     # 先建索引：除 peek 外的读命令都依赖它
python3 src/usage/cli/cdd count
```

`src/usage/cli/cdd` 会自己把 `src/` 放进子进程的 `PYTHONPATH`，不需要额外设置。

**方式二：装成 `cdd` 命令**

```bash
pip install .                 # 开发时用 pip install -e .
cdd rebuild /path/to/project --virtual
```

**可选依赖**（声明在 `pyproject.toml`）：

```bash
pip install '.[mcp]'          # MCP 服务器需要 mcp 包
pip install '.[test]'         # 跑测试需要 pytest
```

**MCP 服务器**：装好 `mcp` 后，在 `.mcp.json` 里加

```json
{
  "codedendrite": {
    "command": "python3",
    "args": ["/path/to/Code-Dendrite/mcp/server.py", "--root", "/path/to/project"]
  }
}
```

`--root` 指向的项目要先 `cdd rebuild` 过。

**lens 插件**（可选，只对 DeepSeek Harness 有用）：`lens/scripts/install.sh`。仓库路径、profile、端口分别用 `DSH_REPO`、`PROFILE`、`DSH_PORT` 覆盖；脚本里 node 路径和 harness 重启脚本写的是作者本机路径，换机器要先改这两行。

---

## 目录

| 路径 | 内容 |
|---|---|
| `src/scanner/` | **语言扫描器**：源码 → 符号 / 行号 / 导入 / 调用点。`language/`（23 种语言按扩展名路由：20 种解析出符号，yaml / json / toml 只识别不解析）、`calls/`、`hashing/`、`project/`、`store/`、`structure/` |
| `src/analyzer/` | **分析器**：符号 → 锚点身份 + 因果边。`identity/`（结构哈希与漂移）、`anchors/`、`inherit/`、`dataflow/`、`dynamic/`、`path/`、`control_flow/`、`ui/`、`shared/` |
| `src/api/` | **对外查询面**：`inspector/`、`navigator/`、`query/`、`relations/` |
| `src/usage/` | **使用面**：`cli/`、`packets/`、`workflow/`、`profiles/`、`tools/`、`repair/`、`structure/`、`analyze/` |
| `src/view/` | **可视化**：`browser/`、`code_map/`、`relations/`、`timeline/`、`module_tree/`、`pipeline/`、`html/` |
| `lens/` | DSH 插件 `dsh-cdd-lens`：会话轨迹侧栏 + 可交互的锚点图（node 包，独立于 `src/`） |
| `lens-pcb/` | lens 的并行分支（PCB 形态布局），build 戳独立 |
| `mcp/` | MCP 服务器：把上面几层暴露成工具 |
| `skills/` | 给 agent 的三个 skill：`cdd-understand`（理解项目）、`cdd-rebuild`（拓扑重构）、`cdd-learn`（分层带学） |
| `src/tests/` | 测试与夹具 |

依赖方向：`scanner` → `analyzer` → `api` → `usage` / `view`。`scanner`、`analyzer` 不 import 任何上层。剩一处反向依赖：`api/query/cmd_chain.py` 在函数里 import 了 `view.relations`、`view.timeline`、`view.code_map` 和 `usage.profiles.yaml_profile`（共 4 处）。放错层的模块已经挪走，所以 `scan_project`、`debug_workflow`、`generate_module_tree`、`smart_analyze` 和导航器（`start`、`jump` …）从 `usage` 导入，`generate_mermaid_for_project` 从 `view.html.graph` 导入，不再从 `api` 导入。

---

<a id="call-chain"></a>

## 入口 → 打穿

入口是 `mcp/server.py::call_tool`。建好索引后，一条命令把它打穿到实现层：

```bash
python3 src/usage/cli/cdd chain "mcp/server.py::call_tool" --depth 5
```

链会穿透 mcp → usage → analyzer 三层。输出是**树形展开**：同一个函数被几处调用，就在每处各打印一次，所以「行数」和「不同函数数」是两个数：

| 层 | 行数 | 不同函数 |
|---|---:|---:|
| `mcp/` | 15 | 10 |
| `src/usage/` | 36 | 13 |
| `src/analyzer/` | 4 | 1 |
| 合计 | **55** | **24** |

重复最多的是 `_anchor_attr`（14 次）。完整输出（55 行，一行不省）：

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
        [4] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _match_sort_key  src/usage/packets/task_context_packet/anchor.py:68
        [4] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
        [4] _is_test_file  src/usage/packets/task_context_packet/plugin.py:119
    [2] build_level0  src/usage/packets/task_context_packet/anchor.py:275
      [3] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
    [2] build_level1  src/usage/packets/task_context_packet/anchor.py:336
      [3] _find_anchor_area  src/usage/packets/task_context_packet/anchor.py:328
        [4] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _find_anchor_module  src/usage/packets/task_context_packet/plugin.py:123
    [2] build_level2  src/usage/packets/task_context_packet/anchor.py:422
      [3] _build_edge_indexes  src/usage/packets/task_context_packet/anchor.py:250
      [3] _score_related_symbol  src/usage/packets/task_context_packet/anchor.py:391
        [4] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _find_anchor_module  src/usage/packets/task_context_packet/plugin.py:123
  [1] tool_symbol  mcp/server.py:112
    [2] _anchors  mcp/server.py:47
      [3] load_anchors  src/analyzer/anchors/core_load.py:33
    [2] _relations  mcp/server.py:54
    [2] resolve_task_anchor  src/usage/packets/task_context_packet/anchor.py:113
      [3] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _bounded_matches  src/usage/packets/task_context_packet/anchor.py:78
        [4] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _match_sort_key  src/usage/packets/task_context_packet/anchor.py:68
        [4] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
        [4] _is_test_file  src/usage/packets/task_context_packet/plugin.py:119
    [2] build_anchor_packet  src/usage/packets/task_context_packet/anchor.py:622
      [3] _build_edge_indexes  src/usage/packets/task_context_packet/anchor.py:250
      [3] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
  [1] tool_search  mcp/server.py:126
    [2] _anchors  mcp/server.py:47
      [3] load_anchors  src/analyzer/anchors/core_load.py:33
    [2] resolve_task_anchor  src/usage/packets/task_context_packet/anchor.py:113
      [3] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _bounded_matches  src/usage/packets/task_context_packet/anchor.py:78
        [4] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
      [3] _match_sort_key  src/usage/packets/task_context_packet/anchor.py:68
        [4] _anchor_attr  src/usage/packets/task_context_packet/anchor.py:54
        [4] _is_test_file  src/usage/packets/task_context_packet/plugin.py:119
  [1] tool_impact  mcp/server.py:150
    [2] _relations  mcp/server.py:54
    [2] _anchors  mcp/server.py:47
      [3] load_anchors  src/analyzer/anchors/core_load.py:33
  [1] tool_modules  mcp/server.py:194
    [2] _project_summary  mcp/server.py:73
```

**这条链是索引现场算出来的，不是手抄的**：以上数字取自 2026-09-14 的索引。跑同一条命令应当得到同一个起点、同一组文件名；行数、函数数和行号随代码变。

---

## 命令

`cdd` 的实体是 `src/usage/cli/cdd`（无扩展名的 Python 脚本，靠 shebang 执行）。下面用源码直跑的写法；装成命令后把 `python3 src/usage/cli/cdd` 换成 `cdd`。

```bash
cd <repo>
python3 src/usage/cli/cdd status                  # 索引位置、数量、时间
python3 src/usage/cli/cdd rebuild . --virtual     # 全量重建
python3 src/usage/cli/cdd update .                # 增量更新；首次会自动全量建立
python3 src/usage/cli/cdd count                   # 各类因果边数量
python3 src/usage/cli/cdd peek <文件>             # 现场解析一个文件，不需要索引
python3 src/usage/cli/cdd chain <anchor> --depth 12
python3 src/usage/cli/cdd callers <anchor>        # 上行：谁在用它
python3 src/usage/cli/cdd chain2context <anchor> --budget 40000 --output ctx.md
python3 src/usage/cli/cdd draw                    # 生成浏览器版目录浏览器
python3 src/usage/cli/cdd modules <关键词>        # 语义模块
```

`chain2context` 把一条链上所有 anchor 连源码组装成可投喂的上下文；超预算的 anchor 单列一栏，不静默丢。

---

## 五种因果关系

各类数量随代码和扫描范围变，用 `cdd count` 看当前值。

| 类型 | 含义 |
|------|------|
| `call` | A 调用 B |
| `dataflow` | A 的输出流入 B 的输入 |
| `impact` | ≥2 个模块依赖同一目标，改它会波及这些模块 |
| `inherit` | 子类继承父类 |
| `dispatch` | 注册表 / 装饰器 / HTTP 路由分发 |

边一律**静态可解析才建**。解析不到的不会编一个出来——`cdd callers` 对方法零结果时会提示未解析的候选调用点，而不是报告「没人用」。

### 锚点的颗粒度

锚点只到**模块顶层 def 与类方法**。函数体里再嵌套的 `def`（局部 helper、闭包工厂）不单独成锚点：它们的调用边全部记在母函数的 `callees` 下，打开母函数源码就拿到了，没有需要再追问的独立身份。三个例子印证这条规则：

- `src/analyzer/anchors/core_load.py::load_anchors` 内的 `_coerce_callers` / `_coerce_callees`——索引里没有它们的 anchor 条目，但 `load_anchors.callees` 留了字符串痕迹
- `src/usage/packets/task_context_packet/anchor.py::build_anchor_packet` 内的 `_related`——同上
- 这不是漏识别，是锚点生成器只走 `tree.body`（顶层 + 类方法层）的设计取舍

---

## AML Coding 记忆服务 0.2（`src/usage/aml_coding`）

为 [Agent Memory Leaderboard](https://agentmemoryleaderboard.ai) Coding 赛道提供 Add/Search 接口。只用 `text-embedding-v4` 一个模型：不调 LLM，不用 rerank，不克隆仓库。

**Add**：输入 `request_id, user_id, session_id, messages[{role, content, timestamp?}]`，每个请求是一个已解决的编码任务。处理步骤：

1. 对整段轨迹算指纹。其他 `user_id` 已经存过的同一段轨迹，只记一行引用。
2. 解析事件：issue、思考、工具调用及其结果。被拆成多条消息的结果会拼回原样。
3. 按时间顺序回放文件：`Read` 记下带行号的内容，`Edit` 按 `old_string → new_string` 修改并记下改动落在哪一行，`Write` 整体替换文件。
4. 用 Python `ast` 抽取 anchor（`文件::类.方法` 及其行范围）和同一文件内的调用边。只读过片段的文件改用 `def`/`class` 行兜底。
5. 把本次任务的 read / edit / test / 带类名或路径的 mention 事件挂到对应的 anchor 上。
6. 每个被碰过的 anchor 生成一个单元，包含代码、调用和被调用关系、本次任务的 diff，每个单元不超过约 1,500 tokens。其余内容切成 100 词的块，步长 80。
7. 只给普通块算向量，然后在一个事务里写入。

写入落盘后才返回 200。同一个 `request_id`、相同内容重复提交时幂等，内容不同则返回 409。上限：每段轨迹回放出的代码不超过 2 MB、anchor 不超过 2,000 个；磁盘剩余不足 3 GB 时返回 503。

**Search**：输入 `query, user_id, top_k`。只在这个 `user_id` 引用过的轨迹里检索，分三路：符号和路径精确命中（权重 3）、BM25（全部单元）、向量（只查普通块），三路按加权倒数排名融合。每个 anchor 只出现一次。其他任务碰过同一个符号时只附一个指针：最新的排在前面，不附对方的代码，最多占预算的 20%。每次最多返回 `top_k` 条、约 12k tokens，格式为 `{"data": [{id, content, score, created_at}]}`。只返回证据，不生成答案。

```bash
mkdir -p ~/.config/cdd-aml && (umask 077; cat > ~/.config/cdd-aml/dashscope.key)   # 百炼密钥
cd src && python3 -m usage.aml_coding serve --data ~/cdd-aml-data --key-file <存 AML 接口密钥的文件> --port 8014
python3 -m usage.aml_coding stats --data ~/cdd-aml-data    # 调用次数、向量 token 数、花费
```

---

## 测试

```bash
cd <repo>
pip install '.[test]'
PYTHONPATH=src python3 -m pytest src/tests src/tests/tests -q
```

---

## 生成物

这些是产物，不手改，改了要用 `cdd rebuild` 重生：

- `.codedendrite/` — anchors.json / relations.json / module_tree*.json / 各种 .html
- `.code_genome_db.json`、`.code_hash_db.json`（带 `.lock`）

`.codedendrite_ignore` 控制扫描排除范围（当前排除 `.cache/`、`backup/`、`doc/`，`lens/` 与 `lens-pcb/` 的打包产物 `lib/` 和设计稿 `design/`，以及 `lens/output/`）。
