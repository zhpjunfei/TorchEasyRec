______________________________________________________________________

## date: 2026-06-28 tags: [experiment, v14, v15, roadmap] status: updated related: \["\[[v14-experiments]\]"\]

# v15 优化路线图（ots 扫完后的新方向）

> ⭐ Codex 深度审查版见 \[[v14-optimization-plan-codex]\] — 以 UV CTR + UV CVR 为核心目标的全新路线图。
> ots 全扫（21 点 0.005→0.50）GAUC_cvr 从 0.6957 → 0.7413，所有超参 lever 已穷尽。转向架构升级。
> seq_transformer 方案已完成代码实现（2026-06-29），详见下文 §六。

______________________________________________________________________

## 一、已完成（v14，2026-06-28 完结）

### ots 全扫描

| 实验数 |    范围    |      GAUC_cvr 提升      |  状态   |
| :----: | :--------: | :---------------------: | :-----: |
|   21   | 0.005→0.50 | **+4.56pp**（严格单调） | ✅ 完结 |

### 已证否的方向

| 方向                     | 证据                                           | 结论                         |
| :----------------------- | :--------------------------------------------- | :--------------------------- |
| dropout 调参             | ots≥0.12 时 dropout 0.1→0.3 仅 +0.08pp（噪声） | ❌ ots 替代品，高 ots 下冗余 |
| CVR tower 扩宽           | wide −0.18pp, wide+dropout −0.10pp             | ❌ 瓶颈不在 tower MLP        |
| dense weight decay       | adamw 等同基线                                 | ❌ 零效果                    |
| cvr tower wd             | Config D 等同 A                                | ❌ 零效果                    |
| ctcvr/ESMM               | +0.29pp GAUC_cvr, −0.07pp CTR                  | ❌ 中性偏负                  |
| 梯度隔离/手术/自适应加权 | 全部负或中性                                   | ❌                           |

### 基线状态

| 指标     |   ots=0.50（极致）   |   ots=0.12（推荐）   | ots=0.01（v12 baseline） |
| :------- | :------------------: | :------------------: | :----------------------: |
| GAUC_cvr | **0.7413 (+4.56pp)** | **0.7245 (+2.88pp)** |          0.6957          |
| GAUC_ctr |   0.7040 (−0.04pp)   |   0.7043 (−0.01pp)   |          0.7044          |
| BCE_cvr  |   0.384（过置信）    |    0.470（健康）     |          0.494           |
| gap_cvr  |        4.51pp        |        4.75pp        |          5.25pp          |

______________________________________________________________________

## 二、核心认知（28+ 实验的教训）

### 2.1 什么有效、什么无效

| 状态      | 方向                                         |   证据强度   | 机制                                          |
| :-------- | :------------------------------------------- | :----------: | :-------------------------------------------- |
| ✅✅ 最强 | out_task_space_weight 单调增益 0.005→0.50    |  ⭐⭐⭐⭐⭐  | 非点击梯度从 0%→90.5%，CVR 塔获得全量数据训练 |
| ✅ 有效   | PLE extraction network 容量                  | ❓（实验中） | 共享表征质量决定两 tower 上限                 |
| ❌ 已证伪 | CVR tower MLP 宽度                           |    ⭐⭐⭐    | [512,256,128] 已够，1024→无效                 |
| ❌ 已证伪 | dropout 调参（ots≥0.12）                     |     ⭐⭐     | ots 自身提供正则，dropout 冗余                |
| ❌ 已证伪 | weight decay / ctcvr / 梯度干预 / 自适应加权 |    ⭐⭐⭐    | 多重独立证伪                                  |

### 2.2 未探索的杠杆（按确定性排序）

| 杠杆                      | 预期增益  |          成本          |      风险      |
| :------------------------ | :-------: | :--------------------: | :------------: |
| PLE expert 容量（进行中） |   1~2pp   |    低（改 config）     |       低       |
| Contrastive Phase 2       | 0.1~0.3pp |   极低（改 config）    |      极低      |
| 实时特征（短窗口/ratio）  | 0.5~1.5pp | 高（Flink SQL + 数据） |       中       |
| Sequence encoder 升级     | 0.3~0.8pp |  中（改 proto+model）  | 中（OOM 风险） |
| Embedding 维度/容量       |   未知    |    低（改 config）     |       中       |
| PLE expert count vs width |   未知    |    低（改 config）     |       低       |

______________________________________________________________________

## 三、v15 实验路线图

### Round 1（当前 — config-only，可并行）

| 序号 | 实验                   | 内容                                      | 目的                               | 优先级 |
| :--: | :--------------------- | :---------------------------------------- | :--------------------------------- | :----: |
|  1   | **seq_transformer** 🏃 | click_50_seq: 完全重写 TransformerEncoder | 升级 sequence 建模，详细设计见 §六 | **P0** |
|  2   | **cdot_out8**          | CDOT output_dim: 4→8                      | 保留更多交叉信息                   |   P1   |
|  3   | **dcnv2_cross6**       | DCNv2 cross_num: 4→6                      | 更多特征交叉层                     |   P2   |

