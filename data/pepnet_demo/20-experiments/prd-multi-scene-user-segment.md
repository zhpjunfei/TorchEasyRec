# PRD：精排模型多场景分群优化

> 状态：ready-for-agent
> 创建时间：2026-08-06
> 关联实验：第零阶段 v1/v2/v3、第一阶段 v18、第二阶段 v19

______________________________________________________________________

## Problem Statement

当前精排模型存在三个核心问题：

1. **融合公式偏差**：线上公式 `score = ctr × (1 + cvr)` 导致 CTR 过度优化（CTR 边际贡献是 CVR 的 4~5 倍），所有用户群体都出现 CTR↑ CVR↓ 的矛盾信号。

1. **用户分群缺失**：新用户、沉默用户、老用户使用同一套样本和特征，但三者的行为模式差异巨大（老用户 UVCTR 是沉默用户的 4.2 倍，UVCVR 是 5.8 倍）。

1. **场景标签污染**：推荐、搜索、比价三个场景的样本合并训练，但搜索和比价样本的 `is_click` 硬编码为 0，导致 CTR/CVR 模型学到错误的负样本信号。比价样本只有正样本（`is_chajia_click=1`），缺乏负样本。

## Solution

分三个阶段逐步优化：

1. **第零阶段**：修改融合公式，消除 CTR 过度优化的系统性偏差
1. **第一阶段**：分群特征工程 + loss 权重调整，让不同用户群体有专属特征表达
1. **第二阶段**：场景 mask + 辅助任务，利用 `task_space_indicator_label` 实现场景级别的梯度隔离

## User Stories

1. 作为推荐系统工程师，我希望融合公式对 CTR 和 CVR 的敏感度是可预测的，以便精确控制排序目标
1. 作为推荐系统工程师，我希望不同用户群体（新用户/沉默用户/老用户）有不同的融合参数，以便针对性优化
1. 作为推荐系统工程师，我希望模型能显式感知用户类型，以便学习不同用户群体的排序模式
1. 作为推荐系统工程师，我希望 CTR 任务只在推荐场景样本上训练，避免搜索/比价样本的标签污染
1. 作为推荐系统工程师，我希望 CVR 任务只在推荐场景样本上训练，避免搜索/比价样本的标签污染
1. 作为推荐系统工程师，我希望比价任务有合理的正负样本（从 chajia_sample 中负采样），以便学到泛化能力
1. 作为推荐系统工程师，我希望搜索任务作为辅助网络，通过共享表征间接提升推荐效果
1. 作为推荐系统工程师，我希望 CVR loss 权重从 1.0 提升到 2.0，缩小 CTR/CVR 权重差距
1. 作为推荐系统工程师，我希望按 user_type 分组监控 AUC，以便分别评估不同用户群体的效果
1. 作为推荐系统工程师，我希望新增离线序列特征（offline_chajia_click/like/order/search_click_100_seq），丰富用户行为表达
1. 作为推荐系统工程师，我希望新增跨场景比率特征（offline\_\*\_common_ratio），捕捉用户跨平台行为模式
1. 作为推荐系统工程师，我希望新增用户类型/活跃度特征（f_req_usertype, active_days），增强冷启动能力
1. 作为数据工程师，我希望 label_table 包含 is_home_scene/is_search_scene/is_chajia_scene 三个互斥的场景标记字段
1. 作为数据工程师，我希望比价负样本从 chajia_sample 的商品池中采样，使用 LATERAL VIEW + 等值 JOIN 避免 ODPS 笛卡尔积限制
1. 作为数据工程师，我希望 HASH 函数结果用 ABS 取绝对值，避免 ODPS HASH 返回负数导致采样失败
1. 作为数据工程师，我希望比价负样本的 JOIN 条件是严格等值表达式，符合 ODPS 语法限制
1. 作为算法工程师，我希望第零阶段 v1（ctr^0.3 × cvr^1.7）的失败经验被记录，避免重复踩坑
1. 作为算法工程师，我希望第零阶段 v2（0.3×ctr + 0.7×cvr）的实验结果被追踪，以便决定下一步方向
1. 作为算法工程师，我希望样本勘验 SQL 能验证负样本的正确性（正样本 item 不应出现在负样本中）
1. 作为算法工程师，我希望每个比价用户都有完整的 10 个负样本，避免训练信号不均衡

