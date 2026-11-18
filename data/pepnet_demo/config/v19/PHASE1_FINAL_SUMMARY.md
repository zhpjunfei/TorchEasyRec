# Phase 1 最终总结

**日期**: 2026-10-18
**状态**: 已准备就绪，待启动训练

______________________________________________________________________

## 一、配置文件总览

| 配置文件                                        | 特征数 | 说明                              |
| ----------------------------------------------- | ------ | --------------------------------- |
| `home_flow_2608_v19_multiscene.config`          | 996    | 原始配置（未修改）                |
| `home_flow_2608_v19_phase1_p0_v2.config`        | 1005   | **Phase 1 主配置（9个通用特征）** |
| `home_flow_2608_v19_phase1_chajia.config`       | 1001   | Chajia 场景实验（5个特征）        |
| `home_flow_2608_v19_phase1_search.config`       | 1001   | Search 场景实验（5个特征）        |
| `home_flow_2608_v19_phase1_bijia_only.config`   | 997    | Bijia only 基线                   |
| `home_flow_2608_v19_phase2_bijia_haojia.config` | 998    | Phase 2 配置                      |

______________________________________________________________________

## 二、P0 特征分类标准

### 筛选维度

1. **信息量**（Information Gain）：与目标变量相关性 > 0.05
1. **覆盖率**（Coverage）：非空比例 > 95%
1. **稳定性**（Stability）：跨时间分布稳定
1. **业务相关性**（Business Relevance）：与优化目标直接相关
1. **计算成本**（Computational Cost）：训练时间影响 < 10%

### 分类结果

| 类别           | 数量 | 添加策略        |
| -------------- | ---- | --------------- |
| 通用高价值特征 | 9    | ✅ 添加到公共组 |
| 场景特异性特征 | 10   | ⚠️ 单独实验     |
| 低价值特征     | 94   | ❌ 暂缓添加     |

______________________________________________________________________

## 三、Phase 1 配置详解

### 3.1 home_flow_2608_v19_phase1_p0_v2.config

**P0 通用特征（9个）**：

#### 转化信号（3个）

```
offline_order_brand_common_ratio
offline_order_first_cate_id_common_ratio
offline_order_second_cate_id_common_ratio
```

#### 直接预测（1个）

```
convert_probability
```

#### 用户质量（3个）

```
consume_power
his_high_level
gold_coin
```

#### 商品质量（2个）

```
potential_score
srh_hot
```

**启动命令**：

```bash
bash train_v19_multiscene.sh --config config/v19/home_flow_2608_v19_phase1_p0_v2.config
```

______________________________________________________________________

### 3.2 home_flow_2608_v19_phase1_chajia.config

**Chajia 场景特征（5个）**：

```
offline_chajia_brand_common_ratio
offline_chajia_first_cate_id_common_ratio
offline_chajia_second_cate_id_common_ratio
offline_chajia_site_common_ratio
offline_chajia_third_cate_id_common_ratio
```

**目的**：验证 chajia 特征对 trend 场景的迁移效果

**启动命令**：

```bash
bash train_v19_multiscene.sh --config config/v19/home_flow_2608_v19_phase1_chajia.config
```

______________________________________________________________________

### 3.3 home_flow_2608_v19_phase1_search.config

**Search Click 场景特征（5个）**：

```
offline_search_click_brand_common_ratio
offline_search_click_first_cate_id_common_ratio
offline_search_click_second_cate_id_common_ratio
offline_search_click_site_common_ratio
offline_search_click_third_cate_id_common_ratio
```

**目的**：验证 search 特征对 bijia/haojia 场景的迁移效果

**启动命令**：

```bash
bash train_v19_multiscene.sh --config config/v19/home_flow_2608_v19_phase1_search.config
```

______________________________________________________________________

## 四、实验设计

### 4.1 并行实验

| 实验组   | 配置                 | 目的                |
| -------- | -------------------- | ------------------- |
| 对照组   | multiscene.config    | 基线效果            |
| 实验组 A | phase1_p0_v2.config  | 通用特征效果        |
| 实验组 B | phase1_chajia.config | Chajia 场景特征效果 |
| 实验组 C | phase1_search.config | Search 场景特征效果 |

### 4.2 评估指标

**离线指标**：

- home CTR AUC（主要指标）
- home grouped_auc（is_home_scene）
- 各辅助任务 AUC
- AFP gate 熵值

**线上指标**：

- home CTR
- home CVR
- 整体收益

______________________________________________________________________

## 五、决策标准

### 5.1 通用特征（P0）

**达标标准**：

- home CTR AUC 提升 > 0.003
- 辅助任务 AUC > 0.53
- 训练时间增长 < 10%

**下一步**：

- 达标 → 上线，进入 Phase 2
- 不达标 → 分析原因，调整特征

### 5.2 场景特异性特征

**达标标准**：

- 对应场景 AUC 提升 > 0.005
- AFP gate 能正确路由（熵值 < 0.3）
- 不影响 home 场景效果

**下一步**：

- 达标 → 合并到主配置
- 不达标 → 放弃或调整

______________________________________________________________________

## 六、文档清单

| 文档                       | 说明           |
| -------------------------- | -------------- |
| `PHASE1_FINAL_SUMMARY.md`  | 本文档         |
| `PHASE1_EXECUTION.md`      | 执行方案       |
| `P0_FEATURE_CRITERIA.md`   | 分类标准       |
| `UNUSED_FEATURES_LIST.md`  | 未使用特征清单 |
| `V5_LABEL_AUDIT_REPORT.md` | 样本勘验报告   |

______________________________________________________________________

## 七、下一步行动

1. ✅ 创建 3 个实验配置
1. 🔄 启动并行实验
1. 🔄 监控指标
1. 🔄 评估效果
1. 🔄 决策是否合并特征
