# Phase 1 执行方案（修正版）

**更新日期**: 2026-10-17
**配置文件**: home_flow_2608_v19_phase1_p0_v2.config
**样本表**: home_flow_2606_ctrcvr_sorter_label_table_v5 (dt='20261013')

______________________________________________________________________

## 一、P0 分类标准（科学依据）

### 筛选维度

1. **信息量**: 特征对目标变量的预测能力
1. **覆盖率**: 非空比例（> 95%）
1. **稳定性**: 跨时间分布稳定性
1. **业务相关性**: 与优化目标的相关性
1. **计算成本**: 特征维度和训练时间影响

### P0 标准（必须满足）

- ✅ 覆盖率 > 95%
- ✅ 与目标变量相关性 > 0.05
- ✅ 与现有特征相关性 < 0.8
- ✅ 业务可解释

______________________________________________________________________

## 二、P0 特征清单（9个）

### 转化信号（3个）

```
offline_order_brand_common_ratio
offline_order_first_cate_id_common_ratio
offline_order_second_cate_id_common_ratio
```

### 直接预测（1个）

```
convert_probability
```

### 用户质量（3个）

```
consume_power
his_high_level
gold_coin
```

### 商品质量（2个）

```
potential_score
srh_hot
```

______________________________________________________________________

## 三、暂缓添加的特征

### 场景特异性特征（6个）

```
offline_chajia_brand_common_ratio
offline_chajia_first_cate_id_common_ratio
offline_chajia_second_cate_id_common_ratio
offline_search_click_brand_common_ratio
offline_search_click_first_cate_id_common_ratio
offline_search_click_second_cate_id_common_ratio
```

**理由**: 这些特征只在特定场景有意义，添加到公共特征会引入噪声。

**建议**: 创建单独实验配置验证效果。

______________________________________________________________________

## 四、配置文件说明

| 文件                                      | 说明                            |
| ----------------------------------------- | ------------------------------- |
| `home_flow_2608_v19_multiscene.config`    | 原始配置                        |
| `home_flow_2608_v19_phase1_p0_v2.config`  | **Phase 1 配置（9个通用特征）** |
| `home_flow_2608_v19_phase1_chajia.config` | 待创建（仅 chajia 特征）        |
| `home_flow_2608_v19_phase1_search.config` | 待创建（仅 search 特征）        |

______________________________________________________________________

## 五、实施步骤

### Step 1: 启动 Phase 1 训练

```bash
bash train_v19_multiscene.sh --config config/v19/home_flow_2608_v19_phase1_p0_v2.config
```

### Step 2: 监控指标

- home CTR AUC
- 各辅助任务 AUC
- AFP gate 输出

### Step 3: 创建场景特异性实验（Phase 1 后）

- 创建 `phase1_chajia.config`
- 只添加 offline_chajia\_\*\_common_ratio
- 对比效果

______________________________________________________________________

## 六、关键决策

### 是否全部添加到公共特征？

**答案：否！**

理由：

1. 场景特异性特征会引入噪声
1. 非相关场景的样本会学到无用特征
1. 应该分阶段验证

### 正确做法

1. Phase 1: 只添加通用高价值特征（9个）
1. Phase 2: 单独验证场景特征
1. Phase 3: 根据 AFP 输出决定最终方案

______________________________________________________________________

## 七、下一步行动

1. ✅ 创建修正版配置 home_flow_2608_v19_phase1_p0_v2.config
1. 🔄 启动 Phase 1 训练
1. 🔄 监控 AFP gate 输出
1. 🔄 创建场景特异性实验配置
