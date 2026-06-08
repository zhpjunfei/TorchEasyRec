______________________________________________________________________

## date: 2026-06-07 tags: [data, sql, sample-v1, 60d, label-30d, base] related: \["\[[sample-v2-7d]\]", "\[[sql-attribution-30d-vs-24h]\]", "\[[../20-experiments/ab-test-2026-06-06]\]"\]

# Sample v1 — 60 天样本集 (线上 base 使用)

> 线上 base 模型 `pepnet_v4_cdot32_weight03` 训练用的样本. **30 天归因**, 60 天数据.

## 路径

- ODPS 表: `home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1a_smpl_weight`
- fg_task: `v2_training_set`
- label_table: `home_flow_2604_ctrcvr_sorter_label_table_v1.sql` (**30 天归因**)
- 主 SQL: `home_flow_2604_ctrcvr_sorter_fix_sample_v2.sql`
  - `DISTRIBUTE BY RAND() + SORT BY RAND()`
  - `dt > bizdate-60`

## 关键特征

1. **数据规模**: 60 天 ≈ 13 亿 (60 × 22M/d)
1. **归因窗口**: 30 天 (label_table 用 `cv_time < click_time + 2592000`)
1. **数据分布**: `DISTRIBUTE BY RAND() + SORT BY RAND()` (两层随机)
1. **加权**: `search_price` 非折扣页 0.3, 其他 1.0

## 与 sample_v2 (7d) 关键差异

| 维度                    | sample_v1 (60d)                         | sample_v2 (7d)                               |
| :---------------------- | :-------------------------------------- | :------------------------------------------- |
| 数据量                  | ~13亿                                   | ~1.5亿 (**9x 劣势**)                         |
| 归因窗口                | 30 天                                   | 24 小时                                      |
| label_table             | v1                                      | v3                                           |
| 分桶                    | `DISTRIBUTE BY RAND() + SORT BY RAND()` | `DISTRIBUTE BY CAST(RAND()*10000 AS BIGINT)` |
| ALTER ADD search_weight | 否                                      | 是                                           |

**重要**: 这两套样本**不可直接对比** — 数据量 / 归因窗口 / pCVR 含义都不同. 详见 \[[sql-attribution-30d-vs-24h|sql 归因差异]\].

## 在 A/B 测试中的角色

\[[../20-experiments/ab-test-2026-06-06|2026-06-06 A/B]\] base = `pepnet_v4_cdot32_weight03` (60d 数据, production-tuned)

- exp1 = `v6_domain_id_only` (7d)
- exp2 = `v6_ple_d` (7d)
- **base 久经校准, exp 新训练** — 不公平

## 文件位置

`data/pepnet_demo/sql/sample_v1/`

- `home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1a_smpl_weight.sql`
- `home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v1c.py`
- `home_flow_2604_ctrcvr_sorter_fix_sample_v2.sql`
- `home_flow_2604_ctrcvr_sorter_label_table_v1.sql`

## 下一步

- \[[sample-v2-7d|7d 样本]\] — v6+ 实验使用
- \[[sql-attribution-30d-vs-24h|归因窗口差异]\]
