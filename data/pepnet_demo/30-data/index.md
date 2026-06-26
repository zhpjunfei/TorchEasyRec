______________________________________________________________________

## date: 2026-06-26 tags: [data, index] status: active related: \["\[[sample-v1-60d]\]", "\[[sample-v2-7d]\]", "\[[sample-v3-pipeline]\]"\]

# 30-data — 数据 / SQL

> 训练样本定义、SQL 流水线与数据分析。

## 笔记列表

| 文件                             | 说明                                         |  状态  |
| :------------------------------- | :------------------------------------------- | :----: |
| \[[sample-v1-60d]\]              | 60 天样本集 (线上 base 使用)                 | active |
| \[[sample-v2-7d]\]               | 7 天样本集 (v6+ 实验使用)                    | active |
| \[[sample-v3-pipeline]\]         | sample_v3 特征工程全流程: SQL → FG → EasyRec | active |
| \[[site-mapping]\]               | site/level 分布分析                          | active |
| \[[sql-attribution-30d-vs-24h]\] | 标签归因窗口 30d vs 24h 关键差异 ⭐          | active |

## 样本版本关系

```
sample-v1 (60d) ──→ 线上 base
    └── sample-v2 (7d) ──→ v6+ experiments
            └── sample-v3 (full pipeline) ──→ 下一代
```

## 相关 SQL

- `sql/sample_v1/` — sample-v1 查询
- `sql/sample_v2/` — sample-v2 查询
- `sql/sample_v3/` — sample-v3 全流水线
- `sql/analysis/` — 分析查询
