# v19 多场景融合方案 - 对抗性审核报告

**审核日期**: 2026-10-02
**审核范围**: 数据质量、模型架构、评估方案、工程落地

______________________________________________________________________

## 执行摘要

| 类别         | 严重度 | 数量 | 状态               |
| ------------ | ------ | ---- | ------------------ |
| P0: 严重错误 | 🔴     | 2    | 已修复 1, 待修复 1 |
| P1: 重要问题 | 🟡     | 3    | 需决策             |
| P2: 建议改进 | 🟢     | 3    | 可选优化           |

**核心结论**: 方案方向正确，但存在关键实现错误（task_space_indicator_label 使用不当）和数据质量问题（trend 场景样本偏差），需立即修正后方可实验。

______________________________________________________________________

## 🔴 P0: 严重错误

### 1. task_space_indicator_label 使用错误 ✅ 已修复

**问题描述**:

- 原配置使用 `is_bijia_scene` 等原始场景标记作为 `task_space_indicator_label`
- 正确语义应为：该任务只在对应场景**且有点击**时才学习

**错误影响**:

- `is_bijia_scene=1` 对所有 bijia 样本都是 1，无法区分正负样本
- 导致辅助任务在 bijia 负样本上也会计算 loss，违背设计意图

**修复方案**:

```protobuf
# 修复前（错误）
task_space_indicator_label: "is_bijia_scene"

# 修复后（正确）
task_space_indicator_label: "is_bijia_scene_click"  # = is_bijia_scene AND is_bijia_click
```

**文件变更**:

- `config/v19/home_flow_2608_v19_multiscene.config`
  - 添加 4 个派生字段到 `label_fields`
  - 修正 3 个辅助任务的 `task_space_indicator_label`

______________________________________________________________________

### 2. 数据准备脚本缺少质量过滤 ⏳ 待修复

**问题描述**:
当前脚本 `sql/2606_sample/v4/home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1`:

```sql
WHERE _dedup_rn = 1
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)
```

**缺失过滤**:

1. **trend 时序泄漏**: 684 行 (0.39%) 存在未来曝光，应剔除
1. **无效 request_id**: 各场景 request_id=NULL 的样本应过滤
1. **极端异常值**: event_unix_time 异常的行应检查

**建议修复**:

```sql
WHERE _dedup_rn = 1
AND request_id IS NOT NULL
AND NOT (is_trend_scene = 1 AND event_unix_time < LAG(event_unix_time) OVER ...)  -- 时序泄漏检查
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)
```

______________________________________________________________________

## 🟡 P1: 重要问题

### 3. 样本量极端不均衡

| 场景   | PV        | 占比  | 正样本率 | vs home |
| ------ | --------- | ----- | -------- | ------- |
| home   | 1,160,816 | 66.7% | 3.0%     | 1.0x    |
| bijia  | 268,444   | 15.4% | 35.9%    | 0.2x    |
| haojia | 136,786   | 7.9%  | 13.1%    | 0.1x    |
| trend  | 173,462   | 10.0% | 49.8%    | 0.1x    |

**风险分析**:

1. **梯度尺度差异**: bijia 正样本率 35.9% vs home 3.0%，差值 12 倍
1. **辅助任务权重**: weight=1.0 可能过度优化小样本场景
1. **主任务干扰**: 大梯度可能导致 CTR/CVR 学习不稳定

**建议方案**:

- **方案 A**: 降低辅助任务 weight 至 0.1-0.3
- **方案 B**: 按场景分层采样，保证各场景 batch 比例均衡
- **方案 C**: 使用 focal loss 处理正负样本不均衡

______________________________________________________________________

### 4. trend 场景数据质量问题 ⚠️ 需决策

**问题**:

1. **时序泄漏**: 684 行 (0.39%) 存在未来曝光
1. **正样本率异常**: 49.8% vs home 3.0%，差值 16 倍
1. **样本代表性**: trend_exposure 依赖客户端发版，可能偏差

**根本原因**:

- `trend_click` 不依赖客户端上报（无需曝光即可点击）
- `trend_exposure` 依赖客户端发版，覆盖率不足
- 导致 click/exposure 比率失真

**决策建议**:

