______________________________________________________________________

## date: 2026-06-11 tags: [experiment, v10, title-vector, world-knowledge] related: \["\[[v9-experiments]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v10 实验 — DIN 序列特征优化

> v10 pipeline 与 v9 一致（v1c 编码, v1 SQL 60d+30d归因）. 以 title_vector 实验结果最优的配置为基线. 实验变量：序列侧 dim alignment、weight sharing、time gate (B2)、cate alignment. 所有实验 4卡, batch_size=4096/GPU, 有效=16384. T_max=6700/warmup=1000.

## 实验清单

| 实验             | Config                                       | 变化                                       |
| :--------------- | :------------------------------------------- | :----------------------------------------- |
| baseline         | `home_flow_2604_v10_baseline.config`         | v10 基线                                   |
| seq_align        | `home_flow_2604_v10_seq_align.config`        | dim alignment + weight sharing             |
| seq_align_b2     | `home_flow_2604_v10_seq_align_b2.config`     | dim alignment + weight sharing + B2        |
| seq_align_cate   | `home_flow_2604_v10_seq_align_cate.config`   | cate alignment only                        |
| seq_align_all    | `home_flow_2604_v10_seq_align_all.config`    | dim alignment + weight sharing + cate      |
| seq_align_all_b2 | `home_flow_2604_v10_seq_align_all_b2.config` | dim alignment + weight sharing + B2 + cate |
| b2_only          | `home_flow_2604_v10_b2_only.config`          | B2 only (baseline + time_gate_dim=8)       |
| dim_lite_b2      | `home_flow_2604_v10_dim_lite_b2.config`      | dim-lite (1.96M×32) + B2, no WS/cate       |

## 各 Config 相对 Baseline 变更对比

### 1. 核心变量矩阵

| 变更维度             | baseline | seq_align | seq_align_b2 | seq_align_cate | seq_align_all | seq_align_all_b2 | b2_only | dim_lite_b2 |
| :------------------- | :------: | :-------: | :----------: | :------------: | :-----------: | :--------------: | :-----: | :---------: |
| seq item_id dim      |    24    |  **32**   |    **32**    |       24       |    **32**     |      **32**      |   24    |   **32**    |
| seq item_id bucket   |  1.96M   |  **3M**   |    **3M**    |     1.96M      |    **3M**     |      **3M**      |  1.96M  |    1.96M    |
| `embedding_name`     |    ✗     |   **✓**   |    **✓**     |       ✗        |     **✓**     |      **✓**       |    ✗    |      ✗      |
| `time_gate_dim`      |    0     |     0     |    **8**     |       0        |       0       |      **8**       |  **8**  |    **8**    |
| query cate alignment |    ✗     |     ✗     |      ✗       |     **✓**      |     **✓**     |      **✓**       |    ✗    |      ✗      |
| weight sharing       |    ✗     |     ✓     |      ✓       |       ✗        |       ✓       |        ✓         |    ✗    |      ✗      |

### 2. Query 端（target 侧）特征变更

所有 config 的 seq_groups query 端共享同一组特征列表：

**baseline / seq_align / seq_align_b2** — 16 个 query 特征:

```
item_id, cate_id_path, related_goods_ids, brand, core_entity,
price_tag, promotion_channel, publish_user, site, spu_id,
discount_intensity, dianpupingfen, pinpaidengji, dianpufensi,
item_type, username
```

**seq_align_cate / seq_align_all / seq_align_all_b2** — 19 个 query 特征（+3 cate）:

```
item_id, cate_id_path, related_goods_ids, brand, core_entity,
**first_cate_id, second_cate_id, third_cate_id**,   ← 新增
price_tag, promotion_channel, publish_user, site, spu_id,
discount_intensity, dianpupingfen, pinpaidengji, dianpufensi,
item_type, username
```

### 3. Content 端（sequence 侧）特征变更

**baseline / seq_align_cate / b2_only** — seq item_id: 24-dim, 1.96M bucket

**seq_align / seq_align_b2 / seq_align_all** — seq item_id: **32-dim, 3M bucket**（与 target 一致）

**dim_lite_b2** — seq item_id: **32-dim, 1.96M bucket**（仅扩 dim，保持 bucket）

**ts 维度差异**（content 端独有）:

| 行为类型        | ts 维度 |
| --------------- | :-----: |
| click_10/50     |    8    |
| conversion_5/20 |    8    |
| favorite_5/10   |  **4**  |

### 4. 各 Config 的 DIN Encoder 配置

**baseline / seq_align / seq_align_cate / seq_align_all**:

```protobuf
din_encoder {
    input: "click_10_seq"
    attn_mlp { hidden_units: 128 hidden_units: 64 activation: "Dice" }
}
# 其余 5 个 sequence_encoders 结构同上（input 不同）
```

