______________________________________________________________________

## date: 2026-06-07 tags: [data, sql, attribution, 30d-vs-24h, confounder, critical] status: critical-discovery related: \["\[[sample-v1-60d]\]", "\[[sample-v2-7d]\]", "\[[../20-experiments/ab-test-2026-06-06]\]"\]

# SQL 标签归因窗口 30d vs 24h 关键差异 ⭐

> 2026-06-06 关键发现: 线上 base (60d + 30d 归因) vs v6+ 实验 (7d + 24h 归因) 的 pCVR 含义完全不同. **不可直接对比, 是 A/B 测试 pvctr 退步主因之一**.

## 5 大 SQL 差异 (2026-06-06 发现)

| 维度         | sample_v1 (60d, 线上 base)              | sample_v2 (7d, v6+ exp)                      |
| :----------- | :-------------------------------------- | :------------------------------------------- |
| **归因窗口** | 30 天归因                               | **24 小时归因**                              |
| 含义         | pCVR="30 天内转化"                      | pCVR="**24 小时内转化**"                     |
| 数据量       | ~13亿 (60d)                             | ~1.5亿 (7d)                                  |
| label_table  | v1                                      | v3                                           |
| 分桶         | `DISTRIBUTE BY RAND() + SORT BY RAND()` | `DISTRIBUTE BY CAST(RAND()*10000 AS BIGINT)` |

## 含义不同的具体代码

### label_table_v1.sql (60d, 30 天归因)

```sql
WHERE is_conversion = 1
  AND cv_time < click_time + 2592000  -- 30 天 = 2592000 秒
```

### label_table_v3.sql (7d, 24h 归因)

```sql
WHERE is_conversion = 1
  AND cv_time < click_time + 86400  -- 24h = 86400 秒
```

## 为什么重要

1. **绝对 CVR AUC 数字不可比**:

   - v1 (30d 归因): 模型在"30 天内是否转化"上打分
   - v3 (24h 归因): 模型在"24 小时内是否转化"上打分
   - 30d 归因下正样本更多, AUC 数字系统性偏高

1. **A/B 测试 pvctr 退步主因之一**:

   - \[[../20-experiments/ab-test-2026-06-06|2026-06-06 A/B]\] exp1/exp2 用 7d 24h, base 用 60d 30d
   - exp 的 pCVR 信号更稀疏 (24h 内能转化的少于 30 天内能转化的)
   - 加上 9x 数据劣势 → exp1/exp2 pvctr 退步

1. **离线 vs 在线 CVR 数字比较前, 必读 label_table SQL**

## 9x 数据劣势 + 30d vs 24h 归因 + 校准 = 三不公平

| 维度     | 不公平                      | 影响                            |
| :------- | :-------------------------- | :------------------------------ |
| 数据量   | 60d vs 7d (**9x**)          | pCTR 弱排序 → 错排 → pvctr 退步 |
| 归因窗口 | 30d vs 24h                  | pCVR 含义不同, 24h 信号更稀疏   |
| 校准     | base 久经校准 vs exp 新训练 | base 阈值匹配当前流量           |

**当前 A/B 不能下结论**:

- ❌ v6_ple_d 优于 v4 (60d vs 7d 不公平)
- ❌ v6 架构不能上产
- ❌ v1c vs v6_ple_d 离线 +2.4pp 不可直接相加

**当前 A/B 已证实**:

- ✅ 同 7d 下, exp2 (v6_ple_d) > exp1 (v6_domain_id_only) +5.3% (Z=2.6)
- ✅ PLE + d 架构在 7d 数据下真实业务价值

## 建议

1. **统一归因窗口** (P1 决策): 是否统一到 24h 归因, 或回退 30d
1. **公平 A/B** (P2): v6_baseline_hbs (7d) vs v6_ple_d (7d), 排除数据规模因素
1. **离线 CVR 翻译三条件**:
   - ① 同验证集
   - ② 同训练数据
   - ③ 可比 base

## 教训 (写在 \[[../40-errors/error-2-constant-lr|错误 2]\])

- 离线 vs 在线 CVR 数字比较前, 必读 label_table SQL
- 多变量同时变化 = confounded, 不可归因

## 下一步

- \[[sample-v1-60d|60d 样本]\]
- \[[sample-v2-7d|7d 样本]\]
- 统一归因窗口决策 (P1)
- 公平 A/B 设计 (P2)
