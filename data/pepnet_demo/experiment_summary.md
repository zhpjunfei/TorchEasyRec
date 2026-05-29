# PEPNet_v2 实验结果汇总

## 第一阶段：结构探索

| #   | Config                   |  CDOT  | DCNv2 | cvr_add_ctr | Tower | Epoch |  CTR AUC  |  CVR AUC  | 说明             |
| --- | ------------------------ | :----: | :---: | :---------: | :---: | :---: | :-------: | :-------: | ---------------- |
| 1   | pepnet                   |  all   |  ❌   |    true     |  512  |   1   |   0.685   |   0.736   | 基线             |
| 2   | pepnet_nocdot            |   ❌   |  ❌   |    true     |  512  |   1   |   0.686   |   0.736   | CDOT all 无用    |
| 3   | pepnet_nocdot_noadd      |   ❌   |  ❌   |    false    |  512  |   1   |     —     |   0.731   | cvr_add_ctr 必开 |
| 4   | pepnet_tower256          |  all   |  ❌   |    true     |  256  |   1   |   略差    |   略差    | 小 tower 弱      |
| 5   | pepnet_epoch3            |  all   |  ❌   |    true     |  512  |   3   |   0.658   |   0.704   | 3 epoch 过拟合   |
| 6   | pepnet_cdot_domain       | domain |  ❌   |    true     |  512  |   1   |   0.690   |   0.739   | CDOT domain 有效 |
| 7   | pepnet_cdot_domain_dcnv2 | domain |   ✓   |    true     |  512  |   1   | **0.693** | **0.740** | 🏆 原最佳        |

## 第二阶段：超参数微调

| #   | Config            | 变化                      | CTR AUC |  CVR AUC  |
| --- | ----------------- | ------------------------- | :-----: | :-------: |
| 8   | cross2            | cross_num=2, low_rank=128 |  0.693  |   0.740   |
| 9   | gamma1            | ppnet_gamma=1.0           |  0.694  |   0.741   |
| 10  | warmup1000        | warmup_size=1000          |  0.694  | **0.742** |
| 11  | warmup1000_gamma1 | warmup=1000 + gamma=1.0   |  0.693  | **0.742** |
| 12  | warmup1000_lr5e4  | warmup=1000 + lr=5e-4     |  0.692  |   0.742   |
| 13  | warmup1500        | warmup_size=1500          |  0.693  |   0.740   |

## 关键结论

1. **DCNv2 有效** — cross_num=4, low_rank=256，CDOT domain + DCNv2 比纯 nocdot 高 +0.7pp CTR, +0.4pp CVR
1. **CDOT all 无用，CDOT domain 有用** — domain group 3 个特征信号干净，CDOT 能学到东西
1. **cvr_add_ctr_logits 必开** — 关闭掉 0.5pp CVR
1. **1 epoch 最优** — 3 epoch 过拟合严重 (CTR 0.658, CVR 0.704)
1. **warmup 有效** — 500→1000 带来 +0.2pp，更长预热帮助 DCNv2 收敛
1. **超参数已接近天花板** — 第二阶段所有微调效果 ±0.1pp 以内震荡，无实质突破

## 综合最优配置

```
CDOT:       domain (mmb_id, item_id, f_req_page)
DCNv2:      cross_num=4, low_rank=256
Bias:       domain
LHUC:       domain
cvr_add_ctr: true
Tower:      [512, 256, 128], PPNet gamma=2.0
Warmup:     cosine warmup 1000
LR:         0.001
Weight decay: 0.01 (仅 MLP.weight + cdot.sub_compress_weight)
```

最佳 AUC: **CTR 0.694**, **CVR 0.742**

## 下一步方向

| 方向                                                         |   预期提升   | 难度 |
| ------------------------------------------------------------ | :----------: | :--: |
| **relation_mlp** — CVR tower 接入 CTR logits 做额外 MLP 输入 | **~2pp CVR** |  中  |
| CDOT 精选特征 — domain 3 个 + 1-2 个高价值 KV/ratio          |  0.1-0.3pp   |  低  |
| Cross 结构探索 — CrossNet 变体替代 DCNv2                     |     未知     |  高  |

relation_mlp 是当前 PEPNet_v2 和 v1c 最大的结构差距，也是唯一可以带来显著提升的方向。

## Config 文件

| Config                             | 路径                                                        |
| ---------------------------------- | ----------------------------------------------------------- |
| pepnet (基线)                      | `home_flow_2604_pepnet.config`                              |
| pepnet_nocdot                      | `home_flow_2604_pepnet_nocdot.config`                       |
| pepnet_cdot_domain                 | `home_flow_2604_pepnet_cdot_domain.config`                  |
| 🏆 pepnet_cdot_domain_dcnv2 (最优) | `home_flow_2604_pepnet_cdot_domain_dcnv2_warmup1000.config` |
| pepnet_epoch3                      | `home_flow_2604_pepnet_epoch3.config`                       |
| pepnet_tower256                    | `home_flow_2604_pepnet_tower256.config`                     |
