# PEPNet_v2 实验结果汇总

## 实验结果

| #   | Config                       |  CDOT  | DCNv2 | cvr_add_ctr | Tower | Epoch |  CTR AUC  |  CVR AUC  | 说明             |
| --- | ---------------------------- | :----: | :---: | :---------: | :---: | :---: | :-------: | :-------: | ---------------- |
| 1   | pepnet                       |  all   |  ❌   |    true     |  512  |   1   |   0.685   |   0.736   | 基线             |
| 2   | pepnet_nocdot                |   ❌   |  ❌   |    true     |  512  |   1   |   0.686   |   0.736   | CDOT all 无用    |
| 3   | pepnet_nocdot_noadd          |   ❌   |  ❌   |    false    |  512  |   1   |     —     |   0.731   | cvr_add_ctr 必开 |
| 4   | pepnet_tower256              |  all   |  ❌   |    true     |  256  |   1   |   略差    |   略差    | 小 tower 弱      |
| 5   | pepnet_epoch3                |  all   |  ❌   |    true     |  512  |   3   |   0.658   |   0.704   | 3 epoch 过拟合   |
| 6   | pepnet_cdot_domain           | domain |  ❌   |    true     |  512  |   1   |   0.690   |   0.739   | CDOT domain 有效 |
| 7   | **pepnet_cdot_domain_dcnv2** | domain |   ✓   |    true     |  512  |   1   | **0.693** | **0.740** | 🏆 最优          |

## 关键结论

1. **DCNv2 有效** — cross_num=4, low_rank=256，CDOT domain + DCNv2 比纯 nocdot 高 +0.7pp CTR, +0.4pp CVR
1. **CDOT all 无用，CDOT domain 有用** — domain group 3 个特征信号干净，CDOT 能学到东西
1. **cvr_add_ctr_logits 必开** — 关闭掉 0.5pp CVR
1. **1 epoch 最优** — 3 epoch 过拟合严重 (CTR 0.658, CVR 0.704)

## 优化方向

### 微调（空间小）

| 方向       | 具体尝试                      | 预期                  |
| ---------- | ----------------------------- | --------------------- |
| DCNv2 参数 | `cross_num=2`, `low_rank=128` | 轻量化，防过拟合      |
| 学习率     | cosine warmup 500             | 让 cross 多预热       |
| Tower 结构 | `[512,256]`, PPNet gamma=1.0  | 让 cross 承担更多交叉 |

### 重点突破（空间大）

| 方向             | 具体尝试                             | 预期                  |
| ---------------- | ------------------------------------ | --------------------- |
| **relation_mlp** | CVR tower 接收 CTR logits 做额外输入 | v1c 高 2pp CVR 的核心 |
| CDOT 精选特征    | domain 3 个 + 1-2 个高价值 KV/ratio  | 补充低频交叉信号      |

## Config 文件

| Config                      | 路径                                             |
| --------------------------- | ------------------------------------------------ |
| pepnet (基线)               | `home_flow_2604_pepnet.config`                   |
| pepnet_nocdot (最佳无 CDOT) | `home_flow_2604_pepnet_nocdot.config`            |
| pepnet_cdot_domain          | `home_flow_2604_pepnet_cdot_domain.config`       |
| 🏆 pepnet_cdot_domain_dcnv2 | `home_flow_2604_pepnet_cdot_domain_dcnv2.config` |
| pepnet_epoch3               | `home_flow_2604_pepnet_epoch3.config`            |
| pepnet_tower256             | `home_flow_2604_pepnet_tower256.config`          |
