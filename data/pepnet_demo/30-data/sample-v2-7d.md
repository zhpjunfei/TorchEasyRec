______________________________________________________________________

## date: 2026-06-07 tags: [data, sql, sample-v2, 7d, label-24h] related: \["\[[sample-v1-60d]\]", "\[[sql-attribution-30d-vs-24h]\]"\]

# Sample v2 — 7 天样本集 (v6+ exp 使用)

> v6+ 实验 (v6_baseline, v6_ple, v6_ple_d 等) 训练用的样本. **24 小时归因**, 7 天数据.

## 路径

- ODPS 表: `home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight` (注: 表名带 30d 但实际是 7d)
- 实际: `home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_7d_v3_smpl_weight`
- fg_task: `v3_training_set`
- label_table: `home_flow_2604_ctrcvr_sorter_label_table_v3.sql` (**24 小时归因**)
- 主 SQL: `home_flow_2604_ctrcvr_sorter_fix_sample_v3.sql`
  - `DISTRIBUTE BY CAST(RAND()*10000 AS BIGINT)`
  - `dt > bizdate-7`

## 关键特征

1. **数据规模**: 7 天 ≈ 1.5亿
1. **归因窗口**: 24 小时 (label_table 用 `cv_time < click_time + 86400`)
1. **数据分布**: `DISTRIBUTE BY CAST(RAND()*10000 AS BIGINT)` (单层 hash 分桶)
1. **加权**: `search_price` 非折扣页 0.3, 其他 1.0
1. **ALTER ADD search_weight**: 在表创建后 ALTER TABLE 加列

## "更现代"的设计 (vs sample_v1)

| 维度                | sample_v1 (60d) | sample_v2 (7d)         |
| :------------------ | :-------------- | :--------------------- |
| per-impression 标签 | ❌ 多曝光共享   | ✅ per-impression      |
| request_id          | ❌              | ✅ NOT NULL            |
| bot 过滤            | ❌              | ✅ HAVING COUNT < 3000 |
| 标题向量防泄漏      | ❌              | ✅                     |

**v3 是更现代的设计**, 但也意味着 pCVR 含义从"30 天内转化"变成"24 小时内转化", 绝对 CVR AUC 数字不可比.

## 与 sample_v1 (60d) 关键差异

| 维度                    | sample_v1 (60d)                         | sample_v2 (7d)                               |
| :---------------------- | :-------------------------------------- | :------------------------------------------- |
| 数据量                  | ~13亿                                   | ~1.5亿 (**9x 劣势**)                         |
| 归因窗口                | 30 天                                   | 24 小时                                      |
| label_table             | v1                                      | v3                                           |
| 分桶                    | `DISTRIBUTE BY RAND() + SORT BY RAND()` | `DISTRIBUTE BY CAST(RAND()*10000 AS BIGINT)` |
| ALTER ADD search_weight | 否                                      | 是                                           |

**重要**: 这两套样本**不可直接对比**. 详见 \[[sql-attribution-30d-vs-24h|sql 归因差异]\].

## 在 A/B 测试中的角色

\[[../20-experiments/ab-test-2026-06-06|2026-06-06 A/B]\] exp1/exp2 都用 7d (v3 SQL):

- exp1 = `v6_domain_id_only` (7d) → pvctr -10.4%
- exp2 = `v6_ple_d` (7d) → pvctr -5.6%
- exp2 > exp1 +5.3% 显著 (同 7d 下架构差异)

**核心问题**: 不能与 base (60d) 直接比较 — 9x 数据劣势 + 归因窗口不同 + 校准差异.

## 文件位置

`data/pepnet_demo/sql/sample_v2/`

- `home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight.sql` (表名带 30d 但 7d)
- `home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3.py`
- `home_flow_2604_ctrcvr_sorter_fix_sample_v3.sql`
- `home_flow_2604_ctrcvr_sorter_label_table_v3.sql`

## 下一步

- \[[sample-v1-60d|60d 样本]\]
- \[[sql-attribution-30d-vs-24h|归因窗口差异]\]
- 修后 5-run 重评 v6_ple_d (见 \[[../20-experiments/eval-pipeline-fix]\])
