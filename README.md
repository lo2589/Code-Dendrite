# CodeDendrite: 基于 AST 的代码因果导航系统

**用静态分析替代向量搜索。**

检索找的是「长得像的代码」，导航要的是「连得上的代码」。一个调用你函数的函数，跟你的函数在文本上一点都不像——这正是相似度在调用链问题上必然失手的地方。CodeDendrite 不猜相似度，它把仓库解析成一张有因果边的图，然后让你顺着边走。

---

## 当前版本

**七桶分层 + DSH Session Lens V1.24**

- 代码按职责切成七层，依赖单向：`base`（类型与纯数据）→ `parse`（AST 提取）→ `index`（索引与锚点身份）/ `relate`（因果边）→ `synth`（上层合成）→ `serve`（对外接口）、`view`（呈现）。
- 上行链遇到**基础节点**就标注停住：扇入 ≥ 20 的 anchor（`load_anchors` 这类，被几十上百处调用）是公共底座，不是某条业务链的中间环节，再往上没有增量。结果里照常出现，标 `is_base` 并写明被多少处调用。
- DSH Session Lens V1.24：成功修改事件携带精确项目相对路径，只对改动文件跑 `cdd update --files ... --topology-only`；只读、展开、折叠、Pin、看源码都不触发重索引。

---

## 核心思路

| | RAG + 向量搜索 | CodeDendrite |
|---|---|---|
| 粒度 | 文本块 | 函数 / 类 / 方法 |
| 关系 | 无 | 5 种因果边 |
| 可解释性 | 相似度分数 | 证据链 + 置信度 |
| 增量更新 | 全量重建 | 内容哈希增量检测 |
| 小模型投喂 | 原始代码片段 | 分层预算的紧凑文本 |
| 模型依赖 | 需要 embedding 模型 | 纯静态分析，零模型依赖 |

三件事一起做到才有用：**精确到函数级别的锚点**、**从 AST 派生的因果关系**、**按 token 预算分层的投喂**。少任何一件，小模型拿到的东西都还是碎片。

---

## 五种因果关系

本仓库自身实测（`cdd count`）：

| 类型 | 数量 | 含义 | 用途 |
|------|------:|------|------|
| `dataflow` | 7069 | A 的输出流入 B 的输入 | 追数据来源 |
| `call` | 4033 | A 调用 B | 追执行路径 |
| `impact` | 407 | 改 A 会影响 B | 评估改动影响面 |
| `inherit` | 96 | 子类继承父类 | 理解类层级 |
| `dispatch` | 61 | 注册表 / 装饰器 / HTTP 路由分发 | 追动态调度 |

边一律**静态可解析才建**。解析不到的不会编一个出来——`cdd callers` 对方法零结果时会提示未解析的候选调用点，而不是报告「没人用」。**「没找到调用者」不等于「没被调用」**，这句话写在输出里。

---

## 数据流水线

```
源代码
  │
  ├─ parse/     11 种语言的 AST 适配器 → 符号、行号、导入
  │
  ├─ index/     锚点身份：结构哈希（raw / struct）+ 漂移检测
  │             产物 .codedendrite/anchors.json
  │
  ├─ relate/    从锚点派生 5 种因果边
  │             产物 .codedendrite/relations.json
  │
  └─ serve/     对外接口（78 个导出）+ CLI
                └─ view/   HTML 图、关系图、调用时间线、DSH Lens
```

`rebuild` 全量、`update` 增量，两者共用同一套语言适配层。增量靠内容哈希判定哪些文件真的变了，并把 `resolved` / `failed` 逐文件报出来——解析不了的文件是报告里的一行，不是静默消失。

**锚点身份是这套东西的地基。** `hash_mode: struct` 让改格式不断链，只有真改语义才断；漂移分 `ok / stale / missing_symbol / missing_file / renamed` 五档，`renamed` 单独一档是因为「搬到别处了」和「没了」是两件事。

---

## 两个问题，两套输出

CDD 不假装一个视图能回答所有问题：

**「这里有什么」** — `cdd draw` × `cdd outline`：目录 → 文件 → 类 → 函数。这是字典，用来找东西。

