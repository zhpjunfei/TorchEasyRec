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

## 第三阶段：结构补全

| #   | Config             | 变化                          | CTR AUC | CVR AUC | 说明                                            |
| --- | ------------------ | ----------------------------- | :-----: | :-----: | ----------------------------------------------- |
| 14  | relation_mlp       | CVR 加 relation_mlp           |  0.694  |  0.741  | −0.1pp，持平 baseline                           |
| 15  | relation_mlp_noadd | relation_mlp + 关 cvr_add_ctr |  0.694  |  0.736  | +0.5pp vs nocdot_noadd，relation_mlp 有独立作用 |
| 16  | domain2            | domain + page + KV            |  0.693  |  0.741  | −0.1pp，domain 特征扩展无效                     |

## 第四阶段：数据扩展

| #   | Config                     | 变化                                               | CTR AUC | CVR AUC | 说明                                                |
| --- | -------------------------- | -------------------------------------------------- | :-----: | :-----: | --------------------------------------------------- |
| 17  | freqpage16                 | f_req_page emb=16 + 全page数据                     |  0.696  |  0.739  | ❌ CTR +0.2pp 但 CVR -0.3pp，不可接受               |
| 18  | cdot32                     | freqpage16 + f_req_page emb=32 + cdot input_dim=32 |  0.696  |  0.740  | ❌ 比 freqpage16 CVR +0.1pp，但仍差 baseline -0.2pp |
| 19  | nofreqpage                 | 去掉 f_req_page（只用原始数据）                    |  0.693  |  0.741  | ➖ ±0pp，f_req_page 删掉无影响                      |
| 20  | cdot32_weight03            | cdot32 + 搜索样本降权 0.3                          |  0.696  |  0.742  | ✅ CTR +0.2pp, CVR ±0pp，大幅优于 freqpage16        |
| 21  | cdot32_weight03_nofreqpage | weight03 + 去掉 f_req_page                         |    —    |    —    | 🔄 运行中                                           |

### v1c 基线

| 模型                        |  CTR AUC   |  CVR AUC   |
| --------------------------- | :--------: | :--------: |
| v1c (DBMtl_DCNv2) 线上      | **0.690**  | **0.768**  |
| PEPNet_v2 (warmup1000) 最佳 |   0.694    |   0.742    |
| 差距                        | **+0.4pp** | **-2.6pp** |

## 第五阶段：瓶颈诊断

| #   | Config   | 基干            | 变化                      |  CTR AUC  |  CVR AUC  | 说明                    |
| --- | -------- | --------------- | ------------------------- | :-------: | :-------: | ----------------------- |
| 22  | v1ctower | cdot32_weight03 | tower → [128,64,32]       | **0.695** | **0.742** | ❌ 排除 tower 过参数化  |
| 23  | 2epochs  | cdot32_weight03 | num_epochs=2, T_max=12655 |  过拟合   |  过拟合   | ❌ 第2个 epoch AUC 下降 |

## 关键结论

1. **DCNv2 有效** — cross_num=4, low_rank=256，CDOT domain + DCNv2 比纯 nocdot 高 +0.7pp CTR, +0.4pp CVR
1. **CDOT all 无用，CDOT domain 有用** — domain group 信号干净，CDOT 能学到东西
1. **cvr_add_ctr_logits 必开** — 关闭掉 0.5pp CVR
1. **relation_mlp 有独立作用（+0.5pp），但与 cvr_add_ctr 冗余** — 单独开 +0.5pp，叠加后 0pp
1. **Domain 特征扩展无效** — 加 page + KV 特征、加 f_req_page 均无变化
1. **f_req_page 无用** — 去掉后 CTR/CVR 均不变（0.693/0.741），CDOT domain 只用 mmb_id + item_id 即可
1. **搜索样本降权 0.3 有效** — 全量搜索数据导致 CVR -0.3pp，降权到 0.3 后 CVR 恢复（0.742），CTR 仍 +0.2pp。embedding 受益 + tower 保护 = 双赢
1. **1 epoch 最优** — 3 epoch 过拟合严重 (CTR 0.658, CVR 0.704)
1. **warmup 有效** — 500→1000 带来 +0.2pp
1. **超参数已接近天花板** — 第二阶段所有微调效果 ±0.1pp 以内震荡
1. **v1c CVR 0.768 有 2.6pp 差距** — tower 过参数化 ❌、训练步数不足 ❌ 均已排除
1. **训练样本仅按天 GROUP BY (mmb_id, item_id)** — 无跨天去重。click_cnt>0 时序过滤只保留点击商品"附近"的负样本
1. **核心假设：共享 bottom MLP vs MoE** — v1c 的 DBMtl 共享 4 层 MLP `[512,256,128,64]` 比 PEPNet_v2 的 EPNet 门控+专家更适合当前数据

