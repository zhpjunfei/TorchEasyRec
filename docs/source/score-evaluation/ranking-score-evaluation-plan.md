# 精排模型分数评估方案

> **来源**: 钉钉文档「链路分析」(tab 25)，作者 叁柒(冉康)，创建时间 06-08
> **适用框架**: tzrec / DLRM-HSTU
> **数据链路**: `stg_dh_pairec_debug_log_mi` → UDTF解析 → `dwd_pairec_request_item_stage_detail_mi` → request_id+item_id聚合 → `dwd_pairec_request_item_funnel_mi`
> **评估分支**: 漏斗分析 / 实验分析 / **分数分析** / 淘汰分析 / 策略分析

______________________________________________________________________

## 一、评估目标

精排模型分数评估的核心目标是验证模型输出分数的 **区分度**、**校准度**、**稳定性**，确保分数能够有效排序商品，支撑后续的重排、过滤等策略。

______________________________________________________________________

## 二、数据准备

### 2.1 数据来源

| 层级     | 表名                                      | 说明                                  |
| -------- | ----------------------------------------- | ------------------------------------- |
| 原始日志 | `stg_dh_pairec_debug_log_mi`              | 推荐系统原始调试日志                  |
| 解析明细 | `dwd_pairec_request_item_stage_detail_mi` | UDTF 解析后的逐条请求-商品明细        |
| 聚合数据 | `dwd_pairec_request_item_funnel_mi`       | request_id + item_id 聚合后的漏斗数据 |

### 2.2 所需字段

| 字段类别 | 字段名                                                    | 说明         |
| -------- | --------------------------------------------------------- | ------------ |
| 请求级   | `request_id`, `user_id`, `scene`, `timestamp`, `trace_id` | 请求上下文   |
| 曝光级   | `item_id`, `position`, `rank`, `exposure_score`           | 曝光信息     |
| 点击级   | `is_click`, `click_position`, `dwell_time`                | 点击行为     |
| 转化级   | `is_convert`, `convert_value`, `gmv`                      | 转化行为     |
| 模型级   | `pre_score`, `final_score`, `component_scores`            | 模型输出分数 |

______________________________________________________________________

## 三、评估维度

### 3.1 分数分布分析

**目的**: 检查模型分数的整体分布是否合理。

| 评估项       | 说明                                                                | 正常范围参考         |
| ------------ | ------------------------------------------------------------------- | -------------------- |
| 分位数统计   | P10, P25, P50, P75, P90, P95                                        | 各分位点应有合理跨度 |
| 分数区间占比 | \[0,0.1), \[0.1,0.3), \[0.3,0.5), \[0.5,0.7), \[0.7,0.9), [0.9,1.0] | 避免单峰聚集         |
| 直方图可视化 | 绘制分数分布直方图                                                  | 观察双峰、偏态异常   |
| 版本对比     | 与上一版本分数分布对比                                              | 检测显著偏移         |

**SQL 示例 — 分数分位数统计**:

```sql
SELECT
    percentile_cont(0.1) WITHIN GROUP (ORDER BY final_score) AS p10,
    percentile_cont(0.25) WITHIN GROUP (ORDER BY final_score) AS p25,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY final_score) AS p50,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY final_score) AS p75,
    percentile_cont(0.90) WITHIN GROUP (ORDER BY final_score) AS p90,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY final_score) AS p95,
    avg(final_score) AS mean_score,
    stddev(final_score) AS std_score
FROM dwd_pairec_request_item_funnel_mi
WHERE dt = '${bizdate}';
```

______________________________________________________________________

### 3.2 分数-CTR/CVR 相关性

**目的**: 验证分数是否能有效区分正负样本。

| 评估项     | 说明                                        |
| ---------- | ------------------------------------------- |
| 分桶命中率 | 按分数分桶（10桶），计算每桶的实际 CTR、CVR |
| 单调性检验 | 分数越高桶的 CTR/CVR 是否单调递增           |
| AUC / Gini | 计算分数对点击/转化的排序能力               |
| KS 值      | 衡量分数对正负样本的区分能力                |

**Python 示例 — 分数分桶分析**:

```python
import pandas as pd
import numpy as np

def score_bucket_analysis(
    df: pd.DataFrame,
    score_col: str = "final_score",
    label_col: str = "is_click",
    n_buckets: int = 10,
) -> tuple[pd.DataFrame, float]:
    """
    将样本按分数分桶，统计每桶的 CTR 和分数范围，并返回单调性比例。

    Returns:
        result: 每桶的统计 DataFrame
        monotonic_ratio: CTR 单调递增的比例
    """
    df = df.dropna(subset=[score_col, label_col])
    df["bucket"] = pd.qcut(
        df[score_col], q=n_buckets, labels=False, duplicates="drop"
    )

    result = (
        df.groupby("bucket")
        .agg(
            sample_count=(label_col, "count"),
            ctr=(label_col, "mean"),
            avg_score=(score_col, "mean"),
            min_score=(score_col, "min"),
            max_score=(score_col, "max"),
        )
        .reset_index()
    )

    # 检查单调性
    result["ctr_monotonic"] = result["ctr"].diff().ge(0)
    monotonic_ratio = result["ctr_monotonic"].mean()

    return result, float(monotonic_ratio)
```