**「这些怎么连的」** — `cdd chain` × `cdd callers` × `cdd show`：顺着因果边走。往下看它调了谁，往上看谁调它。

往下和往上不对称，而且这个不对称本身有信息量：

- **往下越多 → 越重。** 一个 anchor 扇出大，说明它自己干的事多。
- **往上越多 → 越基础。** 扇入大说明它是 `load_anchors` 这类公共底座——**知道它是谁就够了**，再往上每个调用者都会引出一整棵子树，而那一层对「这东西被谁用」没有增量。

---

## 快速开始

```bash
# 索引一个项目（首次自动全量建立，之后增量）
cdd update /path/to/project
cdd status /path/to/project          # 索引位置、数量、更新时间

# 找东西
cdd outline /path/to/project         # 目录/文件/符号大纲
cdd file backend/main.py             # 这个文件里有什么
cdd peek backend/main.py             # 现场解析，不需要索引

# 顺着走
cdd chain 'backend/main.py::Class.method'   # 它调了谁
cdd callers 'backend/main.py::Class.method' # 谁调它
cdd code 'backend/main.py::Class.method' -C 3   # 打印源码，上下各 3 行

# 给小模型的上下文
cdd context 'create_anchor' /path/to/project            # 紧凑文本
cdd context 'create_anchor' /path/to/project --full     # 完整任务包
```

目录永远可以省略，省略就是当前目录；也可以不切目录，路径直接跟在命令后面。

### Python API

```python
from serve import scan_project, list_anchors, load_anchors, load_relations
from serve import analyze_call_chain, trace_variable, find_subclasses
from serve import find_definition, search_symbol, analyze_code

anchors  = load_anchors("/path/to/project")     # {anchor_id: Anchor}
relations = load_relations("/path/to/project")  # {"edges": [...], "meta": {...}}
```

公开接口统一从 `serve` 层出（78 个导出，实现分布在各桶）。新代码建议直接 import 归属层，例如 `from index.api.anchors import load_anchors`。

---

## cdd 命令全集

`cdd` 是人用入口。下面是它现在真正提供的命令。

### 索引

| 命令 | 作用 |
|---|---|
| `cdd update [目录]` | 增量更新；首次自动全量建立 |
| `cdd rebuild [目录]` | 强制全量重建 |
| `cdd status [目录]` | 索引位置、数量、更新时间 |
| `cdd peek <文件>` | 现场解析单个文件，不需要索引 |
| `cdd outline [目录]` | 生成目录/文件/符号大纲 |
| `cdd path-role <路径> [目录]` | 判断路径是源码/测试/生成文件 |

### 查代码

| 命令 | 作用 |
|---|---|
| `cdd file <文件> [目录]` | 文件内的类和函数 |
| `cdd code <函数> [目录] [-C N]` | 打印源码和行号，可带上下文 |
| `cdd anchors <关键词> [目录]` | 按文件路径关键词搜 anchor |
| `cdd find <关键词> [目录]` | 搜调用/继承/数据流关系 |
| `cdd show <节点ID> [目录]` | 展开节点的一层关系 |
| `cdd chain <函数> [目录]` | 它继续调用了谁 |
| `cdd callers <函数> [目录]` | 静态可解析的调用者 |
| `cdd count [目录]` | 各种关系的数量 |
| `cdd registered [目录]` | 装饰器注册关系 |

### 模型上下文与任务包

| 命令 | 作用 |
|---|---|
| `cdd context <问题> [目录]` | 紧凑任务上下文（可加 `--full`） |
| `cdd issue <issue文件> [目录]` | 从完整 issue 生成证据包 v2 |
| `cdd action status\|done <会话> ...` | 记录动作并阻止重复 |
| `cdd debug <文件> "<错误>" [目录]` | 定位可疑函数 |

### 可视化

| 命令 | 作用 |
|---|---|
| `cdd draw [目录]` | 增量更新索引后，按文件画类/函数及调用入出边 |
| `cdd graph [目录] [--focus <函数>]` | 关系图 HTML |
| `cdd map [目录]` | 全项目代码地图 HTML |
| `cdd timeline <函数> [目录]` | 调用链时间线 HTML |
| `cdd summary [目录] [--full]` | 终端里的依赖摘要 |