## Implementation Decisions

### 1. 融合公式方案

**决策**：使用加法融合 `score = w_ctr × ctr + w_cvr × cvr` 替代原始公式 `score = ctr × (1 + cvr)`。

**原因**：

- 指数加权 `ctr^α × cvr^β` 在 [0,1] 区间会放大微小差异，导致排序剧烈变化
- 加法融合的敏感度是线性的、可预测的
- 第零阶段 v1（ctr^0.3 × cvr^1.7）已验证失败（CTR -38.4%）

**分群参数**：

- 老用户：0.5 × ctr + 0.5 × cvr
- 新用户：0.4 × ctr + 0.6 × cvr
- 沉默用户：0.3 × ctr + 0.7 × cvr

### 2. 场景标记方案

**决策**：在 label_table 中添加三个互斥的 BIGINT 字段：`is_home_scene`、`is_search_scene`、`is_chajia_scene`。

**数据分布**（单天）：

- 推荐：1,270,414 pv（92.0%）
- 搜索：53,845 pv（3.9%）
- 比价正样本：57,021 pv（4.1%）
- 比价负样本：216,090 pv（新增）

### 3. 比价负采样方案

**决策**：使用 LATERAL VIEW POSEXPLODE + HASH 配对 + 等值 JOIN，每用户采样 10 个负样本。

**ODPS 兼容性约束**：

- 不允许笛卡尔积（CROSS JOIN）
- JOIN 条件必须是严格等值表达式（`a.col = b.col`）
- 没有 MOD 函数，用 `%` 运算符替代
- HASH 函数可能返回负数，需用 ABS 取绝对值

**实现方式**：

```sql
-- 预计算 target_rn
SELECT mmb_id, n AS seed,
       (n * 17 + ABS(HASH(mmb_id))) % total_items + 1 AS target_rn
FROM chajia_user_list
LATERAL VIEW POSEXPLODE(split(repeat('a,', 199), ',')) t AS n, val

-- 等值 JOIN
ON u.target_rn = p.item_rn

-- 排除已查价商品
WHERE NOT EXISTS (SELECT 1 FROM chajia_sample c WHERE c.mmb_id = u.mmb_id AND c.item_id = p.item_id)
```

### 4. 场景 mask 方案

**决策**：使用现有的 `task_space_indicator_label` 机制实现场景级别的梯度隔离，无需新开发代码。

**配置方式**：

- CTR 塔：`task_space_indicator_label: "is_home_scene"`，`out_task_space_weight: 0`
- CVR 塔：`task_space_indicator_label: "is_home_scene"`，`out_task_space_weight: 0`
- chajia_click 塔：`task_space_indicator_label: "is_chajia_scene"`，`out_task_space_weight: 0`
- search_ctr 塔：`task_space_indicator_label: "is_search_scene"`，`out_task_space_weight: 0`
- search_cvr 塔：`task_space_indicator_label: "is_search_scene"`，`out_task_space_weight: 0`

### 5. 样本权重方案

**决策**：

- CVR loss 权重从 1.0 提升到 2.0
- search_weight 在最终聚合样本集时计算（`home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v2`）
- 搜索场景样本权重 0.3，其他场景 1.0

### 6. 新增特征方案

**决策**：基于 FG config（`home_flow_2607_ctrcvr_sorter_config_fg_v2.json`）中的 864 个特征，筛选出 153 个未被当前模型使用的特征，按优先级新增：

| 优先级 | 类别            | 数量 | 说明                                                 |
| ------ | --------------- | ---- | ---------------------------------------------------- |
| P0     | 离线序列特征    | 48   | offline_chajia_click/like/order/search_click_100_seq |
| P1     | 跨场景比率      | 20   | offline\_\*\_common_ratio                            |
| P2     | 用户类型/活跃度 | 10   | f_req_usertype, active_days 等                       |
| P3     | 交叉特征        | 22   | 各种 \_fg 交叉特征                                   |