______________________________________________________________________

### 3.3 分数排序能力评估

**目的**: 评估分数在排序场景中的实际效果。

| 指标            | 说明                        | 计算方式                                            |
| --------------- | --------------------------- | --------------------------------------------------- |
| **NDCG@K**      | 归一化折损累计增益          | 以模型分数作为排序依据，K=10/20/50                  |
| **Precision@K** | 前 K 个位置的点击率         | $\\frac{\\text{前K个正样本数}}{K}$                  |
| **Recall@K**    | 前 K 个位置覆盖的正样本比例 | $\\frac{\\text{前K个正样本数}}{\\text{总正样本数}}$ |
| **MRR**         | 平均 reciprocal rank        | 第一个正样本位置的倒数均值                          |

**Python 示例 — NDCG 计算**:

```python
import numpy as np

def dcg_at_k(rel_scores: np.ndarray, k: int) -> float:
    """计算 DCG@k"""
    rel = rel_scores[:k]
    positions = np.arange(1, len(rel) + 1)
    return np.sum(rel / np.log2(positions + 1))

def ndcg_at_k(true_labels: np.ndarray, scores: np.ndarray, k: int) -> float:
    """计算 NDCG@k"""
    dcg = dcg_at_k(scores, k)
    ideal_order = np.argsort(-true_labels)[:k]
    idcg = dcg_at_k(true_labels[ideal_order], k)
    return dcg / idcg if idcg > 0 else 0.0

def compute_ndcg_groups(
    df: pd.DataFrame,
    group_col: str,
    label_col: str = "is_click",
    score_col: str = "final_score",
    k: int = 10,
) -> pd.DataFrame:
    """按分组计算 NDCG@k"""
    results = []
    for grp, group_df in df.groupby(group_col):
        labels = group_df[label_col].values
        preds = group_df[score_col].values
        ndcg = ndcg_at_k(labels, preds, k)
        results.append({"group": grp, f"ndcg@{k}": ndcg})
    return pd.DataFrame(results)
```

______________________________________________________________________

### 3.4 分数稳定性评估

**目的**: 确保分数在不同时间、不同用户群体下保持稳定。

| 评估项             | 说明                                     | 阈值                                   |
| ------------------ | ---------------------------------------- | -------------------------------------- |
| **日粒度波动**     | 连续 30 天的平均分、P50 分数变化趋势     | 日均变化 < 5%                          |
| **用户分群稳定性** | 按新老用户、活跃度分层，观察各层分数分布 | —                                      |
| **物品分群稳定性** | 按品类、热度分层，检查分数偏差           | —                                      |
| **PSI**            | Population Stability Index               | < 0.1 稳定, 0.1~0.25 关注, > 0.25 预警 |

**Python 示例 — PSI 计算**:

```python
def calculate_psi(
    expected: np.ndarray,
    actual: np.ndarray,
    n_buckets: int = 10,
) -> float:
    """
    计算分数分布的 PSI (Population Stability Index)。

    Args:
        expected: 基准期分数数组
        actual: 评估期分数数组
        n_buckets: 分桶数量

    Returns:
        PSI 值
    """
    boundaries = np.percentile(
        expected, np.linspace(0, 100, n_buckets + 1)
    )
    boundaries = np.unique(boundaries)

    def get_distribution(data: np.ndarray) -> np.ndarray:
        hist, _ = np.histogram(data, bins=boundaries)
        pct = hist / len(data) + 1e-6  # 平滑防止除零
        return pct

    exp_dist = get_distribution(expected)
    act_dist = get_distribution(actual)

    psi = float(np.sum((act_dist - exp_dist) * np.log(act_dist / exp_dist)))
    return psi
```

______________________________________________________________________

### 3.5 分数校准度评估

**目的**: 验证模型输出的分数是否与真实概率一致。

| 评估项          | 说明                                                             |
| --------------- | ---------------------------------------------------------------- |
| **可靠性曲线**  | 横轴为模型分数，纵轴为实际 CTR，绘制 Reliability Diagram         |
| **ECE**         | Expected Calibration Error，期望校准误差                         |
| **Brier Score** | 分数与真实标签的均方误差                                         |
| **分桶校准**    | 对未校准分数进行 Platt Scaling 或 Isotonic Regression 校准后对比 |

**Python 示例 — 可靠性曲线与 ECE**:

