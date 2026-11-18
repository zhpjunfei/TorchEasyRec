# P0 特征添加方案（修订版）

**日期**: 2026-10-17
**目标**: 添加高价值特征并验证多场景建模可行性

______________________________________________________________________

## 一、可行性重审

### 之前的错误认知

| 错误                           | 修正                                                           |
| ------------------------------ | -------------------------------------------------------------- |
| sample_weight 可实现特征级隔离 | sample_weight 是 task_tower 级别，控制 loss 权重，不是特征级别 |
| AFP 可强制场景特异性           | AFP 自动学习路由，不能强制隔离                                 |
| 需要扩展 proto 支持            | 现有机制已足够                                                 |

### 关键发现

当前配置已通过 `task_space_indicator_label` 实现"软隔离"：

```protobuf
task_towers {
  tower_name: "trend_click"
  label_name: "is_trend_click"
  task_space_indicator_label: "is_trend_scene"  # ← 关键！
}
```

**含义**：

- trend_click 辅助任务只在 `is_trend_scene=1` 的样本上计算 loss
- 梯度只在 trend 样本上反向传播
- 相当于"软隔离"：特征共享，但学习信号隔离

______________________________________________________________________

## 二、P0 特征添加清单

### A. 共享高价值特征（所有 tower 共用）

| 特征名                                    | 类型   | 价值说明                 |
| ----------------------------------------- | ------ | ------------------------ |
| offline_order_brand_common_ratio          | FLOAT  | 下单品牌偏好，强转化信号 |
| offline_order_first_cate_id_common_ratio  | FLOAT  | 下单一级类目偏好         |
| offline_order_second_cate_id_common_ratio | FLOAT  | 下单二级类目偏好         |
| consume_power                             | FLOAT  | 用户消费能力             |
| his_high_level                            | FLOAT  | 历史高等级标识           |
| gold_coin                                 | DOUBLE | 金币余额                 |
| convert_probability                       | DOUBLE | 商品转化率预测           |
| potential_score                           | DOUBLE | 商品潜力评分             |
| srh_hot                                   | BIGINT | 搜索热度                 |

### B. 场景特异性特征（依赖 AFP 隐式学习）

| 特征名                                          | 关联场景 | 说明                 |
| ----------------------------------------------- | -------- | -------------------- |
| offline_chajia_brand_common_ratio               | trend    | 查价品牌偏好         |
| offline_chajia_first_cate_id_common_ratio       | trend    | 查价一级类目偏好     |
| offline_chajia_second_cate_id_common_ratio      | trend    | 查价二级类目偏好     |
| offline_search_click_brand_common_ratio         | search   | 搜索点击品牌偏好     |
| offline_search_click_first_cate_id_common_ratio | search   | 搜索点击一级类目偏好 |

______________________________________________________________________

## 三、实施路径

### Phase 1: 基线实验（立即执行）

**目标**: 验证多场景辅助任务有效性

**步骤**:

1. 添加 9 个 P0 共享特征
1. 依赖现有 `task_space_indicator_label` 控制
1. 监控 AFP gate 输出
1. 评估 CTR/AUC 效果

**预期**:

- 特征数量: +9
- 训练时间: +5%
- CTR 提升: +0.3-0.5%

### Phase 2: AFP 效果评估

**目标**: 验证 AFP 是否自动学习场景特异性

**步骤**:

1. 检查 AFP gate 输出分布
1. 确认 chajia 特征是否路由到 trend expert
1. 对比启停 AFP 的效果差异

**决策**:

- 如果 AFP 效果好 → 继续 Phase 3
- 如果效果不佳 → 考虑启用 `afp_per_task_enabled`

### Phase 3: 优化迭代

**目标**: 根据效果调整特征组合

**选项**:

1. 启用 per-task AFP
1. 调整特征权重
1. 评估是否添加 FG 交叉特征

______________________________________________________________________

## 四、风险评估

| 风险             | 等级 | 缓解措施                          |
| ---------------- | ---- | --------------------------------- |
| 特征冗余         | 低   | 添加前做相关性分析                |
| 过拟合           | 中   | 增加 dropout，监控 validation AUC |
| 训练时间增长     | 低   | 分批添加，逐步评估                |
| AFP 隔离效果不佳 | 中   | Phase 2 验证，准备备选方案        |

______________________________________________________________________

## 五、关键监控指标

### 离线指标

- home 场景 CTR AUC
- home 场景 grouped_auc (is_home_scene)
- 各辅助任务 AUC
- AFP gate 熵值（评估隔离程度）

### 线上指标

- home 场景 CTR
- home 场景 CVR
- 整体收益

______________________________________________________________________

## 六、结论

**方案可行性**: ✅ 高

**理由**:

1. 现有机制（task_space_indicator_label）已实现"软隔离"
1. AFP 可自动学习特征路由
1. 不需要修改框架，风险低
1. 可快速验证，迭代成本低

**下一步**: 启动 Phase 1 实验
