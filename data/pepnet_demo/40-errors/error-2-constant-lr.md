______________________________________________________________________

## date: 2026-05-31 tags: [error, confounded, constant-lr, sql-attribution, lesson] status: resolved

# 错误 2: constant_lr 结论 confounded + SQL 归因窗口

## 触发时间

2026-05-31

## 上下文

- 之前 \[[error-1-fixedlr]\] 用 fixedlr 跑出 CVR 0.76970, 误以为找到了优化
- 进一步推理: "如果 constant_lr 更好, 那 sample_v2 (7d) 的所有结论可能都不准"
- 准备用 fixedlr 重新跑 v6+ 实验

## 错误行为

- 准备用 fixedlr 替代 cosine 作为生产 baseline
- 推断 "v6+ 0.78x CVR 可能都是 0.74x 真实"

## 根因

**错误 1 同源**: 同时改了 LR schedule 和 weight_decay, 见 \[[error-1-fixedlr]\].

**附根因 (2026-06-06 发现)**: 离线 vs 在线 CVR 数字比较前, 没读 label_table SQL, 不知道 sample_v1 (60d) 和 sample_v2 (7d) 归因窗口不同 (30d vs 24h), 见 \[[../30-data/sql-attribution-30d-vs-24h|sql 归因差异]\].

## 为什么出错

- 没坚持单变量变更 (同 \[[error-1-fixedlr]\])
- 离线 CVR 数字比较前没读 SQL
- 跨数据集对比时没意识到 pCVR 含义可能不同

## 正确做法

1. 任何"对比"只改一个变量
1. 离线 vs 在线 CVR 数字比较前, 必读 label_table SQL
1. 跨数据集对比时, 标注数据量 / 归因窗口 / 校准差异

## 预防

- [ ] 单变量变更原则
- [ ] 离线 vs 在线比较前, 必读 label_table
- [ ] 跨数据集对比, 标注 3 类差异 (数据量/归因/校准)

## 关联

- \[[error-1-fixedlr]\] — 同 confounded 模式
- \[[../30-data/sql-attribution-30d-vs-24h|sql 归因差异]\] — 附根因
- \[[index|错误总结]\]