```python
def reliability_diagram(
    df: pd.DataFrame,
    score_col: str = "final_score",
    label_col: str = "is_click",
    n_bins: int = 10,
) -> tuple[np.ndarray, np.ndarray, float]:
    """
    绘制可靠性曲线，返回分桶置信度和实际 CTR，以及 ECE。

    Returns:
        bin_confidence: 每桶的平均分数
        bin_accuracy: 每桶的实际 CTR
        ece: 期望校准误差
    """
    scores = df[score_col].values
    labels = df[label_col].values

    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_confidences = []
    bin_accuracies = []

    for i in range(n_bins):
        mask = (scores >= bin_edges[i]) & (scores < bin_edges[i + 1])
        if i == n_bins - 1:  # 最后一个桶包含右边界
            mask = (scores >= bin_edges[i]) & (scores <= bin_edges[i + 1])

        if mask.sum() > 0:
            bin_confidences.append(scores[mask].mean())
            bin_accuracies.append(labels[mask].mean())
        else:
            bin_confidences.append((bin_edges[i] + bin_edges[i + 1]) / 2)
            bin_accuracies.append(0.0)

    bin_confidences = np.array(bin_confidences)
    bin_accuracies = np.array(bin_accuracies)

    # ECE: 加权平均的绝对误差
    weights = np.array([
        ((scores >= bin_edges[i]) & (scores < bin_edges[i + 1])).sum()
        for i in range(n_bins)
    ])
    if i == n_bins - 1:
        weights[-1] = ((scores >= bin_edges[-2]) & (scores <= bin_edges[-1])).sum()

    ece = float(np.sum(weights * np.abs(np.array(bin_accuracies) - bin_confidences)) / len(scores))

    return bin_confidences, bin_accuracies, ece
```

______________________________________________________________________

## 四、实验对比评估

### 4.1 A/B 实验指标

在分数评估中，需结合线上 A/B 实验验证分数变更带来的业务影响：

| 指标类型     | 具体指标                       |
| ------------ | ------------------------------ |
| **核心指标** | CTR, CVR, GMV, ARPU            |
| **用户体验** | 人均浏览深度、停留时长、跳出率 |
| **商业指标** | 广告收入、转化率、客单价       |
| **长尾指标** | 新品曝光率、长尾商品 GMV 占比  |

### 4.2 离线实验

| 方法           | 说明                                                         |
| -------------- | ------------------------------------------------------------ |
| **同期对比**   | 同一时间段，不同模型版本的分数表现对比                       |
| **交叉验证**   | 使用 K 折交叉验证，确保评估结果的统计显著性                  |
| **显著性检验** | 使用 t 检验或 Bootstrap 方法验证差异显著性（p-value < 0.05） |

______________________________________________________________________

## 五、异常检测与告警

### 5.1 分数异常检测规则

| 异常类型 | 检测规则                 | 告警级别 |
| -------- | ------------------------ | -------- |
| 分数漂移 | 日均分数变化 > 5%        | P1       |
| 分布突变 | PSI > 0.2                | P1       |
| 零分异常 | 零分占比 > 10%           | P1       |
| 分数越界 | 超出 [0, 1] 范围         | P1       |
| 排序倒挂 | 高分数商品排在低分数之后 | P2       |

### 5.2 监控看板

建议建设以下监控看板：

1. **分数概览**: 实时分数分布、趋势图
1. **排序质量**: NDCG、AUC 等排序指标
1. **业务效果**: CTR、CVR、GMV 实时看板
1. **异常告警**: 分数异常、排序异常的自动告警

______________________________________________________________________

## 六、评估报告模板

每次模型迭代后，应输出标准化评估报告：

```markdown
## 精排模型分数评估报告

### 1. 版本信息
- 模型版本: DLRM-HSTU v3.x
- 评估日期: YYYY-MM-DD
- 数据周期: 近7天

### 2. 分数分布
- 平均分: X.XXXX
- P50: X.XXXX
- 标准差: X.XXXX
- PSI: X.XXX

### 3. 排序能力
- AUC: X.XXX (+/- X.XXX)
- NDCG@10: X.XXX
- NDCG@20: X.XXX

### 4. 校准度
- ECE: X.XXX
- 可靠性曲线: [附图]

### 5. 结论与建议
- [ ] 分数分布正常，无明显漂移
- [ ] 排序能力提升/下降 X%
- [ ] 建议上线/回滚
```

______________________________________________________________________

## 七、实施建议

1. **自动化评估**: 将上述评估逻辑集成到 tzrec 框架的评估流水线中，每次模型训练完成后自动执行
1. **基线对比**: 建立稳定的基线模型，所有新模型版本必须与基线对比
1. **持续监控**: 部署分数监控看板，实时跟踪分数变化和异常
1. **定期回顾**: 每周/每月回顾分数评估结果，发现潜在问题

______________________________________________________________________

## 附录

### A. 依赖说明

| 包         | 版本要求 | 用途     |
| ---------- | -------- | -------- |
| pandas     | >= 1.5   | 数据处理 |
| numpy      | >= 1.21  | 数值计算 |
| scipy      | >= 1.7   | 统计检验 |
| matplotlib | >= 3.5   | 可视化   |

### B. 与链路分析其他模块的关系

本方案对应钉钉文档中五大分析分支之一的 **分数分析**，与其他模块的关联如下：

```
                    dwd_pairec_request_item_funnel_mi
                   /          |           |           \
              漏斗分析     实验分析     分数分析      淘汰分析      策略分析
                 |           |           |            |            |
            转化率漏斗   A/B实验组    分数分布/排序   淘汰规则     排序策略
```

分数分析为实验分析提供离线排序指标，为策略分析提供分数阈值依据，为淘汰分析提供低分过滤标准。
