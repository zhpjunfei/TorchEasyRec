# Agent 错误记录

## 错误 1：fixedlr config 引入额外变量

### 触发时间

2026-05-31

### 上下文

- 分析出 pepnet.config 的根因是 `cosine T_max=6300` 导致 LR=0.00014，CVR 梯度冻结
- 线上 nofreqpage 实验已证明 f_req_page 无贡献（-3% 依然存在）

### 错误行为

创建 `pepnet_fixedlr.config` 时，用了 `pepnet_nofreqpage.config`（无 f_req_page）作为 base。

### 根因

将两个独立分析的结论混为一个操作：

1. 分析 A：f_req_page 不是线上 -3% 的原因 → 结论：可以去掉
1. 分析 B：cosine LR 导致 CVR 不收敛 → 修复：改 optimizer

创建 config 时，把结论 A 的执行（去掉 f_req_page）与结论 B 的修复（改 optimizer）合并到了同一个 config 中。**一次改了两个变量**。

### 为什么出错

表象是「反正 f_req_page 无用，顺手一起改了」，本质是违反了**最小变更原则**：

- fixedlr 的预期行为：只修 optimizer，验证 LR 假设
- 多改了 f_req_page → 如果结果变好/变坏，无法区分是 optimizer 还是 f_req_page 的贡献

### 正确做法

从 `pepnet.config` 复制（保留 f_req_page），只改 optimizer。

### 预防

创建 config 时，先问：「这次实验要证/否什么假设？只改最小集。」

## 错误 2：constant_lr 结论 confounded

### 触发时间

2026-06-01

### 上下文

- 实验汇总记录了 "pepnet.config (cosine+wd=0.01, CVR 0.74162) vs constant_lr (无 wd, CVR 0.76970)"
- 以此得出 "CVR gap 是 LR 问题" 的结论

### 错误行为

将上述对比结论直接作为"根因反转"写入文档，且认为 `pepnet_fixedlr.config` 能复现 0.76970。

### 根因

1. **Confounded 对比**：两个实验同时改了 LR（cosine→constant）和 weight_decay（0.01→0），无法区分谁起作用
1. **版本不一致**：local pepnet.config（无 part_optimizers）≠ cluster 版本（有 part_optimizers）。0.74162 来自 cluster 版本，0.730 来自 local 版本
1. **验证缺失**：没有先在 local baseline 上运行确认两个版本的 baseline 是否一致，就直接得出结论

### 为什么出错

| 事实                                | 推理（错误）               | 实际                                            |
| ----------------------------------- | -------------------------- | ----------------------------------------------- |
| pepnet.config (cosine+wd) → 0.74162 | constant_lr 修复了 CVR     | pepnet.config (cosine, 无 wd) → **0.742**       |
| constant_lr (无 wd) → 0.76970       | 去掉 weight_decay 只是附带 | pepnet_fixedlr (constant, 无 wd) → **0.730** ❌ |

实际正确的对比（同版本、单变量）：

```
local pepnet.config (cosine, 无 wd): CVR 0.742
local pepnet_fixedlr (constant, 无 wd): CVR 0.730
→ constant_lr 在当前配置下反而更差
```

### 正确做法

1. 始终用 local config 作为 verified baseline
1. 只改一个变量：cosine→constant（保留 weight_decay 不变）
1. 如果在 cluster 上做实验，确认 local config 与 cluster config 一致

### 预防

- 任何对比实验必须跑在**同版本的 base config**上
- 跨版本对比时先跑 baseline 确认两边的 baseline AUC 一致
- 单变量原则：一个实验只改一个变量
