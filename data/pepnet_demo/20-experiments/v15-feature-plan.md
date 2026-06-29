______________________________________________________________________

## date: 2026-06-28 tags: [experiment, v15, feature, plan] status: draft related: \["\[[v14-experiments]\]", "\[[v14-optimization-plan]\]"\]

# v15 特征工程实施计划（PLE 证伪后转向）

______________________________________________________________________

## 一、已证伪的方向汇总

| 方向                           | 证据                                | 结论 |
| :----------------------------- | :---------------------------------- | :--: |
| CVR tower MLP 扩宽 [512→1024]  | ots012_wide −0.18pp                 |  ❌  |
| PLE expert 容量翻 4x           | ots012_plebig −0.04pp（噪声）       |  ❌  |
| dropout 调参（ots≥0.12）       | +0.08pp（噪声）                     |  ❌  |
| weight decay / adamw           | 等同基线                            |  ❌  |
| ctcvr / ESMM                   | +0.29pp, CTR −0.07pp                |  ❌  |
| 梯度隔离 / 手术 / 自适应加权   | 全部负或中性                        |  ❌  |
| Contrastive Phase 1a / Phase 2 | v11 实测 CTR −0.00024, CVR −0.00010 |  ❌  |
| label_smoothing                | −0.74% 无法补偿 dropout 缺失        |  ❌  |

**核心结论：当前架构+特征所有可调 lever 已穷尽。瓶颈在特征质量，不在模型容量。**

______________________________________________________________________

## 二、剩余方向的完整评估

### A. 实时特征增强 ⭐ 最推荐

#### 现状

已有 rt1h/3h/12h/24h 的 item 级 count 特征（click/conversion/favorite），以及用户侧 KV 实时特征。

#### 子方向 A1：短窗口实时特征（rt5m/rt15m/rt30m）

**问题**：1h 窗口太宽。对于热门 item，1h 内的点击量已饱和，区分度低。
**解法**：新增 rt5m（300s）/ rt15m（900s）/ rt30m（1800s）窗口。

**链路**：

```
修改 Flink SQL → 写入 FeatureStore → ODPS 训练数据 LEFT JOIN → Config 新增 raw_feature → 训练
```

**文件改动**：

| 文件                                                                                     | 改动内容                                                          |     行数     |
| :--------------------------------------------------------------------------------------- | :---------------------------------------------------------------- | :----------: |
| `data/pepnet_demo/sql/sample_v3/home_flow_2604_statistic_real_time_feature_to_fs_v1.sql` | `ARRAY[3600,10800,43200,86400]` 中加入 `300,900,1800`；新增输出列 |      ~5      |
| FeatureStore 表                                                                          | item 级 rt 表新增 9 列（3 种行为 × 3 种窗口），user 级 KV 表同理  |      —       |
| `home_flow_2604_ctrcvr_sorter_fix_sample_v3.sql`                                         | CREATE TABLE 新增列 + LEFT JOIN 新增列                            |     ~30      |
| 训练 config                                                                              | 新增 `raw_feature { feature_name: "item__cnt_click_rt5m" ... }`   | ~15/每个特征 |
| 训练数据                                                                                 | ODPS INSERT OVERWRITE                                             |     1-2h     |

**算力**：不影响模型训练速度（纯新增特征列）
**预期增益**：低（短窗口和已有 rt1h 高度相关） — 0.1~0.3pp

#### 子方向 A2：实时 ratio 特征 ⭐ 高价值

**问题**：`item__cnt_click_rt1h` 是 raw count，受 item 基础曝光量影响大（热门 item 天然高）。需要 normalized 度量。

**解法**：新增 `item__click_rate_rt1h = item__cnt_click_rt1h / item__cnt_exposure_rt1h`。需要基础表有曝光计数（目前 Flink SQL 没有计算曝光）。

**链路同 A1**，但需要基础设施改动。

**预期增益**：中高（0.5~1.0pp）— 因实时 ratio 和离线 15d ratio 信息不同（实时捕捉突发热度）

#### 子方向 A3：用户侧实时统计

**现状**：已有 `user__kv_*_*_rt` KV 特征，但缺少**非 KV** 的用户级实时特征（如 `user__cnt_click_rt1h`）。

**解法**：Flink SQL 新增用户级非 KV count 特征。

**预期增益**：中（0.3~0.5pp）

______________________________________________________________________

### B. Sequence Encoder 升级

#### 现状

8 个序列全部使用 DIN（target attention with MLP）。代码库已有 `TransformerEncoder`。

#### 改动内容

**纯 config 改动** — 将 `click_50_seq` 的 encoder 从：

