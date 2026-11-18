# CVR校准问题分析

**日期**: 2026-10-21
**问题类型**: 模型校准偏差
**状态**: ⚠️ 需要关注

______________________________________________________________________

## 一、问题现象

### 1.1 CVR预测 vs 实际分布

| 指标              | 修复前 | 修复后 | 实际CVR | 校准误差   |
| ----------------- | ------ | ------ | ------- | ---------- |
| **pred_cvr mean** | 0.3148 | 0.3095 | 0.1210  | **+19.0%** |
| **pred_cvr std**  | 0.2151 | 0.2176 | -       | -          |
| is_conversion     | 0.0813 | 0.0815 | -       | -          |
| is_home_scene     | 0.6660 | 0.6821 | -       | -          |

**关键发现**：

- CVR预测均值约0.31，但实际转化率仅0.12
- 校准误差+19%，远超健康范围（±2%）
- 修复前后几乎无变化，说明**这不是标签泄漏问题**

______________________________________________________________________

## 二、原因分析

### 2.1 CTCVR损失机制

```python
# multi_task_rank.py:186-196
# CTCVR loss = BCE(ctr_logits * cvr_logits, ctr_label * cvr_label)
# 只有ctr和cvr同时为正时才有监督信号
```

**影响**：

- CTCVR只在`is_click=1 AND is_conversion=1`的样本上提供梯度
- 这类样本占比：`0.2371 * 0.1193 ≈ 2.8%`（非常稀疏）
- 大部分样本（未点击或只点击不转化）对CVR tower无直接监督

### 2.2 CVR tower孤立训练

```protobuf
# cvr tower配置
tower_name: "cvr"
label_name: "is_conversion"
weight: 1.0
# 没有辅助任务提供额外监督
```

**问题**：

- CVR tower只依赖主任务的BCE loss
- 正样本率仅11.93%（home场景）
- 模型可能学到"保守预测"策略（预测偏高以覆盖正样本）

### 2.3 与CTR校准对比

| 任务 | pred_mean | actual | calibration_error | 状态    |
| ---- | --------- | ------ | ----------------- | ------- |
| CTR  | 0.3618    | 0.3720 | -1.02%            | ✅ 正常 |
| CVR  | 0.3095    | 0.1195 | +19.00%           | ❌ 异常 |

**差异原因**：

- CTR正样本率高（37%），模型容易学习
- CVR正样本率低（12%），且CTCVR路径进一步稀疏化

______________________________________________________________________

## 三、解决方案

### 方案A：调整CVR损失权重（快速验证）

```protobuf
task_towers {
  tower_name: "cvr"
  label_name: "is_conversion"
  weight: 2.0  # 提高权重，强化监督信号
  ...
}
```

**预期效果**：提高CVR tower的学习速率，可能改善校准

### 方案B：添加CVR辅助任务（推荐）

```protobuf
# 利用多场景CVR信号
tower_name: "bijia_cvr"
label_name: "is_bijia_conversion"
task_space_indicator_label: "is_bijia_scene"
weight: 0.5

tower_name: "haojia_cvr"
label_name: "is_haojia_conversion"
task_space_indicator_label: "is_haojia_scene"
weight: 0.3

tower_name: "trend_cvr"
label_name: "is_trend_conversion"
task_space_indicator_label: "is_trend_scene"
weight: 0.5
```

**数据基础**（来自SQL5验证）：

- bijia_conversion: 2.66M (13.58%)
- trend_conversion: 1.97M (17.23%)
- haojia_conversion: 0.47M (5.24%)
- **总计**: ~5.1M额外正样本

**预期效果**：

- 增加CVR监督信号密度
- 多场景特征迁移，提升home CVR泛化能力
- 改善校准偏差

### 方案C：Focal Loss（复杂度高）

```protobuf
losses {
  focal_loss {
    alpha: 0.25
    gamma: 2.0
  }
}
```

**适用场景**：正负样本极度不均衡时

______________________________________________________________________

## 四、建议行动

### 短期（立即）

1. **保持当前修复**：CTR修复有效，GAUC有微升
1. **记录CVR基准**：当前cvr AUC=0.763, GAUC=0.739, calibration_error=+19%

### 中期（下一步实验）

**实验1：提高CVR权重**

```bash
# 修改config: cvr weight 1.0 → 2.0
bash data/pepnet_demo/config/v19/train_v19_multiscene.sh \
  home_flow_2608_v19_multiscene_v2_fix_label_leak.config \
  20261019
```

**实验2：添加CVR辅助任务**

- 创建新config：`home_flow_2608_v19_multiscene_v3_add_cvr_aux.config`
- 添加bijia_cvr, haojia_cvr, trend_cvr三个辅助塔
- 对比校准误差是否改善

### 长期（如果校准仍不改善）

1. **检查CVR特征质量**：是否有强预测因子未使用
1. **调整CVR tower结构**：加深MLP或增加正则化
1. **考虑独立训练CVR**：先用home样本预训练CVR tower

______________________________________________________________________

## 五、判断标准

| 指标              | 当前值 | 目标值 | 状态      |
| ----------------- | ------ | ------ | --------- |
| CVR AUC           | 0.763  | >0.75  | ✅ 达标   |
| CVR GAUC          | 0.739  | >0.74  | ⚠️ 接近   |
| calibration_error | +19%   | \<±5%  | ❌ 需改善 |
| pred_cvr mean     | 0.31   | ~0.12  | ❌ 偏差大 |

**决策点**：

- 如果AUC/GAUC达标但校准差 → 可接受（排序任务不依赖校准）
- 如果线上CVR指标受影响 → 必须修复校准

______________________________________________________________________

## 六、结论

1. **CVR校准问题独立于标签泄漏**：修复前后无变化
1. **根本原因**：CTCVR路径导致CVR监督信号稀疏
1. **建议方案**：添加多场景CVR辅助任务
1. **优先级**：低于CTR GAUC优化（当前CVR不是主优化目标）

______________________________________________________________________

**分析完成时间**: 2026-10-21 10:15
**下一步**: 决定是否需要立即修复CVR校准，还是先完成CTR优化再处理