### Round 2（数据 pipeline 改动）

| 序号 | 实验            | 内容                                                  | 优先级 |
| :--: | :-------------- | :---------------------------------------------------- | :----: |
|  4   | 实时短窗口特征  | rt5m/rt15m — Flink SQL → FeatureStore → ODPS → Config |   P0   |
|  5   | 实时 ratio 特征 | click_rate_rt — Flink SQL 新增曝光计数                |   P0   |
|  6   | 用户侧实时统计  | user\_\_cnt_click_rt1h 等                             |   P1   |

### Phase 3（部署与最终调优）

| 序号 | 实验                 | 内容                                     | 目的                      | 优先级 |
| :--: | :------------------- | :--------------------------------------- | :------------------------ | :----: |
|  12  | 最优 config 重复验证 | ots=0.12/0.15 + Round 1/2 增益           | 确认可复现                |   P0   |
|  13  | 在线融合 β 调优      | fusion_score = CTR × CVR^β               | 线上 CTR vs CVR trade-off |   P0   |
|  14  | gap_cvr 监控         | 离线 GAUC vs 在线 UV GAUC 差距           | 验证离线评估有效性        |   P0   |
|  15  | BCE_cvr 校准         | 如 \<0.420 需校准（temperature scaling） | 防止过置信                |   P1   |

______________________________________________________________________

## 四、决策树

```
Round 1（config-only，1-2天）
│
├── seq_transformer ≥ +0.5pp → 主攻 sequence 方向
│   ├── num_layers 1→2
│   ├── 扩展 to like_50_seq, chaprice_50_seq
│   └── transformer_hidden 64→128
│
├── cdot_out8 ≥ +0.3pp → CDOT capacity 调优
│   ├── output_dim 8→16
│   └── compress_hidden 放大
│
├── dcnv2_cross6 ≥ +0.2pp → 更多交叉层有效
│
└── 全部 < +0.2pp → 确认模型容量极限，启动 Round 2 数据驱动
    └── 实时特征 = 最后一搏
```

______________________________________________________________________

## 五、实验提交顺序（当前）

```
Round 1 (当前): ots012_seq_transformer 🏃（代码+config 已就绪）
Round 2:        cdot_out8, dcnv2_cross6 (config-only, 可并行)
Round 3:        根据 Round 1/2 结果决定
```

______________________________________________________________________

## 六、seq_transformer 完整方案

### 6.1 动机

原有 TransformerEncoder 有 4 个架构问题：

| #   | 问题                                                                                     | 严重程度 |
| :-- | :--------------------------------------------------------------------------------------- | :------: |
| 1   | **Target leakage**: `[q, s, q-s, q×s]` 864 维 concat 作为 proj_in 输入，q 注入所有 token | 🔴 致命  |
| 2   | **Score-value 空间不匹配**: `score=Linear(h)` 但 `value=s`，梯度混叠噪声                 | 🔴 致命  |
| 3   | **双注意力冗余**: Transformer self-attention + DIN MLP scoring，都做 importance modeling |  🟡 中   |
| 4   | **Feature explosion**: 864→128 (6.75:1) 压缩，噪声信号通过 q-s/q×s 进入                  |  🟡 中   |

### 6.2 新架构

```
s [B,T,216] ─→ proj_in ─→ Transformer ─→ h [B,T,128]    ← 纯序列，无 target
q [B,216]   ─→ proj_in ─→ q_proj [B,128]                  ← 同 W，同空间

cross-attention:
  scores = q_proj · h^T / √128         [B,1,T]            ← 0 参数
  attended = softmax(scores) · h       [B,128]            ← target 选择

vector gate:
  gate = sigmoid(MLP([q, attended, q⊙attended]))  [B,128] ← 384→64→128
  fused = attended·gate + mean(h)·(1-gate)          [B,128] ← 逐 dim 融合
  output = LN(fused)                                 [B,128] ← 无残余
  output = proj_pooled(output)                       [B,216]
```

### 6.3 两套注意力分工

| 机制                          |                     公式 | 参数  | 角色                        |
| :---------------------------- | -----------------------: | :---: | :-------------------------- |
| Self-attention (Transformer)  | `s_i → h_i` with context | 197K  | 序列内上下文建模            |
| Cross-attention (dot-product) |         `q · h_i / √128` | **0** | target 驱动的 position 选择 |

完全正交：self-attention 做表示，cross-attention 做选择。

### 6.4 代码改动 `tzrec/modules/sequence.py`

**旧类 `TransformerEncoder` (行 419-543) → 完全重写 (行 419-573)**

