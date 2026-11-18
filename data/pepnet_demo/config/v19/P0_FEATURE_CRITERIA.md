# P0 特征分类标准与筛选依据

**日期**: 2026-10-17
**目标**: 建立科学的特征分类标准，避免盲目添加

______________________________________________________________________

## 一、特征分类维度

### 1.1 信息量（Information Gain）

- 特征对目标变量的预测能力
- 与现有特征的相关性（避免冗余）
- 评估方法：IV值、信息增益、相关性分析

### 1.2 覆盖率（Coverage）

- 非空比例
- 缺失率高的特征可能不稳定
- 阈值：覆盖率 > 90% 优先添加

### 1.3 稳定性（Stability）

- 跨时间分布是否稳定
- 是否有极端值
- 评估方法：PSI（Population Stability Index）

### 1.4 业务相关性（Business Relevance）

- 是否与优化目标直接相关
- 是否可解释
- 优先级：转化信号 > 点击信号 > 曝光信号

### 1.5 计算成本（Computational Cost）

- 特征维度
- 训练时间影响
- 内存占用

______________________________________________________________________

## 二、P0 特征筛选标准

### 必须满足（缺一不可）

1. ✅ 覆盖率 > 95%
1. ✅ 与目标变量相关性 > 0.05
1. ✅ 与现有特征相关性 < 0.8（避免冗余）
1. ✅ 业务可解释

### 优先满足

1. 📌 转化相关信号（order, convert_probability）
1. 📌 用户质量信号（consume_power, gold_coin）
1. 📌 商品质量信号（potential_score, srh_hot）

### 暂缓添加

1. ⚠️ 场景特异性特征（需单独验证）
1. ⚠️ FG交叉特征（需做相关性分析）
1. ⚠️ 低覆盖率特征（< 80%）

______________________________________________________________________

## 三、P0 特征清单（重新评估）

### 必添加（高价值通用特征）

| 特征名                                    | 类型   | 信息量 | 覆盖率 | 稳定性 | 理由         |
| ----------------------------------------- | ------ | ------ | ------ | ------ | ------------ |
| offline_order_brand_common_ratio          | FLOAT  | 高     | 99%    | 高     | 转化信号     |
| offline_order_first_cate_id_common_ratio  | FLOAT  | 高     | 99%    | 高     | 转化信号     |
| offline_order_second_cate_id_common_ratio | FLOAT  | 高     | 99%    | 高     | 转化信号     |
| convert_probability                       | DOUBLE | 高     | 99%    | 高     | 直接预测转化 |
| consume_power                             | FLOAT  | 中     | 95%    | 高     | 用户质量     |
| his_high_level                            | FLOAT  | 中     | 95%    | 高     | 用户质量     |
| gold_coin                                 | DOUBLE | 中     | 95%    | 高     | 用户质量     |
| potential_score                           | DOUBLE | 中     | 90%    | 中     | 商品质量     |
| srh_hot                                   | BIGINT | 中     | 90%    | 中     | 商品质量     |

**小计**: 9 个特征

### 待验证（场景特异性特征）

| 特征名                                           | 关联场景 | 信息量 | 覆盖率 | 风险 | 建议     |
| ------------------------------------------------ | -------- | ------ | ------ | ---- | -------- |
| offline_chajia_brand_common_ratio                | trend    | 高     | 99%    | 中   | 单独实验 |
| offline_chajia_first_cate_id_common_ratio        | trend    | 高     | 99%    | 中   | 单独实验 |
| offline_chajia_second_cate_id_common_ratio       | trend    | 高     | 99%    | 中   | 单独实验 |
| offline_search_click_brand_common_ratio          | search   | 中     | 99%    | 中   | 单独实验 |
| offline_search_click_first_cate_id_common_ratio  | search   | 中     | 99%    | 中   | 单独实验 |
| offline_search_click_second_cate_id_common_ratio | search   | 中     | 99%    | 中   | 单独实验 |

**小计**: 6 个特征（暂缓）

### 暂缓添加（低优先级）

| 特征类                         | 数量  | 理由         |
| ------------------------------ | ----- | ------------ |
| offline_like\_\*\_common_ratio | 5个   | 收藏信号弱   |
| FG交叉特征                     | 22个  | 需相关性分析 |
| 数组特征                       | 9个   | 需解析处理   |
| 其他标量                       | 50+个 | 信息量低     |

______________________________________________________________________

## 四、是否应该添加到公共特征？

### 分析

| 特征类型       | 添加到公共特征 | 单独实验 | 理由         |
| -------------- | -------------- | -------- | ------------ |
| 通用高价值特征 | ✅             | -        | 所有场景受益 |
| 场景特异性特征 | -              | ✅       | 避免噪声     |
| 待验证特征     | -              | ✅       | 风险控制     |

### 结论

**不要盲目全部添加到公共特征！**

正确做法：

1. Phase 1: 只添加 9 个通用高价值特征
1. Phase 2: 单独验证场景特异性特征效果
1. Phase 3: 根据实验结果决定是否加入公共组

______________________________________________________________________

## 五、实施建议

### 修正后的 Phase 1

**只添加 9 个特征**：

```
offline_order_brand_common_ratio
offline_order_first_cate_id_common_ratio
offline_order_second_cate_id_common_ratio
convert_probability
consume_power
his_high_level
gold_coin
potential_score
srh_hot
```

**暂缓添加**：

```
offline_chajia_*_common_ratio (3个)
offline_search_click_*_common_ratio (3个)
```

### 创建单独实验配置

```
home_flow_2608_v19_phase1_generic.config    # 9个通用特征
home_flow_2608_v19_phase1_chajia.config     # 仅 chajia 特征
home_flow_2608_v19_phase1_search.config     # 仅 search 特征
```

______________________________________________________________________

## 六、评估指标

### 离线评估

- AUC 提升
- GAUC 提升
- 特征重要性排序
- AFP gate 输出分布

### 线上评估

- CTR
- CVR
- 收益

______________________________________________________________________

## 七、总结

1. **P0 分类应基于科学标准**，不是主观划分
1. **不要盲目添加特征**，尤其是场景特异性特征
1. **分阶段验证**，控制风险
1. **数据驱动决策**，根据实验结果调整
