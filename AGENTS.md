# Codebase Knowledge Graph (codebase-memory-mcp)

THIS PROJECT USES codebase-memory-mcp AND codegraph FOR STRUCTURED CODE CONTEXT.
ALWAYS PREFER MCP GRAPH TOOLS (search_graph, trace_path, get_code_snippet)
OVER GLOB/GREP/FILE-SEARCH FOR CODE DISCOVERY.

## Priority Order

1. `search_graph` — find functions, classes, routes, variables by pattern
1. `trace_path` — trace who calls a function or what it calls
1. `get_code_snippet` — read specific function/class source code
1. `query_graph` — run Cypher queries for complex patterns
1. `get_architecture` — high-level project summary

## When to FALL BACK to grep/glob

- Searching for string literals, error messages, config values
- Searching non-code files (Dockerfiles, shell scripts, configs)
- When MCP tools return insufficient results

<!-- codebase-memory-mcp:start -->

# AGENTS.md 工作规则

**请务必使用中文回复**

## 核心原则

### 1. 先思考，后编码

- 明确陈述假设。如果不确定，宁可提问也不要猜测。
- 存在歧义时，给出多种解释。
- 如果有更简单的方案，应提出反对。
- 感到困惑时停下来。指出不清楚的地方。

### 2. 简单至上

- 用最少代码解决问题。不做投机性内容。
- 不超出需求范围。不为一次性代码做抽象。
- 检验标准：资深工程师会说这过度复杂吗？如果是，就简化。

### 3. 精准修改

- 只动必须改的地方。只清理自己的遗留问题。
- 不要"改进"相邻的代码、注释或格式。
- 不要重构未损坏的部分。匹配现有风格。

### 4. 目标驱动执行

- 定义成功标准。循环直到验证通过。
- 不要照搬步骤。定义成功并迭代。
- 强有力的成功标准让你能独立循环。

### 5. 模型仅用于判断性工作

- 用我（模型）做：分类、起草、总结、信息提取。
- 不要用我做：路由、重试、确定性转换。
- 如果代码能回答，就让代码回答。

### 6. Token 预算不是建议

- 每任务：4,000 token。每会话：30,000 token。
- 接近预算时，总结并重新开始。
- 暴露超出预算的情况。不要静默超限。

### 7. 显式冲突，不要平均处理

- 如果两种模式矛盾，选择其中一种（更新/经过更多测试的）。
- 解释原因。标记另一种待清理。
- 不要混合冲突的模式。

### 8. 先读后写

- 添加代码前，阅读导出项、直接调用方、共享工具。
- "看起来正交"是危险的。如果不确定代码为何如此组织，请提问。

### 9. 测试验证意图，而不仅是行为

- 测试必须编码"为什么"行为重要，而不仅是"做什么"。
- 当业务逻辑变更时，一个不会失败的测试就是错误的。

### 10. 每个重要步骤后设置检查点

- 总结已完成、已验证、剩余的内容。
- 不要从一个无法回溯的状态继续。
- 如果失去头绪，停下来重新陈述。

### 11. 遵循代码库的约定，即使你不认同

- 在代码库内，遵循规范 > 个人品味。
- 如果你认为某个约定有害，提出来。不要静默分叉。

### 12. 响亮地失败

- 如果任何内容被静默跳过，"已完成"就是错误的。
- 有任何测试被跳过，"测试通过"就是错误的。
- 默认暴露不确定性，而非隐藏它。

______________________________________________________________________

## 实验决策记录

### DECISION: 不需要多 Epoch 验证校准实验趋势稳定

- 基线单 Epoch 后已开始过拟合，多 Epoch 无意义

### DECISION: 融合公式优化策略 (2026-08-06)

**背景**：当前线上公式 `score = ctr * (1+cvr)` 导致 CTR 过度优化

**第零阶段 v1**：`ctr^0.3 * cvr^1.7`（指数加权）

- 结果：❌ 严重负向（CTR -38.4%, CVR +1.2%）
- 原因：指数放大效应过于极端

**第零阶段 v2**：`0.6*ctr + 0.5*cvr`（加法融合）

- 结果：⚠️ PV 维度正向（CTR -11.9%, PV_CVR +16.7%, 净收益 +4.8%）
- 教训：加法融合远优于指数融合，CTR/CVR 权重比 1.2:1 是合理区间

**第零阶段 v3**：`0.3*ctr + 0.7*cvr`（加法融合）

- 状态：🔄 进行中
- 预期：进一步提升 CVR 权重（权重比 0.43:1）

**第一阶段**：场景 mask + CVR loss 权重 + 辅助任务

- 状态：✅ 配置文件已完成（v17_scene_mask）
- 关键改动：CTR/CVR 场景 mask、CVR weight 2.0、chajia/search 辅助任务、lifecycle_tags grouped_auc
- 基于 chajia_click_seq2，实现 Issue #1 全部需求

**样本管道优化**：

- 状态：✅ 已完成
- 场景标记：is_home_scene, is_search_scene, is_chajia_scene
- ~~比价负采样~~ **已废弃**：request_id=NULL 导致 sq56 特征关联失败，回填方案特征表 match_rate=0%。改为只用正样本训练 chajia_click 辅助任务（Issue #4）

**关键经验**：

1. 加法融合远优于指数融合，线性关系更稳定可控
1. CTR/CVR 权重比是关键：原始 4:1 → v2 的 1.2:1 → v3 的 0.43:1
1. CVR 权重提升需谨慎，过度强调会牺牲 CTR
1. ODPS HASH 函数返回负数，必须用 `ABS(HASH())`

### BUG FIX: FX tracing 期间 Proxy 变量不可用于控制流 (2026-07-18)

- 每次在 `loss()` 或 `forward()` 中引入涉及 tensor 运算+控制流的代码时，第一时间考虑 FX tracing 兼容性
- 不要只 guard `torch.tensor()` 那一行——整个计算链都需要被保护
- `is_fx_tracing()` 检查应该包裹**整个**可能产生 Proxy 的代码块

<!-- codebase-memory-mcp:end -->
