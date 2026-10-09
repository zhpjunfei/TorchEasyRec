# 对抗性审核回应

## 关于 task_space_indicator_label 的修正

**用户质疑**：为什么要限制该场景的点击行为？这样会导致该场景没有点击负样本。

**回应**：你是对的，我之前的理解有误。

### 正确理解

从代码实现看（`multi_task_rank.py:136-140`）：

```python
if task_tower_cfg.HasField("task_space_indicator_label"):
    in_task_space = (
        batch.labels[task_tower_cfg.task_space_indicator_label] > 0
    ).float()
    loss_weight = loss_weight * (
        task_tower_cfg.in_task_space_weight * in_task_space
        + task_tower_cfg.out_task_space_weight * (1 - in_task_space)
    )
```

当 `in_task_space_weight=1, out_task_space_weight=0` 时：

- indicator > 0 的样本：正常计算 loss
- indicator = 0 的样本：loss_weight = 0，不参与学习

### v17 的实际用法

| 任务              | indicator             | 含义                       | 是否正确                         |
| ----------------- | --------------------- | -------------------------- | -------------------------------- |
| CTR 主任务        | `is_home_scene`       | 只在 home 场景学习         | ✓                                |
| CVR 主任务        | `is_home_scene_click` | 只在 home 且有点击时学习   | ✓（conversion 只能发生在点击后） |
| chajia_click 辅助 | `is_chajia_scene`     | 在 chajia 场景所有样本学习 | ✓                                |

### 修正后的配置

```protobuf
# 辅助任务使用场景标记（学习该场景所有样本）
task_space_indicator_label: "is_bijia_scene"    # 不是 is_bijia_scene_click
task_space_indicator_label: "is_haojia_scene"   # 不是 is_haojia_scene_click
task_space_indicator_label: "is_trend_scene"    # 不是 is_trend_scene_click
```

这样辅助任务会在对应场景的**所有样本**（包括正负样本）上学习，而不是只在学习有点击的样本。

______________________________________________________________________

## 关于 trend 正样本率 49.8%

**用户质疑**：从哪里得到的结论？如果需要真实的数据，把 SQL 给我。

**回应**：这个数据来自 `docs/label-table-v3-audit-20260901.md`，但那是 v3 label table 的数据，不是当前 v1 encoded 表的数据。

### 数据来源

```markdown
trend_pv  trend_click
173,462   86,xxx  → 49.8%
```

**问题**：

1. 这是 v3 label table 的审计数据（2026-09-01），可能不是最新
1. v1 encoded 表的结构和 v3 不同，需要重新查询

### 验证 SQL

已生成查询 SQL（`/tmp/query_scene_stats.sql`），请在 ODPS 执行：

```sql
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS total_pv,
    SUM(is_click) AS home_click,
    SUM(is_bijia_click) AS bijia_click,
    SUM(is_haojia_click) AS haojia_click,
    SUM(is_trend_click) AS trend_click,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS home_ctr_pct,
    ROUND(SUM(is_bijia_click) * 100.0 / COUNT(1), 2) AS bijia_ctr_pct,
    ROUND(SUM(is_haojia_click) * 100.0 / COUNT(1), 2) AS haojia_ctr_pct,
    ROUND(SUM(is_trend_click) * 100.0 / COUNT(1), 2) AS trend_ctr_pct
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261001'
GROUP BY ...;
```

**请执行上述 SQL，获取 v1 表的实际正样本率，再决定是否需要剔除 trend。**

______________________________________________________________________

## 修正后的配置结构

### label_fields (11个)

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
label_fields: "is_home_scene_click"  # CVR 主任务用
```

### task_towers (5个)

```protobuf
# CTR 主任务：在 home 场景学习
task_towers {
  tower_name: "ctr"
  label_name: "is_click"
  task_space_indicator_label: "is_home_scene"
}

# CVR 主任务：在 home 且有点击时学习
task_towers {
  tower_name: "cvr"
  label_name: "is_conversion"
  task_space_indicator_label: "is_home_scene_click"
}

# 辅助任务：在各自场景学习（包含正负样本）
task_towers {
  tower_name: "bijia_click"
  label_name: "is_bijia_click"
  task_space_indicator_label: "is_bijia_scene"  # ✓ 场景标记，不是点击派生
}

task_towers {
  tower_name: "haojia_click"
  label_name: "is_haojia_click"
  task_space_indicator_label: "is_haojia_scene"
}

task_towers {
  tower_name: "trend_click"
  label_name: "is_trend_click"
  task_space_indicator_label: "is_trend_scene"
}
```

______________________________________________________________________

## 下一步行动

1. **执行 SQL 验证各场景正样本率**
1. **根据实际数据决定是否需要剔除 trend**
1. **运行实验对比 v18 vs v19**
