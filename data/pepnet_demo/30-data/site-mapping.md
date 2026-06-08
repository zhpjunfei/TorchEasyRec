______________________________________________________________________

## date: 2026-06-07 tags: [data, site, level, distribution, exploratory] related: \["\[[sql-attribution-30d-vs-24h]\]", "\[[../10-architecture/data-schema]\]"\]

# Site / Level 分布分析 (摘要)

> 完整映射表 (350+ 站点) 见 `99-archive/site_mapping.md`. 本文档仅保留关键发现.

## 站点编码 → 站点名映射

完整 350 个 site_id → sitename 映射见 `99-archive/site_mapping.md` (老文件, 保留供追溯).

## 关键发现

| site_id | sitename | 特征             | 业务影响                                       |
| :-----: | :------- | :--------------- | :--------------------------------------------- |
| **346** | 话题     | **click→CVR 0%** | content stream, 无转化, 建议在 bias group 降权 |
|  其他   | 商品站   | click→CVR > 0    | 正常商品站                                     |

## Level 分布

| level | 占比 | click→CVR |
| :---: | :--: | :-------: |
|   B   | 26%  |   较高    |
|   F   | 41%  |   较低    |
| 其他  | 33%  |   中等    |

**单调关系**: B → F, click→CVR 单调递减.

## 数据来源

- `99-archive/site_mapping.md` (356 行, May 30 老文件)
- `99-archive/feature_understanding.md` (May 30 老文件, 详细分析)

## 在模型中的角色

| 字段      | 用途                                                        |
| :-------- | :---------------------------------------------------------- |
| `site_e`  | bias group (首维 1-dim 偏置), lhuc group (EPNet/PPNet 门控) |
| `level_e` | bias group, lhuc group                                      |

## 下一步

- \[[sql-attribution-30d-vs-24h|sql 归因差异]\]
- \[[../10-architecture/data-schema|特征 schema]\]
