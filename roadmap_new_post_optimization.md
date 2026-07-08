# 新帖子冷启精排优化 Roadmap

## 问题

PiRec 精排相比旧精排，新帖子分发量少约 30%（粗召同一套）。
重排阶段已对新帖子加权，但分发量缺口仍存在 → **根因在精排模型对 new item 打分偏低**。

## Phase 1：线上调分 ✅ 已完成

重排阶段已通过新帖子提权实现。

## Phase 2：SQL up-sample（执行中）

### 核心思路

训练集新帖子样本复制翻倍，梯度贡献 ~2×，让模型学到更稳健的新帖子表示。

### 改动

shuffled SQL 将新帖子行翻倍：

```sql
SELECT * FROM base WHERE isNewItem = 0
UNION ALL
SELECT * FROM base WHERE isNewItem = 1
UNION ALL
SELECT * FROM base WHERE isNewItem = 1   -- 翻倍
```

### 效果预估

- 新帖子训练占比：~17% → ~29%
- 精排模型对 new item 打分偏差可能收敛
- 新帖子 UV 提升预期：+5~10%

### 风险

- 训练集变大 ~16%，训练时间略增
- 新帖子重复采样 → 可能过拟合，AB 观察

### 依赖

- [x] isNewItem SQL 列已存在（`home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3.sql`）
- [ ] SQL 列类型已改为 STRING（适配 FG handler）
- [ ] 下一轮训练数据窗口

## Phase 3：可选——根因诊断（优先级低）

精排模型对 new item 打分偏低的具体原因调查：

- 特征分布差异（lookup_feature 对 new item 的输出值）
- serving vs 训练的 feature computation 一致性
- PEPNet 的 expert 路由是否偏老帖子

## 时间线

```
当前：  Phase 2 SQL 修改 → 数据产出 → 训练
下一轮：训练完成 → 线上 AB 验证 Phase 2 效果
根据 Phase 2 结果决定是否需要 Phase 3
```