## 综合最优配置

```
CDOT:       domain (mmb_id, item_id)
DCNv2:      cross_num=4, low_rank=256
Bias:       domain
LHUC:       domain
cvr_add_ctr: true
Tower:      [512, 256, 128], PPNet gamma=2.0
Warmup:     cosine warmup 1000
LR:         0.001
Weight decay: 0.01 (仅 MLP.weight + cdot.sub_compress_weight)
搜索降权:    CVR 塔 sample_weight_name=search_weight, search_price=0.3
```

最佳 AUC: **CTR 0.694 / CVR 0.742**（搜索数据降权版 CTR 0.696 / CVR 0.742，可作为上线候选）

## 下一步方向

| 方向                                                     |   结果    |    状态     |
| -------------------------------------------------------- | :-------: | :---------: |
| ~~relation_mlp~~ — CVR 加 CTR hidden MLP                 | 0pp 冗余  |   ❌ 放弃   |
| ~~domain2~~ — CDOT domain 加 page + KV                   | 0pp 无效  |   ❌ 放弃   |
| ~~freqpage16~~ — 全 page 数据 + f_req_page 升维          |  -0.3pp   |   ❌ 放弃   |
| **cdot32_weight03** — 搜索降权 0.3，CTR +0.2pp, CVR ±0pp | ✅ 正收益 | ✅ 上线候选 |
| ~~f_req_page~~ — 该特征无贡献                            |    0pp    |   ❌ 可删   |
| v1c 结构 diff — 找真正的差距                             |   未知    |  🔄 待验证  |
| ~~v1ctower~~ — tower [128,64,32]                         | 0.742 ❌  |   ✅ 排除   |
| ~~2epochs~~ — 更多训练步数                               | 过拟合 ❌ |   ✅ 排除   |
| 共享 bottom MLP — 对齐 v1c 架构                          |   未知    |  🔄 待实验  |

## 最终结论

经过 21 组实验，PEPNet_v2 在 warmup1000 + cvr_add_ctr 下达到最优：**CTR 0.694 / CVR 0.742**。

搜索数据降权 0.3（cdot32_weight03）可作为候选上线：CTR +0.2pp 且 CVR 不降，净正收益。其他所有结构差异（relation_mlp、CDOT 特征扩展、数据扩展）均已验证完毕。

v1c 基线 CVR **0.768** 高出 **2.6pp**。

v5 阶段两个瓶颈假设均被排除：

- v1ctower：tower [512,256,128] → [128,64,32] → CTR 0.695 / CVR 0.742，**无变化** → ❌ tower 非瓶颈
- 2epochs：第 2 个 epoch AUC 开始下降 → **过拟合** → ❌ 训练步数非瓶颈

**差距是架构性的**。核心假设指向 v1c 的**共享 bottom MLP**（DBMTL `[512,256,128,64]`）可能比 PEPNet_v2 的 EPNet MoE 更适合当前数据规模。

## Config 文件

| Config                               | 路径                                                |
| ------------------------------------ | --------------------------------------------------- |
| pepnet (基线)                        | `home_flow_2604_pepnet.config`                      |
| pepnet_nocdot                        | `home_flow_2604_pepnet_nocdot.config`               |
| pepnet_cdot_domain                   | `home_flow_2604_pepnet_cdot_domain.config`          |
| 🏆 warmup1000 (最优 AUC)             | `v2/..._warmup1000.config`                          |
| ⭐ cdot32_weight03 (上线候选)        | `v4/..._cdot32_weight03.config`                     |
| pepnet_epoch3                        | `home_flow_2604_pepnet_epoch3.config`               |
| pepnet_tower256                      | `home_flow_2604_pepnet_tower256.config`             |
| pepnet_relation_mlp                  | `v3/..._relation_mlp.config`                        |
| pepnet_relation_mlp_noadd            | `v3/..._relation_mlp_noadd.config`                  |
| pepnet_domain2                       | `v3/..._domain2.config`                             |
| pepnet_v4_freqpage16                 | `v4/..._freqpage16.config`                          |
| pepnet_v4_cdot32                     | `v4/..._cdot32.config`                              |
| pepnet_v4_cdot32_weight03            | `v4/..._cdot32_weight03.config`                     |
| pepnet_v4_cdot32_weight03_nofreqpage | `v4/..._cdot32_weight03_nofreqpage.config` 🔄       |
| pepnet_nofreqpage                    | `home_flow_2604_pepnet_nofreqpage.config`           |
| v5_v1ctower                          | `v5/..._v5_v1ctower.config` — CTR 0.695 / CVR 0.742 |
| v5_2epochs                           | `v5/..._v5_2epochs.config` 🔄                       |
| v5_baseline                          | `v5/..._v5_baseline.config`                         |