以上默认自动打开浏览器，加 `--no-open` 只生成文件。

### 语义模块（可选能力）

| 命令 | 作用 |
|---|---|
| `cdd modules <关键词> [目录]` | 搜语义模块 |
| `cdd owner <函数> [目录]` | 这个函数属于哪个模块 |
| `cdd module <模块ID> [目录]` | 看指定模块 |
| `cdd module-graph [目录]` | 模块关系图 |
| `cdd tree build\|check\|render\|candidates [目录]` | Module Tree V2 |

模块树是把 anchor 再往上聚一层，回答「这套代码由哪些能力构成」。它需要额外一轮合成，**默认不参与日常导航**——`chain` / `callers` / `context` 都不依赖它。

### Ignore 配置

| 命令 | 作用 |
|---|---|
| `cdd ignore init [目录]` | 创建默认 `.codedendrite_ignore` |
| `cdd ignore list \| show [目录]` | 分组查看 / 看原始配置 |
| `cdd ignore add <规则> [目录] [--kind scan\|map\|privacy]` | 加规则 |
| `cdd ignore remove <规则> [目录] [--kind ...]` | 删规则 |
| `cdd ignore check <路径> [目录]` | 这个路径最终会被怎么处理 |

改完规则要跑 `cdd rebuild`，旧索引才会彻底更新。

### 临时调试日志（会改源码）

`cdd log-add` / `log-file` / `log-folder` 沿调用链插 `print`，`cdd log-remove` 全部删掉。删完要 `cdd rebuild`，行号才回正。

---

## 项目结构

```
CodeDendrite/
├── base/      类型与纯数据，无依赖       16 个模块
│   ├── shared/          Anchor / Edge 等公共类型
│   ├── anchorMemory/    记忆条目类型
│   ├── anchorRepair/    漂移状态类型
│   ├── codeGenome/      基因库类型
│   ├── inheritance/     Python 继承类型
│   ├── cpp_inheritance/ C++ 继承类型
│   └── dataFlow/        数据流类型
│
├── parse/     AST 提取，只依赖 base      54 个模块
│   ├── languages/       统一语言注册与解析管线
│   ├── codeGenome/      多语言 AST 提取
│   ├── codeAnalysis/    11 种语言的分析器
│   ├── inheritance/     Python 继承提取
│   ├── cpp_inheritance/ C++ 继承提取
│   └── hash/            内容哈希与增量检测
│
├── index/     索引与锚点身份              25 个模块
│   ├── api/             anchors / query 等对外函数
│   ├── codeTree/        anchor_engine 与 anchor_engine_v2
│   ├── inheritance/     类索引
│   └── cpp_inheritance/ C++ 类索引
│
├── relate/    因果边                      53 个模块
│   ├── api/             relations 读写与查询
│   ├── dataFlow/        数据流分析
│   ├── inheritance/     继承追踪
│   ├── cpp_inheritance/ C++ 继承追踪
│   ├── pathTracer/      路径追踪
│   ├── dynamic/         运行时分发痕迹
│   └── codeTree/        深度漂移分析
│
├── synth/     上层合成                    50 个模块
│   ├── api/             task_context_packet / module_tree / action_session
│   ├── smartAnalyzer/   智能分析器
│   ├── context_builder/ 上下文压缩
│   ├── anchorMemory/    锚点记忆
│   ├── anchorRepair/    锚点修复
│   └── codeTree/        anchor CLI / deep drift
│
├── view/      呈现                        27 个模块
│   ├── visualize/       anchor_browser / 代码地图 / 关系图 / 时间线
│   ├── codeAnalysis/    语言可视化入口
│   ├── codeTree/        HTML viewer
│   ├── lens/            DSH Session Lens 插件（当前工作树）
│   └── lens-pcb/        Lens 的并行分支
│
├── serve/     对外接口                    39 个模块
│   ├── api/             公开 API 出口（78 个导出）+ CLI
│   ├── ai_tools/        agent 工具封装
│   └── mcp_server.py    MCP server
│
├── skills/codedendrite/cdd   人用 CLI（住在包外面，见下）
├── schemas/                  机器可读 schema
└── tests/                    按层 + 按版本组织
```

