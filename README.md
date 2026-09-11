# CodeDendrite: 基于 AST 的代码因果导航系统

**用静态分析替代向量搜索，让 7B 小模型也能精确理解项目结构。**

## V1.20：JS/TS真实作用域与异步调用链

V1.20修复了JS/TS链路中四类会直接误导读图的问题：注释/字符串被识别成类、嵌套函数只有一行、重复调用导致`call_sites`与`callees`错位、接收者方法被模糊绑定到同名测试函数。对象回调现在挂在所属函数下；相对`import/require`、本地工厂方法、静态HTTP路由和Worker消息均生成可追踪的精确边。

```bash
cdd rebuild /path/to/project --virtual
cdd chain src/client.js::factory.LensPanel /path/to/project --depth 12
```

插件实链已能贯通：`LensPanel → loadState → HTTP handler → projector.schedule → launch → Worker message handler → project → buildGraph`。HTTP/Worker跳转在`relations.json`中标记为`dispatch`。详见[CDD V1.20 JS/TS链路修复](doc/CDD_V1_20_JSTS_SCOPE_CALL_CHAIN.md)。

---

## 总体架构

```mermaid
graph TB
    SRC["源代码<br/>157 文件 · 12 语言"]

    subgraph EXTRACT["提取层 (codeGenome)"]
        PY["Python AST"]
        CPP["C++ AST"]
        JAVA["Java AST"]
        TS["TypeScript AST"]
        OTHER["Go / Rust / Swift / ..."]
    end

    subgraph FOUNDATION["基础数据层"]
        ANCHORS["anchors.json<br/>1312 锚点"]
        RELATIONS["relations.json<br/>1794 边"]
    end

    subgraph ANALYSIS["分析层"]
        PP["路径策略"]
        CC["能力候选提取"]
        MT["模块树 V2"]
        TCP["任务上下文包"]
    end

    subgraph OUTPUT["输出层"]
        JSON_OUT["JSON"]
        HTML_OUT["HTML"]
        COMPACT["compact 文本<br/>≤500 tokens"]
    end

    SRC --> EXTRACT
    PY --> ANCHORS
    CPP --> ANCHORS
    JAVA --> ANCHORS
    TS --> ANCHORS
    OTHER --> ANCHORS
    ANCHORS --> RELATIONS
    RELATIONS --> PP
    PP --> CC
    CC --> MT
    MT --> TCP
    MT --> JSON_OUT
    MT --> HTML_OUT
    TCP --> COMPACT
    TCP --> JSON_OUT
```

---

## 核心思路

传统 AI 编程工具用 **RAG + 向量搜索**：把代码切块 → 嵌入向量 → 相似度检索。问题是：

- 丢失了函数间的调用关系
- 检索结果没有因果解释
- 小模型拿到碎片后仍然在猜

CodeDendrite 用 **AST 静态分析**：

- 精确到函数/类/方法级别（不是文本块）
- 自动派生 5 种因果关系（call · dataflow · inherit · impact · dispatch）
- 按 token 预算分层投喂（不是塞一堆代码进去）

**结果：7B 模型拿到 400 tokens 的任务包，就能定位到正确的入口和候选。**

---

## 五种因果关系

| 类型 | 数量 | 含义 | 用途 |
|------|------|------|------|
| `call` | 631 | A 函数调用 B 函数 | 追踪执行路径 |
| `dataflow` | 924 | A 的输出流入 B 的输入 | 追踪数据来源 |
| `inherit` | 75 | 子类继承父类 | 理解类层级 |
| `impact` | 127 | 修改 A 会影响 B | 评估改动影响 |
| `dispatch` | 37 | A 分发/路由到 B | 追踪动态调度 |

---

## 数据流水线

```
源代码 → AST 解析 → 锚点提取 → 关系派生 → 路径策略 → 高层锚点检测 → 模块核生成 → 贪心合并 → 模块树 V2 → 任务上下文包
```

五个阶段：

| 阶段 | 输入 | 输出 | 说明 |
|------|------|------|------|
| 提取 | 源代码文件 | 符号 + 哈希 | AST 解析，精确到行号 |
| 索引 | 锚点 | anchors.json + relations.json | 1312 锚点，1794 边 |
| 分析 | 锚点 + 关系 | 282 能力候选 | 路径策略 + 高层检测 + 打分 |
| 合成 | 候选集 | 30 模块 · 41 边 | 贪心合并 + 四格填充 + 信心评级 |
| 投喂 | 模块树 + 查询 | task_context.json | 四级上下文，compact ~400 tokens |

