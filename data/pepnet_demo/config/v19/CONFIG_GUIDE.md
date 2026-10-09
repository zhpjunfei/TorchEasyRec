# v19 多场景融合实验配置指南

## 配置文件说明

| 配置文件                                        | 辅助任务                  | 权重          | 用途                          |
| ----------------------------------------------- | ------------------------- | ------------- | ----------------------------- |
| `home_flow_2608_v19_phase1_bijia_only.config`   | bijia_click               | 1.0           | **Phase 1: 验证方法有效性**   |
| `home_flow_2608_v19_phase2_bijia_haojia.config` | bijia_click, haojia_click | 1.0, 0.3      | **Phase 2: 验证 haojia 效果** |
| `home_flow_2608_v19_phase3_full.config`         | bijia, haojia, trend      | 1.0, 0.3, 0.5 | **Phase 3: 全场景融合**       |
| `home_flow_2608_v19_multiscene.config`          | bijia, haojia, trend      | 1.0, 0.3, 0.5 | 原始完整配置（已弃用）        |

## 实验顺序（推荐）

### Phase 1: 基础验证（必须）

```bash
# 配置: home_flow_2608_v19_phase1_bijia_only.config
# 目标: 验证多场景融合方法是否有效
# 评估: Grouped AUC (is_home_scene) 是否提升
```

**判断标准：**

- 如果 CTR AUC 下降 → 放弃多场景融合方案
- 如果 CTR AUC 持平或提升 → 进入 Phase 2

### Phase 2: 扩展验证（可选）

```bash
# 配置: home_flow_2608_v19_phase2_bijia_haojia.config
# 目标: 验证 haojia 辅助任务的贡献
# 评估: 对比 Phase 1，看 haojia 是否带来额外提升
```

**判断标准：**

- 如果 AUC 进一步提升 → 保留 haojia
- 如果 AUC 下降 → 剔除 haojia，直接到 Phase 3

### Phase 3: 全场景融合（可选）

```bash
# 配置: home_flow_2608_v19_phase3_full.config
# 目标: 验证 trend 辅助任务的贡献
# 评估: 对比 Phase 2，看 trend 是否带来额外提升
```

**判断标准：**

- 如果 AUC 进一步提升 → 全场景融合方案可行
- 如果 AUC 下降 → 剔除 trend，使用 Phase 2 配置

## 权重说明

| 辅助任务     | 权重 | 调整理由                             |
| ------------ | ---- | ------------------------------------ |
| bijia_click  | 1.0  | 正负比均衡（1:1.7），序列特征可用    |
| haojia_click | 0.3  | 正样本少（56万），降低权重避免过拟合 |
| trend_click  | 0.5  | 序列失效，降权但保留                 |

## 评估指标

### 主指标

- **Grouped AUC (is_home_scene)**：核心评估指标

### 辅助指标

- **AUC (bijia_click)**：验证 bijia 辅助任务效果
- **AUC (haojia_click)**：验证 haojia 辅助任务效果
- **AUC (trend_click)**：验证 trend 辅助任务效果
- **预测分布校准**：各场景 probs_ctr mean/std

## 预期结果

| 阶段                | 预期变化             | 理由                       |
| ------------------- | -------------------- | -------------------------- |
| Phase 1 vs Baseline | CTR AUC +0.001~0.005 | bijia 与 home 用户行为相似 |
| Phase 2 vs Phase 1  | CTR AUC +0.000~0.002 | haojia 样本量少，贡献有限  |
| Phase 3 vs Phase 2  | CTR AUC ±0.001       | trend 序列失效，效果不确定 |

## 相关文件

- 数据验证：`DATA_VALIDATION_COMPLETE.md`
- 专家分析：`EXPERT_ANALYSIS.md`
- 序列分析：`SEQUENCE_ANALYSIS_REVISED.md`
- 审核 SQL：`AUDIT_SQL.md`
