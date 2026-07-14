# 精排模型分数评估方案

**适用模型**: PEPNet-DCN-PLE 多任务
**模型配置**: `data/pepnet_demo/config/v6/home_flow_2604_v6_ple_d.config`
**数据源**: `home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3`

______________________________________________________________________

## 一、分数定义

### 1.1 双塔输出

`pepnet_dcn_ple.py` 第 528-541 行，遍历 task_towers 顺序为 ctr 先、cvr 后：

```
CTR Tower:  logits_ctr = tower_final_ctr(hidden)
            probs_ctr = sigmoid(logits_ctr)

CVR Tower:  raw_logits_cvr = tower_final_cvr(hidden)
            final_logits_cvr = raw_logits_cvr + logits_ctr   # cvr_add_ctr_logits=true
            probs_cvr = sigmoid(final_logits_cvr)
```

**关键事实**：`cvr_add_ctr_logits: true`，CVR 分数天然包含了 CTR 信息。

### 1.2 业务排序分数（需确认）

| 选项 | 公式                    | 说明                     |
| ---- | ----------------------- | ------------------------ |
| A    | `probs_ctr`             | 仅点击率                 |
| B    | `probs_ctr × probs_cvr` | CT-CVR 乘积（ESMM 思路） |
| C    | `probs_cvr`             | 转化率（已含点击信息）   |

______________________________________________________________________

## 二、数据链路

```
home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3
        │
        ▼  search_weight 采样 + Shuffle + Split
home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight
        │
        ├── dt 前7天  → train  (search_weight: 搜索=0.3, 其他=1.0)
        └── dt 前30天  → val
```

**所需字段**：

| 字段                               | 用途                               |
| ---------------------------------- | ---------------------------------- |
| `item_id`, `position`              | 排序位置                           |
| `is_click`, `is_conversion`        | 正负样本标签                       |
| 模型输出 `probs_ctr` / `probs_cvr` | 评估分数（来自评估日志或预测日志） |

______________________________________________________________________

## 三、评估步骤

### 步骤 1：分数分布 + PSI

**目的**：监测分数漂移。

**SQL**（MaxCompute，需 `dwd_pairec_request_item_funnel_mi` 中包含模型分数）：

```sql
SELECT
    PERCENTILE(score, 0.10)  AS p10,
    PERCENTILE(score, 0.50)  AS p50,
    PERCENTILE(score, 0.90)  AS p90,
    AVG(score)               AS mean_score,
    STDDEV(score)            AS std_score
FROM dwd_pairec_request_item_funnel_mi
WHERE dt = '${bizdate}' AND scene = 'home_flow'
```

**PSI 计算**（Python）：

```python
import numpy as np

def calculate_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    boundaries = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    boundaries = np.unique(boundaries)
    def _dist(data):
        h, _ = np.histogram(data, bins=boundaries)
        return h / len(data) + 1e-6
    e, a = _dist(expected), _dist(actual)
    return float(np.sum((a - e) * np.log(a / e)))

# 判定: PSI < 0.1 稳定; 0.1~0.25 预警; > 0.25 告警
```

### 步骤 2：分桶 CTR 分析

**目的**：验证分数单调区分能力。

```python
import pandas as pd

def bucket_analysis(df, score_col="probs_ctr", label_col="is_click", n=10):
    df = df.dropna(subset=[score_col, label_col]).copy()
    df["bucket"] = pd.qcut(df[score_col], q=n, labels=False, duplicates="drop")
    r = df.groupby("bucket").agg(
        n=(label_col, "count"), ctr=(label_col, "mean"),
        smin=(score_col, "min"), smax=(score_col, "max")
    ).reset_index()
    r["mono"] = r["ctr"].diff().bfill().ge(0)
    return r

# 判定: 单调性比例 >= 90%; 最高桶CTR / 最低桶CTR >= 3:1
```

### 步骤 3：离线排序指标

**目的**：量化排序能力。

tzrec 内置指标（在 config 中配置，评估结果输出到 `model_dir/eval_result.txt`）：

| 指标               | 配置方式                                              | 当前状态  |
| ------------------ | ----------------------------------------------------- | --------- |
| AUC                | `metrics { auc {} }`                                  | ✅ 已启用 |
| XAUC               | `metrics { xauc { sample_ratio: 1e-3 } }`             | ❌ 需追加 |
| Grouped AUC        | `metrics { grouped_auc { grouping_key: "user_id" } }` | ❌ 需追加 |
| Decay AUC          | `train_metrics { decay_auc { thresholds: 200 } }`     | ❌ 需追加 |
| Normalized Entropy | `train_metrics { normalized_entropy {} }`             | ❌ 需追加 |

**补充指标**（需自行实现）：NDCG@K, MRR, Precision@K

### 步骤 4：校准度评估

**目的**：验证分数是否等于真实概率。

```python
def reliability_diagram(scores, labels, n_bins=10):
    edges = np.linspace(0, 1, n_bins + 1)
    centers, ctors, counts = [], [], []
    for i in range(n_bins):
        m = (scores >= edges[i]) & (scores < edges[i + 1])
        if m.sum() == 0: continue
        centers.append((edges[i] + edges[i+1]) / 2)
        ctors.append(labels[m].mean())
        counts.append(m.sum())
    w = np.array(counts) / len(scores)
    ece = float(np.sum(w * np.abs(np.array(ctors) - np.array(centers))))
    return centers, ctors, ece

# 判定: ECE < 0.02 优秀; < 0.05 可接受
```

______________________________________________________________________

## 四、离线实验执行

参考 `data/pepnet_demo/sql/sample_v2/tran_v6_ple_d.sh`：

```bash
export TORCH_MANUAL_SEED=42
export NUMPY_MANUAL_SEED=42
export USE_DETERMINISTIC_ALGORITHMS=1
export EVAL_SEED=42

ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
torchrun --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
-m tzrec.train_eval \
  --pipeline_config_path data/pepnet_demo/config/v6/home_flow_2604_v6_ple_d.config \
  --train_input_path odps://mmb_sage/tables/..._smpl_weight_train/dt=${train_ymd} \
  --eval_input_path odps://mmb_sage/tables/..._smpl_weight_val/dt=${train_ymd} \
  --model_dir /path/to/model_dir
```

评估结果在 `model_dir/eval_result.txt`，格式：

```json
{"global_step": 1000, "auc": 0.723456, "auc_cvr": 0.654321}
```

______________________________________________________________________

## 五、异常检测规则

| 异常       | 规则                     | 级别 |
| ---------- | ------------------------ | ---- |
| 分数漂移   | 日均分数变化 > 5%        | P1   |
| 分布突变   | PSI > 0.2                | P1   |
| 单调性破坏 | 分桶 CTR 单调性 < 80%    | P2   |
| AUC 下跌   | 离线 AUC 跌 > 0.5%       | P2   |
| NE 上升    | Normalized Entropy > 1.0 | P2   |

______________________________________________________________________

## 六、基线对比

| 项目     | 值                                               |
| -------- | ------------------------------------------------ |
| 基线配置 | `home_flow_2604_v6_baseline.config`              |
| 当前配置 | `home_flow_2604_v6_ple_d.config`                 |
| 对比方式 | 同数据集、同 epoch、t-test 显著性检验 (p < 0.05) |
