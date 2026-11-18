# v5 Label 逻辑可行性评估

## 一、v5 相比 v3 的核心变化

| 变化点        | v3 逻辑                     | v5 逻辑                                         | 评估        |
| ------------- | --------------------------- | ----------------------------------------------- | ----------- |
| home 过滤条件 | `is_click >= is_conversion` | `is_exposure > 0 AND is_click >= is_conversion` | ✅ 更严谨   |
| bijia 过滤    | 全量保留                    | JOIN clicked_pair（只保留有点击的用户）         | ✅ 噪声过滤 |
| haojia 过滤   | 全量保留                    | JOIN clicked_pair（只保留有点击的用户）         | ✅ 噪声过滤 |
| trend 场景    | 无                          | 新增 trend 辅助任务                             | ⚠️ 需验证   |
| 序列特征      | click_50                    | click_cnt + click_num                           | ✅ 更丰富   |

## 二、可行性分析

### 2.1 is_exposure > 0 过滤（✅ 合理）

**作用**：只保留真正有曝光的样本，过滤掉日志丢失的"点击"样本

**预期影响**：

- 会移除少量只有 click/conversion 但没有 exposure 记录的样本
- 提升样本质量，避免噪声

**验证 SQL**：运行 `audit_v5_vs_v3.sql` 第 2 部分

### 2.2 clicked_pair 过滤（✅ 合理）

**作用**：bijia/haojia 只保留有点击行为的用户的样本

**理论依据**：

- 多场景建模的核心目标是学习"点击用户"的行为模式
- 无点击用户的行为序列缺乏参考价值
- 减少负样本噪声

**预期影响**：

- bijia：从 8.1M 样本中筛选出有点击的用户子集
- haojia：从 4.4M 样本中筛选出有点击的用户子集
- trend：同理

**验证 SQL**：运行 `audit_v5_decision.sql` 第 5 部分

### 2.3 trend 场景引入（⚠️ 需谨慎）

**数据现状**：

- trend PV: 24.0M（占比 23.5%）
- trend CTR: 52.0%（异常高）
- trend 序列特征：click_50 P50=1（失效）
- trend chajia_50 P50=19.5（有效）

**风险点**：

1. 高 CTR（52%）可能是场景特殊性导致，不代表推荐质量
1. 点击序列特征失效，无法学习行为序列
1. 但 chajia_50 序列有效，可以学习商品信息序列

**建议**：

- Phase 1 暂不引入 trend
- Phase 2 验证 bijia/haojia 后，再考虑 trend
- 如果引入，trend 权重应较低（0.3-0.5）

## 三、效果提升预估

### 3.1 预期收益

| 改进点            | 预期收益               | 实现难度 |
| ----------------- | ---------------------- | -------- |
| is_exposure 过滤  | 提升样本质量，减少噪声 | 低       |
| clicked_pair 过滤 | 提升辅助任务信号质量   | 低       |
| trend 引入        | 增加行为序列多样性     | 中       |
| chajia 序列利用   | 补充商品信息特征       | 中       |

### 3.2 风险评估

| 风险                         | 等级 | 缓解措施                   |
| ---------------------------- | ---- | -------------------------- |
| trend CTR 异常高导致模型偏移 | 中   | 降低 trend 权重（0.3-0.5） |
| 序列特征稀疏影响泛化         | 低   | bijia/haojia 序列充足      |
| 样本分布不均                 | 低   | 已通过权重调整             |

## 四、决策建议

### 方案 A：保守方案（推荐）

- Phase 1：bijia_click 辅助任务（weight=1.0）
- Phase 2：+ haojia_click 辅助任务（weight=0.3）
- **暂不引入 trend**，待序列特征验证后再决定

### 方案 B：激进方案

- Phase 1：bijia + haojia + trend（weight 分别为 1.0/0.3/0.5）
- 风险：trend 序列失效可能导致噪声

## 五、验证 Checklist

运行以下 SQL 并检查指标：

1. **`audit_v5_vs_v3.sql`**：

   - [ ] home 样本量变化 < 5%（is_exposure 过滤影响）
   - [ ] bijia/haojia 样本量减少 30-50%（clicked_pair 过滤）
   - [ ] 各场景曝光率 > 90%

1. **`audit_v5_sequence_quality.sql`**：

   - [ ] bijia click_50 平均长度 > 5
   - [ ] haojia click_50 平均长度 > 10
   - [ ] trend chajia_50 平均长度 > 10

1. **`audit_v5_decision.sql`**：

   - [ ] 各场景 CVR > 10%（转化信号充足）
   - [ ] 高频用户（click_num >= 100）占比 < 1%
