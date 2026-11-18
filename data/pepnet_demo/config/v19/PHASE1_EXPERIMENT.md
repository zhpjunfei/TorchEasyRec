# Phase 1 多场景建模实验说明

**实验日期**: 2026-10-16
**配置文件**: `home_flow_2608_v19_multiscene.config`
**样本表**: `home_flow_2606_ctrcvr_sorter_label_table_v5` (dt='20261013')

______________________________________________________________________

## 一、实验目标

通过引入 bijia/haojia/trend 场景的点击辅助任务，学习跨场景用户行为模式，提升 home 场景 CTR。

______________________________________________________________________

## 二、任务配置

### 主任务

```protobuf
task_towers {
  tower_name: "ctr"
  label_name: "is_click"
  weight: 4.5
  # 监测指标: AUC, grouped_auc(is_home_scene)
}

task_towers {
  tower_name: "cvr"
  label_name: "is_conversion"
  weight: 1.0
  task_space_indicator_label: "is_click"
  # 监测指标: AUC, grouped_auc(is_home_scene)
}
```

### 辅助任务

```protobuf
# bijia辅助任务 (weight=1.0)
task_towers {
  tower_name: "bijia_click"
  label_name: "is_bijia_click"
  weight: 1.0
  task_space_indicator_label: "is_bijia_scene"
  # 监测指标: AUC, grouped_auc(is_bijia_scene)
}

# haojia辅助任务 (weight=0.3)
task_towers {
  tower_name: "haojia_click"
  label_name: "is_haojia_click"
  weight: 0.3
  task_space_indicator_label: "is_haojia_scene"
  # 监测指标: AUC, grouped_auc(is_haojia_scene)
}

# trend辅助任务 (weight=0.5)
task_towers {
  tower_name: "trend_click"
  label_name: "is_trend_click"
  weight: 0.5
  task_space_indicator_label: "is_trend_scene"
  # 监测指标: AUC, grouped_auc(is_trend_scene)
}
```

______________________________________________________________________

## 三、样本分布

| 场景   | PV        | 占比   | CTR    | CVR(点击后) |
| ------ | --------- | ------ | ------ | ----------- |
| home   | 1,825,006 | 66.52% | 37.00% | 35.50%      |
| bijia  | 443,356   | 16.16% | 37.95% | 36.79%      |
| haojia | 182,961   | 6.67%  | 13.68% | 35.31%      |
| trend  | 292,210   | 10.65% | 49.29% | 30.84%      |

**总样本量**: 2,743,533

______________________________________________________________________

## 四、特征覆盖情况

| 特征类型       | home | bijia | haojia | trend |
| -------------- | ---- | ----- | ------ | ----- |
| 序列特征(sq56) | 100% | 100%  | 100%   | 100%  |
| 用户基础(sq33) | 100% | 100%  | 100%   | 100%  |
| item_basic     | 100% | 100%  | 100%   | 100%  |
| cate_path      | 100% | 99.8% | 99.8%  | 99.7% |
| brand          | 100% | 99.4% | 99.4%  | 98.0% |
| item_rt(sq30)  | 100% | 33%   | 64%    | 0%    |

**核心结论**: 序列特征和商品静态特征完全可用，item_rt缺失影响有限。

______________________________________________________________________

## 五、预期效果

1. **多场景行为迁移**: 通过序列特征学习跨场景用户兴趣
1. **高质量信号引入**: trend点击用户home CVR高+7.55pp
1. **特征完整性**: 核心特征100%可用

______________________________________________________________________

## 六、评估指标

### 离线指标

- home场景 CTR AUC
- home场景 grouped_auc (is_home_scene)
- 各辅助任务 AUC

### 在线指标

- home场景 CTR
- home场景 CVR
- 整体收益

______________________________________________________________________

## 七、风险缓解

| 风险          | 措施                               |
| ------------- | ---------------------------------- |
| item_rt缺失   | 使用默认值填充，不影响训练         |
| 样本不均衡    | 已通过weight调整                   |
| trend序列失效 | 已有chajia_50序列作为补充          |
| 噪声引入      | 通过task_space_indicator_label控制 |

______________________________________________________________________

## 八、后续计划

1. **Phase 1**: 运行当前配置，评估效果
1. **Phase 2**: 根据结果调整weight或增减辅助任务
1. **Phase 3**: 考虑添加CVR辅助任务（需验证转化样本量）

______________________________________________________________________

## 九、相关文件

- 配置文件: `config/v19/home_flow_2608_v19_multiscene.config`
- 样本逻辑: `sql/2609/home_flow_2606_ctrcvr_sorter_label_table_v5`
- 特征关联: `sql/2609/home_flow_2608_ctrcvr_sorter_fix_sample_v5.sql`
- 勘验报告: `sql/2609/V5_LABEL_AUDIT_REPORT.md`