---

## Module Tree V2

首次扫描即可输出项目级功能块导览图。

**不是**函数聚类 + 猜名字；**是**多证据合成 + 置信度评级。

### 模块四格

每个模块必须回答：

```
what:      这个模块做什么
how:       内部怎么实现的
functions: 关键入口和类
role:      对项目的贡献
```

### 状态与信心

| 状态 | 含义 |
|------|------|
| `core_flow` | 主链路必经模块 |
| `independent_capability` | 可独立调用的能力 |
| `support_utility` | 支撑工具 |
| `dormant` | 休眠/未接线 |
| `uncertain` | 证据不足 |

| 信心 | 条件 |
|------|------|
| A | ≥4 类证据一致 |
| B | ≥3 类证据 |
| C | 2 类证据 |
| D | <2 类证据 |

### 当前仓库实测

```
模块总数: 30
边数:     41
状态分布: 19 core_flow, 11 independent_capability
信心分布: 26 A, 4 B
区域覆盖: 15/15 (100%)
假模块:   0
```

---

## Task Context Packet

给小模型/执行 agent 一个当前任务的窄上下文。

### 四级上下文

| 级别 | 内容 | Token 预算 |
|------|------|-----------|
| L0 | 项目一句话 + 顶层区域 | 30-80 |
| L1 | 当前区域 + 模块摘要 | 100-300 |
| L2 | 0-3 个可信候选 + why + next_command | 300-800 |
| L3 | 源码片段（按需，默认不给） | 按需 |

L2 是证据门，不是候选数量生成器。唯一精确符号/文件才直接给下一步；跨文件匹配返回 `ambiguous` 和 alternatives，不会拿同文件符号补齐。v2 只有 `exact` 关系能升级为导航命令。

### compact 输出示例

```
项目: CodeDendrite: 30 个功能模块 (19 core_flow, 11 independent_capability)
当前区域: api | 提供 create_anchor 等入口能力
任务锚点: api/anchors.py::create_anchor
导航置信: resolved/high | 完整 anchor ID

候选:
  C0 create_anchor [任务目标] → expand api/anchors.py::create_anchor
  C1 Anchor [被任务调用 via call] → expand codeTree/anchor_engine.py::Anchor
  C2 generate_all_anchors [调用了任务 via call] → expand api/anchors.py::generate_all_anchors

边: create_anchor→Anchor(call), generate_all_anchors→create_anchor(call)
```

**总共 ~400 tokens，7B-4K 模型吃完后还剩 3.5K 上下文。**

### Task Package 评测合同

生成、定位和官方结果必须分栏，官方 harness 未完整运行时不会产生 solve rate：

```bash
cdd eval validate report.json
cdd eval summary report.json
```

合同说明见 `doc/TASKPACKAGE_EVALUATION_CONTRACT.md`，机器可读 schema 位于 `evaluation/taskpackage_evaluation_v1.schema.json`。

### 完整 Issue 证据包 v2

让 CDD 直接读取完整 issue，并保留从文本信号到单一动作的证据链：

```bash
cdd issue issue.md <PROJECT_PATH> --compact
```

`task_context_packet_v2` 对同级强证据冲突返回 `ambiguous`，且最多生成一个结构化动作。详见 `doc/TASK_CONTEXT_PACKET_V2.md` 和 `schemas/task_context_packet_v2.schema.json`。

v1/v2 共用三条证据通道：只有 `candidates` 可带动作，`alternatives` 和 `boundaries` 只保留证据。v1 缺少 resolution 的投影边统一标记为 `resolution_unavailable`；详见 `doc/EVIDENCE_SEMANTICS_V1_V2.md`。

离线比较已有任务包运行时使用 `cdd replay <TASKS.json> <RUN_DIR> --output <REPORT.json>`。缺失索引的任务会保持 `null`，不会用后验 anchor 命中补齐。详见 `doc/OFFLINE_NAVIGATION_REPLAY.md`。

使用 `cdd snapshot` 保存与 base commit 绑定的每题索引；使用 `cdd issue --session` 和 `cdd action done` 阻止重复动作。详见 `doc/TASK_SNAPSHOTS_AND_ACTION_SESSIONS.md`。

---

## 快速开始

### 全链路生成

```bash
cd tools/CodeDendrite
PYTHONPATH=. python api/cli.py . --module-tree-v2
```

输出：
```
.codedendrite/capability_candidates.json   # 282 候选
.codedendrite/module_tree_v2.json          # 30 模块 · 41 边
.codedendrite/module_tree_v2.html          # 可搜索导览页
```