| 组件            |                            改前 |                  改后                   |
| :-------------- | ------------------------------: | :-------------------------------------: |
| `proj_in` input |           `[q,s,q-s,q×s]` (864) |             `s` only (216)              |
| `proj_in`       |              `Linear(864, 128)` |           `Linear(216, 128)`            |
| proj_in 使用    |                   sequence only |        **共享**: s + q 都走此 W         |
| Transformer     |                              同 |                   同                    |
| scoring         | `Linear(h) → 1` (content-based) |  dot-product `q·h^T/√128` (**0 参数**)  |
| pooling value   |               `s` (原始空间) ❌ |            `h` (128 空间) ✅            |
| gating          |                              无 | `MLP([q,attn,q⊙attn]) → [B,128]` 向量门 |
| fusion          |                              无 |     `attended·gate + mean·(1-gate)`     |
| output          |                     直接 return |      `LN(fused).proj_pooled(→216)`      |

**关键修复**:

- 🔴 `query * seq_mean` dim mismatch bug → 统一用 `q_proj_2d` (128-dim)
- 🔴 `score from h, value from s` → value=`h`
- 🔴 target leakage → Transformer 只看到 `s`

### 6.5 Config 改动

文件: `home_flow_2604_v14_config_c_ots012_seq_transformer.config`

```protobuf
# 改动 1: click_50_seq sequence_group 加 3 个 query 特征
feature_names: "core_entity"
feature_names: "click_50_seq__core_entity"
feature_names: "first_cate_id"        # 新增 ←
feature_names: "second_cate_id"       # 新增 ←
feature_names: "third_cate_id"        # 新增 ←
feature_names: "click_50_seq__first_cate_id"
feature_names: "click_50_seq__second_cate_id"
feature_names: "click_50_seq__third_cate_id"

# 改动 2: 替换 encoder
transformer_encoder {
  input: "click_50_seq"
  transformer_hidden: 128
  num_heads: 4
  num_layers: 1
  dropout: 0.1
  max_seq_length: 50
}
```

### 6.6 参数清单

| 组件          |           公式 |        参数 |      占比 |
| :------------ | -------------: | ----------: | --------: |
| `proj_in`     |        216→128 |      27,776 |     0.07% |
| `Transformer` |  1L 4H FFN 512 |     197,632 |     0.49% |
| `gate_mlp`    |         384→64 |      24,640 |     0.06% |
| `gate_proj`   |         64→128 |       8,320 |     0.02% |
| `gate_ln`     | LayerNorm(128) |         256 |   \<0.01% |
| `proj_pooled` |        128→216 |      27,864 |     0.07% |
| **total**     |                | **286,488** | **0.72%** |

相比原 DIN encoder (~119K) 增加了 ~167K，相对 40M 全模型可忽略。

### 6.7 设计决策

| 决策                 | 选项                                       |         选择          | 理由                                  |
| :------------------- | :----------------------------------------- | :-------------------: | :------------------------------------ |
| Transformer 是否含 q | `s` / `s+q` / `s+Linear(q)`                |     **`s` only**      | 避免 target leakage，线上校准稳定     |
| proj_in 是否共享     | 共享 / 独立                                |       **共享**        | q 和 h 同空间，dot-product 语义有意义 |
| scoring 方式         | MLP / dot-product / concat                 |    **dot-product**    | 0 参数，无双注意力冗余                |
| gate 类型            | 标量 / 向量                                |   **向量 [B,128]**    | 逐 dim 独立融合，表达能力更强         |
| gate 输入            | `[q,mean,q⊙mean]` / `[q,attn,mean,q⊙attn]` | **`[q,attn,q⊙attn]`** | 不含 mean，避免和 (1-g) 路径重复注入  |
| fusion 后处理        | LN / LN+residual / 无                      |     **LN(fused)**     | 无 residual 冲刷门控信号              |
| query-seq dim 要求   | 允许不等 / 强制相等                        |     **强制相等**      | proj_in 共享要求 dim 一致             |

### 6.8 边界情况

| 场景                | 行为                                             |
| :------------------ | :----------------------------------------------- |
| 空序列 (全 padding) | h=0 → mean=0, scores 全 -inf → attn=0 → output=0 |
| 单 item             | attended=mean(h)，gate 不影响                    |
| gate 全 1           | fused=attended → LN(attended) → proj_pooled      |
| gate 全 0           | fused=mean(h) → LN(mean) → proj_pooled           |
| 所有 item 等权重    | scores 均匀 → attended=mean(h) → 同单 item       |

### 6.9 与原有 TransformerEncoder 对比

| 维度             |           原版            |          新版           |
| :--------------- | :-----------------------: | :---------------------: |
| Target leakage   |    ❌ q 注入所有 token    |        ✅ 纯序列        |
| proj_in 输入 dim |            864            |           216           |
| Score 方式       | `Linear(h)` content-based | `q·h/√128` target-aware |
| Value            |        `s` (原始)         | `h` (transformer 输出)  |
| 评分参数         |            217            |          **0**          |
| 门控融合         |            无             |     向量门 [B,128]      |
| 输出归一化       |            无             |        LN(fused)        |
| 代码行数         |          ~125 行          |         ~155 行         |
| 参数量           |           ~336K           |          ~286K          |
