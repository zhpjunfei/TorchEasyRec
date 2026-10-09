# v19: 多场景融合建模实验

## 实验目标

将搜索默认着陆页(bijia)、搜索第二页(haojia)、查价页面(trend)的帖子日志纳入建模，
通过多场景行为信息综合建模，提升搜页推荐场景的 CTR 指标。

## 关键改动

### 1. 样本表 (v1 DDL)

- 文件: `../ddl/home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1.ddl`
- 已包含四场景标记: `is_home_scene`, `is_bijia_scene`, `is_haojia_scene`, `is_trend_scene`
- 已包含各场景行为标签: `is_bijia_click/conversion`, `is_haojia_click/conversion`, `is_trend_click/conversion`

### 2. 数据准备脚本

- 文件: `../sql/2606_sample/v4/home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1`
- 每日调度生成训练集，60天滑动窗口
- 去重策略: 按 (dt, mmb_id, item_id) 保留最新一条
- 新增派生字段: `is_home_scene_click`, `is_bijia_scene_click`, `is_haojia_scene_click`, `is_trend_scene_click`

### 3. 模型配置

- 文件: `home_flow_2608_v19_multiscene.config`
- label_fields: 9个 (原3个 + 新增6个)
  - 基础: `is_click`, `is_conversion`, `is_home_scene`
  - 场景标记: `is_bijia_scene`, `is_haojia_scene`, `is_trend_scene`
  - 场景点击: `is_bijia_click`, `is_haojia_click`, `is_trend_click`

### 4. 新增辅助任务

```protobuf
task_towers {
  tower_name: "bijia_click"      # 搜索默认着陆页点击预测
  label_name: "is_bijia_click"
  task_space_indicator_label: "is_bijia_scene"  # 仅在 bijia 场景学习

  grouped_auc { grouping_key: "is_bijia_scene" }  # 分组评估
}

task_towers {
  tower_name: "haojia_click"     # 搜索第二页点击预测
  label_name: "is_haojia_click"
  task_space_indicator_label: "is_haojia_scene"
  grouped_auc { grouping_key: "is_haojia_scene" }
}

task_towers {
  tower_name: "trend_click"      # 查价页面点击预测
  label_name: "is_trend_click"
  task_space_indicator_label: "is_trend_scene"
  grouped_auc { grouping_key: "is_trend_scene" }
}
```

### 5. 主任务保持不变

- CTR 任务: `is_click`, 分组评估 `is_home_scene`
- CVR 任务: `is_conversion`, 分组评估 `is_home_scene`

## 评估指标

| 指标               | 分组 key             |
| ------------------ | -------------------- |
| AUC (CTR)          | 整体 + is_home_scene |
| AUC (CVR)          | 整体 + is_home_scene |
| AUC (bijia_click)  | is_bijia_scene       |
| AUC (haojia_click) | is_haojia_scene      |
| AUC (trend_click)  | is_trend_scene       |

## 训练脚本

### 本地调试

```bash
bash /Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/config/v19/train_v19_multiscene.sh
```

### DLC 提交

```bash
bash /Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/sql/2606_sample/v4/train_v19_multiscene_dlc.sh
```

## 注意事项

1. **样本比例**: bijia/haojia/trend 场景样本量可能远小于 home_scene，建议监控各场景数据分布
1. **权重调整**: 当前辅助任务 weight=1.0，可根据实际效果调整
1. **task_space_indicator_label**: 确保各辅助任务只在对应场景学习，避免污染主任务
1. **与 v18 对比**: v18 是纯 home_scene 基线，v19 是多场景融合，建议并行训练对比

## 相关文件

- 基线配置: `../v18/home_flow_2604_v18_seq_ablation.config`
- v17 多场景经验: `../v17/home_flow_2604_v17_scene_mask.config`
- 样本审计: `../sql/2606_sample/v3/home_flow_2606_label_table_v3_audit.sql`