### Task Context Packet

```bash
# 人用命令
cdd context create_anchor .
cdd context 'api/anchors.py::create_anchor' . --full

# 生成并保存 JSON
PYTHONPATH=. python api/cli.py . --task-context create_anchor

# 直接输出 compact 文本（给小模型用）
PYTHONPATH=. python api/cli.py . --task-context-compact PythonExtractor
```

### 按 YAML 配置展开调用链

`cdd chain --yaml` 会先调用目标项目自己的 YAML 配置加载函数，再用配置值选择注册表、装饰器和动态分派对应的 Anchor。YAML 用于选择链路分支，调用链起点仍由第一个参数指定。与不带 YAML 的“全部候选图”相比，带 YAML 的结果会删除已确定但未选中的分支，因此节点数通常更少。

```bash
# 从真实模块入口展开全部静态可达链路
cd /path/to/project
cdd chain 'main.py::<module>' . \
  --depth 99 \
  --yaml config/runtime.yaml

# 从指定函数开始，只看其下游链路
cdd chain 'code/manager/runtime.py::build_runtime' . \
  --depth 8 \
  --yaml config/runtime.yaml
```

输出头部会显示实际采用的项目加载器、全部激活键；每个由配置选中的节点会显式标注 `[YAML → 注册键]`：

```text
YAML profile: config/runtime.yaml via code/dataset/load_config.py::load_config (12 active registry keys)
YAML selected: answer.parse.normal, cfg.ollama, chat.normal, ...
[2] OllamaProvider*  code/provider/provider.py:362  [YAML → client.ollama]
[1] chat*  code/provider/provider.py:441  [YAML → chat.normal]
[1] trigger_manual*  code/recall/trigger.py:35  [YAML → trigger.manual]
```

说明：

- 使用项目自身已索引的 `config.load`、`yaml.load`、`load_config`、`load_yaml` 或 `parse_yaml` Anchor 解析配置，不写死某个项目路径。
- 若项目加载器因缺少可选依赖而无法导入，安全回退会递归合并 `_BASE_`，再按最终配置选择链路；输出会列出回退方式和被包含文件。
- 支持 `@register` 这类“注册键就是类名”的裸装饰器；配置里的 `YOLOv3`、`CSPResNet` 等名称可直接落到对应 class Anchor。
- class 调用会继续进入 `__init__`；`obj.method()` 会结合局部赋值推断对象类型，避免链路停在类节点。
- `create(cfg)` 这类工厂调用只展开该调用点对应的配置项；配置段内引用的子组件会继续形成父组件到子组件的 YAML 依赖边。
- `main.py::<module>` 表示模块顶层执行入口；先运行 `cdd file main.py .` 可确认入口 Anchor。
- YAML 未提供某项配置时，对应动态分支保留候选，不擅自选择。
- 不带 `--yaml`：展示所有静态候选分支；带 `--yaml`：保留普通调用和 YAML 选中的动态分支。
- 名称后的 `*` 表示该节点由 YAML 选中；`[YAML → key]` 给出选择它的配置键，不表示该函数只能通过 YAML 调用。
- 对 YOLO 这类组件型 YAML，形如 `[from, repeats, component, args]` 的层声明会生成 `YAML component graph`；组件名只有在唯一精确匹配项目内 class Anchor 时才会链接，外部组件显示为 `unresolved`。
- 项目加载器无法导入时会明确显示 `PyYAML.safe_load (fallback)`；不会假装项目加载器执行成功。
- 结果是静态可达链路；反射、运行时生成调用和外部进程调用需要运行时 trace 补充。

### 全部 CLI 命令

| 命令 | 作用 |
|------|------|
| `--module-tree-v2` | 全链路：候选 + 模块树 + HTML |
| `--capability-candidates` | 只生成候选集 |
| `--module-tree-v2-html` | 只渲染 HTML |
| `--module-tree-v2-check` | 检查完整性报告 |
| `--path-policy-check PATH` | 检查路径角色 |
| `--task-context QUERY` | 生成任务上下文包 |
| `--task-context-compact QUERY` | 输出 compact 文本 |

---

## AI Agent Skills

`.kimi-code/skills/` 下有三个开箱即用的 agent skill，让 LLM 编码助手（Kimi Code / Claude Code）直接走 CDD 的导航能力，而不是盲翻文件：