**seq_align_b2 / seq_align_all_b2 / b2_only / dim_lite_b2** — 每个 DINEncoder 增加 `time_gate_dim: 8`:

```protobuf
din_encoder {
    input: "click_10_seq"
    time_gate_dim: 8    ← B2
    attn_mlp { hidden_units: 128 hidden_units: 64 activation: "Dice" }
}
```

### 5. weight sharing 配置变更

仅在 `seq_align` / `seq_align_b2` / `seq_align_all` 中生效。所有 6 个序列的 `item_id` 新增 `embedding_name`:

```protobuf
# sequence feature configs 内
id_feature {
    feature_name: "item_id"
    embedding_name: "item_id_emb"        # ← 新增，与 target 侧一致
    expression: "item:item_id"
    embedding_dim: 32
    hash_bucket_size: 3000000
}
```

### 6. 各 Config query/content 维度对比

content 端非 item_id/ts 的 18 个公共特征合计 **184** 维（cate_id_path=12 + related_goods_ids=24 + brand=16 + core_entity=16 + first_cate_id=8 + second_cate_id=8 + third_cate_id=12 + price_tag=8 + promotion_channel=4 + publish_user=8 + site=8 + spu_id=24 + discount_intensity=8 + dianpupingfen=4 + pinpaidengji=4 + dianpufensi=4 + item_type=4 + username=12）。

| Config           | Q 特征数 | Query dim | Content dim (click/conv) |    Content dim (fav)     |  F.pad   | 说明              |
| ---------------- | :------: | :-------: | :----------------------: | :----------------------: | :------: | ----------------- |
| baseline         |    16    |    188    |     24+184+**8**=216     |     24+184+**4**=212     | +28/+24  | seq item_id=24    |
| seq_align        |    16    |    188    | **32**+184+**8**=**224** | **32**+184+**4**=**220** | +36/+32  | seq item_id→32    |
| seq_align_b2     |    16    |    188    | **32**+184+**0**=**216** | **32**+184+**0**=**216** | +28/+28  | ts 提出到 gate    |
| seq_align_cate   |  **19**  |  **216**  |   24+184+**8**=**216**   |   24+184+**4**=**212**   | **0/+4** | fav q>c→Linear    |
| seq_align_all    |  **19**  |  **216**  | **32**+184+**8**=**224** | **32**+184+**4**=**220** |  +8/+4   | 完全对齐          |
| seq_align_all_b2 |  **19**  |  **216**  | **32**+184+**0**=**216** | **32**+184+**0**=**216** | **0/0**  | ✅ **零 padding** |
| b2_only          |    16    |    188    |   24+184+**0**=**208**   |   24+184+**0**=**208**   | +20/+20  | baseline + B2     |
| dim_lite_b2      |    16    |    188    | **32**+184+**0**=**216** | **32**+184+**0**=**216** | +28/+28  | 32-dim, 1.96M, B2 |

### 7. 关键维度行为分析

**baseline**: seq item_id=24 dim，比 query 的 32 dim 少 8，但 content 多了 ts=8/4 和 3 个 cate 特征（8+8+12=28），导致 content 比 query 大 24~28 dim → F.pad(0, 24~28)。

**seq_align**: seq item_id 提到 32，content 再涨 8 dim → F.pad 反而增大到 32~36。align 本身不减少 padding，而是消除向量空间不匹配。

**seq_align_b2**: ts 从 content 提出到 attention score 的乘法门控，content 统一为 216 dim（不受 ts=4/8 差异影响），F.pad=28 恒定。

**seq_align_cate**: query 加 3 个 cate 特征（+28）到 216，恰好与 click/conversion 的 content 对齐（216=216）→ 零 padding。但 favorite 的 ts=4，content=212，q>c 4 dim → 代码用 `nn.Linear(216, 212)` 投影。

**seq_align_all**: query=216，content=220~224，F.pad=4~8，大幅缩小，且不再区分 ts 类型导致的组间差异。

**seq_align_all_b2**: 全部优化同时打开。B2 将 ts 提出 content（+0），cate alignment 将 query 提到 216，dim alignment 将 content item_id 提到 32 → **q=216, c=216 完全对齐，零 padding，零投影**，所有 6 个 group 行为一致。

### 8. DMP 兼容说明（weight sharing）