| 方案       | 优点         | 缺点           | 推荐度 |
| ---------- | ------------ | -------------- | ------ |
| 剔除 trend | 数据质量可靠 | 损失 10% 样本  | ⭐⭐⭐ |
| 保留但降权 | 利用全部数据 | 噪声可能干扰   | ⭐⭐   |
| 保留且平衡 | 数据充分利用 | 需复杂采样策略 | ⭐     |

**我的建议**: 先剔除 trend 跑 baseline，验证方法有效后再尝试加入。

______________________________________________________________________

### 5. INNER JOIN 过滤偏差

**数据**:

- bijia: src=407,591 → lbl=268,444 (过滤 34%)
- haojia: src=30,268 → lbl=136,786 (放大 4.5x)

**问题**:
两个场景采用相同 INNER JOIN 逻辑，但效果相反：

- bijia 过滤掉无点击 request → 高正样本率 35.9%
- haojia 保留同 request 下多个 item → 低正样本率 13.1%

**影响**:
场景间特征分布不一致，模型难以学习跨场景通用模式。

**建议**:
统一过滤标准，或为各场景创建独立的 expert。

______________________________________________________________________

## 🟢 P2: 建议改进

### 6. 缺少场景感知特征

**当前缺失**:

- 场景 ID embedding（让模型感知当前场景）
- 场景-specific 特征交互

**建议添加**:

```protobuf
feature_configs {
  id_feature {
    feature_name: "scene_id"
    expression: "user:scene_id"  # 从场景标记派生
    embedding_dim: 8
    hash_bucket_size: 10
  }
}
```

______________________________________________________________________

### 7. 评估指标不完整

**建议新增**:

1. 各场景 AUC 对比
1. 预测分布校准分析（probs_ctr mean/std per scene）
1. 交叉场景泛化测试（在 bijia 训练，在 home 测试）

______________________________________________________________________

### 8. 训练效率问题

**当前配置**:

- batch_size=4096，未考虑场景比例

**建议优化**:

- 按场景分层采样：home:bijia:haojia:trend = 6:1.5:0.8:1
- 或使用动态 batch，保证每 batch 场景比例稳定

______________________________________________________________________

## 修正后的配置

### label_fields (13个)

```protobuf
label_fields: "is_click"
label_fields: "is_conversion"
label_fields: "is_home_scene"
label_fields: "is_bijia_scene"
label_fields: "is_haojia_scene"
label_fields: "is_trend_scene"
label_fields: "is_bijia_click"
label_fields: "is_haojia_click"
label_fields: "is_trend_click"
label_fields: "is_home_scene_click"    # 新增
label_fields: "is_bijia_scene_click"   # 新增
label_fields: "is_haojia_scene_click"  # 新增
label_fields: "is_trend_scene_click"   # 新增
```

### task_towers (5个)

```protobuf
task_towers { tower_name: "ctr", ... }           # 主任务
task_towers { tower_name: "cvr", ... }           # 主任务
task_towers { tower_name: "bijia_click", ... }   # 辅助任务，task_space_indicator_label: "is_bijia_scene_click"
task_towers { tower_name: "haojia_click", ... }  # 辅助任务，task_space_indicator_label: "is_haojia_scene_click"
task_towers { tower_name: "trend_click", ... }   # 辅助任务，task_space_indicator_label: "is_trend_scene_click"
```

______________________________________________________________________

## 下一步行动

### 立即可做

1. ✅ 修复 task_space_indicator_label（已完成）
1. ⏳ 添加数据质量过滤到 SQL 脚本
1. ⏳ 决定是否剔除 trend 场景

### 实验验证

4. 先跑 bijia 辅助任务单独实验（最小增量）
1. 验证 CTR AUC 是否提升后再加其他场景
1. 对比实验：baseline(v18) vs multiscene(v19)

### 长期优化

7. 添加场景 ID 特征
1. 实现场景分层采样
1. 建立交叉场景泛化测试

______________________________________________________________________

## 相关文件

- 配置: `config/v19/home_flow_2608_v19_multiscene.config`
- 数据脚本: `sql/2606_sample/v4/home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1`
- 训练脚本: `config/v19/train_v19_multiscene.sh`
- 基线配置: `config/v18/home_flow_2604_v18_seq_ablation.config`
- 数据审计: `docs/label-table-v3-audit-20260901.md`