### 7. 模型架构

**基础架构**：PEPNet + DCNv2 + PLE（`pepnet_dcn_ple`）

**关键组件**：

- PEPNet frontend：DCNv2, CDOT, Bias, LHUC_EPNet
- PLE middle：ExtractionNet layers with CGC routing
- LHUC_PPNet towers：per-task personalization + final linear
- AFP（Automatic Feature Partitioning）
- 场景 mask：通过 task_space_indicator_label 实现

## Testing Decisions

1. **融合公式验证**：通过线上 A/B 实验验证，监控 pv_ctr、pv_cvr、uv_ctr、uv_cvr 四个指标
1. **负样本正确性校验**：
   - 正样本 item 不应出现在负样本中（预期 = 0）
   - 负样本 item 应全部来自 chajia 商品池（预期 = 0）
   - 每个比价用户应有完整的 10 个负样本（预期 100%）
1. **场景 mask 验证**：分别计算各场景的 AUC，确保无偏
1. **样本分布验证**：运行 `home_flow_2606_label_table_v2_audit.sql` 中的 8 个校验项

## Out of Scope

1. **独立建模**：不为新用户/沉默用户/老用户分别训练独立模型
1. **Hard Negative Mining**：当前使用随机采样，不使用基于相似度的 hard negative
1. **对比学习**：不使用 contrastive learning 方式学习用户/商品表征
1. **推理服务修改**：融合公式在线上推理服务中修改，不在本 PRD 范围内
1. **特征工程 SQL 修改**：FG config 的修改不在本 PRD 范围内，仅修改模型配置

## Further Notes

### 关键经验教训

1. **指数加权的陷阱**：在 [0,1] 区间，指数会放大微小差异，导致排序剧烈变化。ctr^0.3 × cvr^1.7 已验证严重负向。
1. **ODPS 笛卡尔积限制**：ODPS 严格禁止笛卡尔积，需用 LATERAL VIEW + 等值 JOIN 替代 CROSS JOIN。
1. **ODPS HASH 负数**：HASH 函数可能返回负数，需用 ABS 取绝对值。
1. **ODPS JOIN 条件限制**：JOIN 条件必须是严格等值表达式，复杂表达式需移到子查询预计算。
1. **没有 MOD 函数**：用 `%` 运算符替代。

### 实验路径

| 阶段        | 实验                     | 状态        | 结果                            |
| ----------- | ------------------------ | ----------- | ------------------------------- |
| 第零阶段 v1 | ctr^0.3 × cvr^1.7        | ❌ 完成     | CTR -38.4%, CVR +1.2%，严重负向 |
| 第零阶段 v2 | 0.3×ctr + 0.7×cvr        | 🔄 进行中   | 待观察                          |
| 第一阶段    | v18 分群特征 + loss 权重 | ✅ 配置完成 | 待训练                          |
| 第二阶段    | v19 场景 mask + 辅助任务 | 📝 计划中   | 本文档                          |

### 配置文件路径

- 基线配置：`data/pepnet_demo/config/v17/home_flow_2604_v17_chajia_click_seq2.config`
- 第一阶段配置：`data/pepnet_demo/config/v18/home_flow_2604_v18_user_segment.config`
- 第二阶段配置：`data/pepnet_demo/config/v19/home_flow_2604_v19_scene_mask.config`（待创建）
- Label 表：`data/pepnet_demo/sql/2606_sample/home_flow_2606_ctrcvr_sorter_label_table_v2`
- Sample 任务：`data/pepnet_demo/sql/2606_sample/home_flow_2606_ctrcvr_sorter_fix_sample_v2`
- FG 配置：`data/pepnet_demo/sql/2606_sample/home_flow_2607_ctrcvr_sorter_config_fg_v2.json`
- 样本勘验 SQL：`data/pepnet_demo/sql/2606_sample/home_flow_2606_label_table_v2_audit.sql`