weight sharing 通过 `seq_emb.weight = bag_weight` 别名实现。DMP 下会各自创建独立 shard（同初始化不同梯度），参见 [`§12e`](../30-data/sample-v3-pipeline.md#12e-dmp-distributed-model-parallel-%E5%85%BC%E5%AE%B9%E6%80%A7)。

## 背景

v9 实验确认了 PLE 结构、title_vector 等改进。v10 聚焦 DIN 序列特征的维度对齐与交互优化：

- **dim alignment**: seq item_id 从 24→32 维，消除 DIN 中 query/content 维度不匹配导致的 F.pad
- **weight sharing**: bag 和 seq 的 item_id 共用同一份 embedding 表，统一向量空间
- **B2 time gate**: 从加法时间门控改为乘法（score × Sigmoid），ts 从 content 提出到 gate
- **cate alignment**: target 侧 first/second/third_cate_id 加入 seq_groups query 端，丰富 attention 信号
- **seq_align_all_b2**: 同时开启以上四项优化，达到 **q=216=c，零 padding**
- **b2_only**: baseline + B2，无 alignment/WS，检验 B2 的独立效应
- **dim_lite_b2**: seq item_id 从 24→32-dim（保留 1.96M bucket，无 WS）+ B2，隔离 bucket 扩大的影响

## 实验结果

所有实验相同条件：4卡, batch_size=4096/GPU, 有效=16384, T_max=6700/warmup=1000. 取 Epoch-0 model-6371 的 Eval Result.

### 逐 Config 分析

| #   | Config               | 变更内容                            |   CTR AUC    |          ΔCTR           |   CVR AUC    |        ΔCVR         | 分析                                                                                                                                        |
| :-- | :------------------- | :---------------------------------- | :----------: | :---------------------: | :----------: | :-----------------: | :------------------------------------------------------------------------------------------------------------------------------------------ |
| 0   | **baseline**         | v10 基线                            |   0.700680   |            —            | **0.748797** |          —          | 参考点                                                                                                                                      |
| 1   | **b2_only**          | +B2 (time_gate_dim=8)               |   0.699702   |   -0.000978 (-0.140%)   |   0.748857   | +0.000060 (+0.008%) | B2 在 24-dim 上几乎无效。CTR 掉最多(-0.14%)，说明 B2 的乘法门控在低维空间中干扰了 attention 又无足够容量补偿                                |
| 2   | **dim_lite_b2**      | 24→32-dim, 1.96M bucket, +B2, 无 WS |   0.700097   |   -0.000583 (-0.083%)   |   0.747176   | -0.001621 (-0.216%) | 纯 dim 扩展（24→32）引入 8×1.96M=15.7M 参数，过拟合偏倚噪声。但相比全量 dim+WS 损失小得多，说明 bucket 扩大和 WS 才是更大的负向源           |
| 3   | **seq_align**        | 24→32-dim, 1.96M→3M bucket, +WS     |   0.700439   |   -0.000241 (-0.034%)   |   0.744630   | -0.004167 (-0.556%) | **CVR 损失最大**。三重变化(32-dim + 3M + WS)叠加产生最大过拟合。CTR 仅 -0.034% 说明 CTR 对参数不敏感                                        |
| 4   | **seq_align_b2**     | #3 + B2                             |   0.700022   |   -0.000658 (-0.094%)   |   0.745952   | -0.002845 (-0.380%) | 相对 #3 CVR 回升 +0.177%，B2 在 32-dim 上有效发挥了时间门控。但 CTR 继续下降(-0.094%)                                                       |
| 5   | **seq_align_cate**   | query 侧 +3 cate 特征               |   0.700604   |   -0.000076 (-0.011%)   | **0.747082** | -0.001715 (-0.229%) | **CVR 损失最小**。cate 特征不增加 embedding 参数量，过拟合风险最低。CTR 几乎持平                                                            |
| 6   | **seq_align_all**    | #3 + cate                           | **0.700822** | **+0.000142 (+0.020%)** |   0.745021   | -0.003776 (-0.504%) | **唯一 CTR 正增长**。cate 在 dim+WS 上产生了正向交互：query 216-dim 为 cate 特征提供了表达空间，attention 分布优化。但 CVR 仍被 dim+WS 拖累 |
| 7   | **seq_align_all_b2** | #6 + B2                             |   0.700325   |   -0.000355 (-0.051%)   |   0.746330   | -0.002467 (-0.329%) | B2 在 32-dim 上再挽回 +0.175% CVR。所有优化同时开启，q=c=216 零 padding，但净损失仍 -0.33%                                                  |

### 关键发现

1. **无实验 CVR 超过 baseline** — 所有改动都对 CVR 有负向影响
1. **CVR 损失排名**：seq_align(-0.556%) > seq_align_all(-0.504%) > seq_align_b2(-0.380%) > seq_align_all_b2(-0.329%) > seq_align_cate(-0.229%) > dim_lite_b2(-0.216%) > b2_only(+0.008%)
1. **CTR 唯一正增长**：seq_align_all (+0.020%) — cate × dim 交互

### 因素隔离

#### CVR 损失拆分

| 因素            | 计算方式                                          |    ΔCVR     | 解释                                      |
| :-------------- | :------------------------------------------------ | :---------: | :---------------------------------------- |
| 纯 dim 24→32    | dim_lite_b2 − b2_only（双方 B2 抵消）             | **-0.224%** | 8×1.96M=15.7M 新增参数 → 过拟合           |
| bucket 1.96M→3M | seq_align_b2 − dim_lite_b2（双方 B2+32-dim 抵消） | **-0.167%** | 3M 比 1.96M 稀疏 53%，冷启特征学习减弱    |
| weight sharing  | seq_align − seq_align_b2 + B2 效应                | **-0.165%** | seq 梯度干扰 bag 表征                     |
| ━━━━━━━━        | ━━━━━━━━━━━━━━━                                   |   ━━━━━━━   | ━━━━━━━━━━━━                              |
| dim+WS 合计     | seq_align − baseline                              | **-0.556%** | ✅ 三项累加 = -0.224-0.167-0.165 ≈ -0.556 |

> 注意：bucket 和 WS 的拆分基于 seq_align_b2 和 dim_lite_b2 的间接比较，精度受 B2 效应一致性影响。

#### B2 效应（依赖 dim 扩展）

| 上下文                                             |  ΔCTR   |    ΔCVR     | 解读                    |
| :------------------------------------------------- | :-----: | :---------: | :---------------------- |
| **24-dim** (b2_only − baseline)                    | -0.140% |   +0.008%   | B2 在低维空间几乎无效   |
| **32-dim** (seq_align_b2 − seq_align)              | -0.060% | **+0.177%** | B2 在 32-dim 上稳定发挥 |
| **32-dim+cate** (seq_align_all_b2 − seq_align_all) | -0.071% | **+0.175%** | B2 × dim 交互稳定可复现 |

> **B2 需要 dim 扩展才能生效**：24-dim 上 +0.008%，32-dim 上一致 +0.175%。说明乘法时间门控需要更大的 embedding 空间才能有意义地调整 attention 分布。

#### cate alignment 效应（依赖 dim+WS 上下文）

| 上下文                                       |  ΔCTR   |  ΔCVR   |        解读        |
| :------------------------------------------- | :-----: | :-----: | :----------------: |
| **单独** (seq_align_cate − baseline)         | -0.011% | -0.229% | 单独加 cate 双方负 |
| **在 dim+WS 上** (seq_align_all − seq_align) | +0.055% | +0.052% |      正向交互      |

> query 188→216 为 cate 特征提供了表达空间，dim alignment 扩大了 query 维度，cate 特征在其中优化了 attention 分布。但单独加 cate（query 从 188→216）时，cate 信号过强，压制了 price_tag、brand 等细粒度匹配信号（shadowing）。

### 完整结论

1. **CVR 损失三分**：

   - 纯 dim 扩展 (24→32, 1.96M) → **-0.22%**
   - bucket 扩大 (1.96M→3M) → **-0.17%**
   - weight sharing → **-0.17%**
   - 三项几乎均分，非之前认为的 dim 扩展绝对主因

1. **B2 需要 dim 扩展**：24-dim 上 +0.008%，32-dim 上一致 +0.175%。B2 不是独立增益，是 **dim 扩展的互补**。时间门控在更大的 embedding 空间中才能发挥价值。

1. **最优组合 = dim_lite (32-dim, 1.96M, 无 WS) + B2** → **-0.216% CVR**，是所有实验中最接近 baseline 的配置。如果还能配合 sample_weight 纠正选择偏差，有望追上甚至超过 baseline。

1. 后续实验迁移至 v7 baseline + sample_weight + is_control feature，见 [`v7-control-weight.md`](./v7-control-weight.md)。

### 选择偏差角度重新解读

精排只控制 **5% 流量**（随机均匀抽样），95% 由另一模型控制。

| 流量        | 占比 | label 来源                 | label 质量          |
| :---------- | :--: | :------------------------- | :------------------ |
| Control     |  5%  | **本模型** 曝光 → 用户反馈 | ✅ 因果完整，无偏   |
| Non-control | 95%  | 另一模型曝光 → 用户反馈    | ⚠️ 存在**选择偏差** |

Non-control 的 CVR 正样本被另一模型选品偏好系统性放大。因此**所有 v10 实验的 CVR 下降**可能不是因为改动本身不好，而是因为增加的参数在 95% 偏差数据上学会了记忆偏差模式而非真实因果。

正在 v7 上通过 sample_weight (IPW) 验证此假设，见 [`v7-control-weight.md`](./v7-control-weight.md)。
