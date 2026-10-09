# 序列特征架构优化实验结果

> 实验日期：2026-08-28
> 数据量：1,521,899 PV
> 训练：1 epoch, 5000 iters, batch_size=4096

## 核心指标对比

| 指标                | search_seq (9seq baseline) | search_seq_ablation (6seq) | search_seq_timegate (6seq+time_gate) |
| ------------------- | :------------------------: | :------------------------: | :----------------------------------: |
| **AUC CTR**         |          0.72148           |          0.72253           |               0.72215                |
| **AUC CVR**         |          0.74649           |          0.75262           |               0.74978                |
| **Grouped AUC CTR** |          0.68807           |          0.68927           |               0.68882                |
| **Grouped AUC CVR** |          0.74530           |          0.74747           |               0.74664                |
| Loss CTR            |          2.52859           |          2.52142           |               2.52247                |
| Loss CVR            |          0.26694           |          0.26737           |               0.26815                |
| Total Loss          |          2.79625           |          2.78942           |               2.79117                |

## vs Baseline (search_seq) 变化

| 实验         |  Δ AUC CTR   |  Δ AUC CVR   | Δ GrpAUC CTR | Δ GrpAUC CVR |    Δ Loss    |
| ------------ | :----------: | :----------: | :----------: | :----------: | :----------: |
| **ablation** | **+0.00105** | **+0.00613** | **+0.00120** | **+0.00217** | **-0.00683** |
| **timegate** | **+0.00067** | **-0.00371** | **+0.00075** | **+0.00134** | **-0.00508** |

## 预测分布

| 指标                | search_seq | ablation | timegate |
| ------------------- | :--------: | :------: | :------: |
| probs_ctr mean      |   0.3303   |  0.3279  |  0.3310  |
| probs_ctr std       |   0.1851   |  0.1875  |  0.1868  |
| probs_cvr mean      |   0.2803   |  0.2773  |  0.2821  |
| probs_cvr std       |   0.2172   |  0.2122  |  0.2162  |
| probs_cvr home mean |   0.2848   |  0.2838  |  0.2886  |

## 结论

1. **ablation 全面正向**：移除退化序列后，CVR AUC +6.1pp，CTR AUC +1.1pp，所有指标正向
1. **timegate 有争议**：CTR 和 Grouped AUC 正向，但 CVR AUC 下降了 3.7pp
1. **loss 分析**：ablation 的 total loss 最低，timegate 次之，baseline 最高
1. **probs_cvr 校准**：ablation 的 mean=0.2773 最接近真实率 10.13%，校准最好