| Skill | 职责 |
|------|------|
| `cdd-understand` | 项目理解：索引 → 枢纽排行 → 模块树 → chain 定位 → task-context 上下文包 |
| `cdd-rebuild` | 拓扑重构：挪代码前先查上下游调用链评估影响面，每步增量重索引验证 |
| `cdd-learn` | 项目学习：L0 全局地图 → L1 模块 → L2 调用链 → L3 数据流，分层带人读懂项目 |

想让其他项目也用上，把 `.kimi-code/skills/` 复制或软链到 `~/.kimi-code/skills/` 即可（新会话生效）。

---

## 锚点数据结构

```python
@dataclass
class Anchor:
    id: str              # "file.py::symbol" 唯一标识
    symbol: str          # 符号名
    file: str            # 相对路径
    line_start: int      # 起始行
    line_end: int        # 结束行
    hash: str            # 结构哈希（秒级变更检测）
    callers: List[str]   # 调用者
    callees: List[str]   # 被调用者
    symbol_type: str     # function / class / method
    drift: str           # ok / stale / missing_symbol / missing_file
    # ... 继承、数据流、AI 记忆等字段
```

---

## 项目结构

```
tools/CodeDendrite/
├── api/                        # 公开 API 层
│   ├── anchors.py              # 锚点管理
│   ├── relations.py            # 关系管理
│   ├── path_policy.py          # 路径策略（三角色分类）
│   ├── capability_candidates.py # 能力候选提取
│   ├── module_tree_v2.py       # 模块树 V2 核心算法
│   ├── task_context_packet.py  # 任务上下文包
│   ├── analysis.py             # 符号搜索
│   └── cli.py                  # CLI 入口
├── codeGenome/                 # 多语言 AST 提取
├── codeTree/                   # 锚点引擎 + 深度分析
├── codeAnalysis/               # 专用及通用语言分析器
├── languages/                  # V1.18 统一语言注册、全量/增量解析管线
├── inheritance/                # Python 继承追踪
├── cpp_inheritance/            # C++ 继承追踪
├── dataFlow/                   # 数据流分析
├── context_builder/            # 上下文构建器
├── anchorRepair/               # 锚点修复
├── anchorMemory/               # AI 记忆
├── pathTracer/                 # 路径追踪
├── smartAnalyzer/              # 智能分析器 V2
├── hash/                       # AST 哈希计算
├── shared/                     # 共享类型（Anchor dataclass）
├── visualize/                  # HTML 可视化
│   └── module_tree_v2.py       # 模块树可视化
├── tests/                      # 测试
│   ├── test_module_tree_v2_smoke.py   # 模块树测试 (20 项)
│   └── test_task_context_smoke.py     # 任务包结构与证据门测试
└── .codedendrite/              # 输出目录
    ├── anchors.json
    ├── relations.json
    ├── module_tree_v2.json
    ├── module_tree_v2.html
    ├── task_context.json
    └── capability_candidates.json
```

---

## 关键技术数据

| 指标 | 数值 |
|------|------|
| 可执行语言 | 20 种（Python、TS/JS、C/C++、Java、Kotlin、Go、Rust、Swift、PHP、Ruby、HTML、C#、Scala、Objective-C、Shell、PowerShell、Vue、Svelte、SQL） |
| 配置路由 | YAML / JSON / TOML；YAML 可用 `cdd chain ... --yaml ...` 选择实际分支 |
| 混合语言边 | V1.18 支持字面量 HTTP method + path 精确桥接；边保留行列、证据与解析状态 |
| 更新一致性 | 全量 rebuild 与增量 update 共用语言适配层；单文件解析失败保留上次有效 Anchor |
| 锚点总数 | 1312（537 function + 647 method + 128 class） |
| 关系总数 | 1794（924 dataflow + 631 call + 127 impact + 75 inherit + 37 dispatch） |
| 源文件数 | 157 |
| 模块数 | 30（19 core_flow + 11 independent_capability） |
| 区域覆盖 | 15/15 (100%) |
| 模块树 JSON | ~99KB |
| 任务包 compact | ~400 tokens |

---

## 与 RAG 向量搜索的对比

| 维度 | RAG + 向量搜索 | CodeDendrite |
|------|---------------|-------------|
| 粒度 | 文本块 | 函数/类/方法 |
| 关系 | 无 | 5 种因果边 |
| 可解释性 | 相似度分数 | 证据链 + 置信度 |
| 增量更新 | 全量重建 | hash 增量检测 |
| 小模型投喂 | 原始代码片段 | 分层预算 compact 文本 |
| 模型依赖 | 需要 embedding model | 纯静态分析，零模型依赖 |

---

**License:** MIT
**更新:** 2026-04-25