```protobuf
sequence_encoders {
  din_encoder {
    input: "click_50_seq"
    attn_mlp { hidden_units: 128 hidden_units: 64 activation: "Dice" }
  }
}
```

改为：

```protobuf
sequence_encoders {
  transformer_encoder {
    input: "click_50_seq"
    transformer_hidden: 64
    num_heads: 4
    num_layers: 1
    dropout: 0.0
    max_seq_length: 50
  }
}
```

**文件改动**：

| 文件        | 改动                                         |
| :---------- | :------------------------------------------- |
| 训练 config | 替换 1 个 sequence_encoder block（~8 lines） |
| proto       | 无需（已有 TransformerEncoder）              |
| model code  | 无需（embedding_group 自动处理）             |

**关键差异** — TransformerEncoder vs DINEncoder：

- DIN: target attention → weighted sum → [B, seq_dim]
- Transformer: target concat → Linear → TransformerEncoder → score → weighted sum → [B, seq_dim]
- 输出维度相同（`seq_dim`），gating 自然处理

**风险**：

- O(n²) attention → batch_size 4096 × seq_len 50 = 204,800 attention pairs per head
- 每 batch 额外计算量：50 × 50 × 4 heads = 10K attention scores vs DIN 的 50 × 128 × 64 = 409K
- 实际 Transformer 可能更快（DIN 的 attn_mlp 有 128×64=8K 参数，Transformer 的 proj_in = 4×seq_dim×64 更大但向量化更好）
- **OOM 风险低** — 50 序列远低于 Transformer 典型瓶颈

**预期增益**：0.3~0.8pp（DIN 已强，Transformer 优势在于捕捉 item 间关联）

______________________________________________________________________

### C. CDOT 容量升级（新提议）

**现状**：CDOT input_dim=32, output_dim=4, mid_dim=32, compress_hidden=[512,374]
**想法**：CDOT 是 feature interaction compress 模块，将 domain group 特征压缩到 4 维。增大 output_dim（4→8→16）可保留更多交叉信息。

**改动**：config 中修改 `cdot { output_dim: 8 }`

**预期增益**：未知（0.2~0.5pp）

______________________________________________________________________

### D. DCNv2 cross_num 增加

**现状**：cross_num=4, low_rank=256
**想法**：增加 cross_num 到 6~8，允许更多特征交叉层

**改动**：config 中修改 `dcnv2 { cross_num: 6 }`

**预期增益**：未知（0.1~0.3pp）

______________________________________________________________________

## 三、推荐实施顺序

### Round 1（0 代码，仅改 config，1-2 天出结果）

| 序号 | 实验                | 配置更改                               |   预期    |
| :--: | :------------------ | :------------------------------------- | :-------: |
|  1   | **seq_transformer** | click_50_seq: DIN → TransformerEncoder | 0.3~0.8pp |
|  2   | **cdot_out8**       | CDOT output_dim: 4→8                   | 0.2~0.5pp |
|  3   | **dcnv2_cross6**    | DCNv2 cross_num: 4→6                   | 0.1~0.3pp |

可以**并行提交**（互不冲突，可同时跑）。

### Round 2（数据 pipeline 改动，5-7 天出结果）

| 序号 | 实验                           | 链路                                     |
| :--: | :----------------------------- | :--------------------------------------- |
|  4   | **实时短窗口** (rt5m/rt15m)    | Flink SQL → FeatureStore → ODPS → Config |
|  5   | **实时 ratio** (click_rate_rt) | Flink SQL 新增曝光计数 → ratio 特征      |

### 决策逻辑

```
Round 1 结果（1-2天）:
│
├── seq_transformer ≥ +0.5pp → 主攻 sequence 方向
│   ├── 增加 num_layers 1→2
│   ├── 扩展到 other 序列（like_50_seq, chaprice_50_seq）
│   └── 增大 transformer_hidden 64→128
│
├── cdot_out8 ≥ +0.3pp → CDOT capacity 值得调优
│   ├── 测试 output_dim 8→16
│   └── 测试 compress_hidden 放大
│
├── dcnv2_cross6 ≥ +0.2pp → 更多交叉层有效
│
└── 全部 < +0.2pp → 确认模型容量极限，启动 Round 2 数据驱动
    └── 实时特征 = 最后一搏
```

______________________________________________________________________

## 四、时间线

```
Day 1-2:  Round 1 — 3 个 config-only 实验并行提交
Day 3:    Round 1 结果评估
Day 3-4:  Round 1.5 — 有效方向深化（如 seq_transformer num_layers=2）
Day 5:    决策：启动 Round 2（实时特征）or 宣布完结
Day 5-10: Round 2 — Flink SQL + 数据 pipeline (如果启动)
Day 11:   最终模型 = ots=0.12 + 有效增益
```