**依赖方向是单向的**：`serve / view` → `synth` → `index / relate` → `parse` → `base`。反过来不成立。

> `cdd` 的源码不在包内，在 `skills/codedendrite/cdd`。它 `parents[2]` 定位仓库根，所以为什么放在那个深度不是随便定的。改它不用重装包。

---

## 关键技术数据

本仓库自测（`cdd status` / `cdd count`）：

| 指标 | 数值 |
|------|------|
| 锚点总数 | **3795** — function 2280 · method 918 · css_rule 226 · class 209 · module 108 · dom_id 54 |
| 因果边 | **11666** — dataflow 7069 · call 4033 · impact 407 · inherit 96 · dispatch 61 |
| 源文件 | 391 |
| 支持语言 | 11 种 — Python · TypeScript/JavaScript · C/C++ · Java · Kotlin · Go · Rust · Swift · PHP · Ruby · HTML |
| 公开 API | 78 个导出 |
| 锚点身份 | 结构哈希，`raw` / `struct` 两种模式 |
| 漂移检测 | 5 档 — ok / stale / missing_symbol / missing_file / renamed |
| 任务包 compact | 单次查询实测 283 tokens |

**已知边界**：静态可达链路只覆盖能静态解析的调用。反射、运行时生成、外部进程调用需要运行时 trace 补充——`cdd callers` 会在方法零结果时明确提示这一点，而不是让你把「没找到」读成「没被调用」。

---

## 锚点数据结构

```python
@dataclass
class Anchor:
    id: str                  # "相对路径::符号" 唯一标识
    symbol: str              # 符号名；None 表示整个文件
    file: str                # 项目相对路径
    line_start: int
    line_end: int
    column_start: int
    column_end: int
    hash: str                # 结构哈希
    signature: str
    qualified_name: str
    imports: list[str]
    code: str                # 符号源码

    # 关系（由 relate/ 填充）
    callers: list[str]
    callees: list[str]
    call_sites: list[dict]
    inputs: list[dict]
    outputs: list[dict]

    # 继承
    parent_classes: list[str]
    overrides: str | None
    overridden_by: list[str]
    mro: list[str]
    own_methods: list[str]
    effective_methods: dict[str, str]

    # 身份与漂移
    symbol_type: str         # function / method / class / module / dom_id / css_rule
    language: str
    drift: str               # ok / stale / missing_symbol / missing_file / renamed
    description: str

    # 控制流虚拟块与注册表
    is_virtual: bool
    virtual_kind: str | None
    parent_anchor: str | None
    scope_label: str | None
    block_metadata: dict
    registered_as: str | None

    observations: list[str]  # 记忆条目
```

---

## 模块树（可选）

模块树把 anchor 再聚一层成「语义模块」，回答的是**「这套代码由哪些能力构成」**，不是「有哪些文件」。它不是函数聚类加猜名字，是多证据合成加置信度评级：每个模块要说清 `what / how / functions / role` 四格，按区域覆盖和证据条数给 A/B/C/D 信心。

它需要额外一轮合成，**日常导航不需要它**。`cdd chain` / `cdd callers` / `cdd context` 全部只依赖 anchors + relations。要看的时候：

```bash
cdd tree check          # 覆盖率和低置信模块
cdd tree build          # 生成并打开 HTML
cdd modules <关键词>     # 直接搜
```

---

## DSH Session Lens

`view/lens/` 是插进 DeepSeek Harness 的插件，把仓库的真实 anchor 图浮在对话上面：被 agent 看过、改过的点亮，被 compaction 拿走的变淡。骨架是 CDD 的静态索引边，会话轨迹在上面上色。

亮度不是估的，是从 `session.surface` 直接读出来的——**一次 compaction 之后，图上直接看得见这轮把哪些代码从模型脑子里拿走了**。代码里没有边，图上就是断开的；先后碰过两个不相干的函数，不会被连成一条假路径。

---

**License:** MIT
