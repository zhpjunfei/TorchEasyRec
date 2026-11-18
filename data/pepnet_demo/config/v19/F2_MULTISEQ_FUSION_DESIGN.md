# F2 设计文档：多序列统一解码模块（HyFormer §2.5 借鉴）

- 日期：2026-10-31
- 状态：设计稿（未写代码，未动任何既有 config）
- 父级决策：`ADVERSARIAL_REVIEW_20261029.md` + HyFormer 借鉴可行性判定（2026-10-30 会话）
- 对照臂：`home_flow_2608_v19_multiscene_v6f_kv_fusion.config`
- 单变量纪律：本模块落成后为独立臂 `v6f_multiseq_fusion`，与 F1（`v6f_seqattn_search`）**不合并**，各自独立消融

______________________________________________________________________

## 一、动机（对口的结构性短板）

【原始证据】`tzrec/models/pepnet_dcn_ple.py` predict()（L773-832）：6 条序列组（click_10 / click_50 / conversion_20 / favorite_10 / chajia_click_100 / search_click_100）各自经 `din_encoder` 独立 target-aware 池化后**扁平 concat** 进 main，序列之间**零交互**，跨序列兴趣（查价 × 搜索 × 点击）只能靠下游 DCNv2 点式交叉捕捉。

【推断】这正是 HyFormer（arxiv 2601.12681）§2.5 "独立解码 + 合并增强"（Query Decoding / Query Boosting）所针对的问题：多序列各自池化丢失跨序列协同信号。

【目标】以最小侵入方式引入"跨序列注意力融合"：保留 6 条序列的现有编码路径，在其输出汇入 main 之前插入一个**融合模块**，用可学 global tokens 对 6 条序列输出做 cross-attention 解码，产生融合向量并入 main。

## 二、模块设计

### 2.1 数据流

```
6 条序列组 → 各自 seq_encoder（DIN，保持不变）→ [B, d_i] ×6   (d_i = 各序列 output_dim)
                                    │
                                    ▼
                     SeqFusion 模块（新增）
                     1. 投影到统一 d_fuse：h_i = W_i · emb_i   （每序列独立 Linear）
                     2. 可学 global tokens：G ∈ R^{T×d_fuse}（T=2~4 个 token）
                     3. cross-attention：G' = MHA(Q=G, K/V=[h_1;...;h_6] 序列维堆叠)
                     4. 输出：flatten(G') ∈ R^{T·d_fuse} → 可选输出 MLP → 与 main concat
                                    │
                                    ▼
                      main = concat(原 main 各分量, fusion_out)
                                    │
                        EPNet / PPNet / DCNv2 / PLE（不动）
```

### 2.2 关键设计决策

| 决策点               | 选择                                    | 依据                                                                                  |
| -------------------- | --------------------------------------- | ------------------------------------------------------------------------------------- |
| 保留还是替换 6×DIN   | **保留** DIN，融合模块接在 DIN 输出之后 | 单变量纪律；DIN 的 target-aware 先验是有效信息，替换会叠加两个变量（F1 已单独测替换） |
| global tokens 数 T   | 2（默认），proto 可配                   | token 化粒度无先验；小 T 限制参数量（对 T_max 耦合风险最小）                          |
| 融合维度 d_fuse      | 128（proto 可配）                       | 与 attn_mlp 隐层同量级；控制新增参数在 ~10^5 量级                                     |
| 融合输出进 main 方式 | concat（新增分量），不替换任何现有分量  | 维度链只增不改，existing EPNet/PPNet 输入断言可扩展兼容                               |
| dropout              | 0.0 默认                                | 训练栈逐位复现纪律（AUX_ABLATION_PLAN §五）                                           |

### 2.3 参数量估算（供 T_max 耦合评估）

- 投影层：Σ d_i × d_fuse ≈ (216+224+...)×128 ≈ 6×~150×128 ≈ 1.1×10^5
- MHA（d_fuse=128, 4 heads）：~4×128² ≈ 6.6×10^4
- 合计 **~2×10^5 参数**（对比主干 PLE/DCN ~10^7 量级，占比 \<2%）

【推断】参数量增量小，但非零——T_max=6541 的 cosine 调度失配与 T7 风险仍需按纪律记录实际步数。

## 三、代码改动点（预估 200–400 行）

| #   | 文件                                        | 改动                                                                                             | 备注                                   |
| --- | ------------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------- |
| 1   | `tzrec/modules/seq_fusion.py`（新增）       | `MultiSeqFusion(nn.Module)`：投影 + global tokens + MHA + 输出 MLP                               | 自包含，带 `output_dim()`              |
| 2   | `tzrec/protos/models/multi_task_rank.proto` | `PEPNetDCNPLE` 增加 `optional MultiSeqFusionConfig seq_fusion = 34;`                             | 字段号 34+ 空闲（已用到 33，此前核验） |
| 3   | `tzrec/protos/module.proto`                 | `MultiSeqFusionConfig`：`fuse_dim` / `num_tokens` / `num_heads` / `dropout` / `output_mlp`       |                                        |
| 4   | `tzrec/models/pepnet_dcn_ple.py`            | predict() 中在 6×DIN concat 处接线：若配置了 seq_fusion，把 6 个 DIN 输出喂入模块，输出并入 main | **只增不改**现有 concat 行             |
| 5   | 维度断言                                    | main 组装处 assert fusion 输出 dim == 配置值                                                     | 前科：`BUG_FIX_MLP_DIMENSION.md`       |

【原始证据·扩展点】`FeatureGroupConfig.sequence_encoders`（model.proto L33）挂序列编码器；模型级 fusion 配置挂 `PEPNetDCNPLE`（multi_task_rank.proto L154-199，字段号已用到 33）。二者不冲突：fusion 消费的是编码器输出，不动编码器本身。

## 四、实验设计（单变量臂）

```
臂名：v6f_multiseq_fusion
对照臂：home_flow_2608_v19_multiscene_v6f_kv_fusion.config
唯一变量：新增 seq_fusion 模块（6 序列 DIN 输出跨序列融合）
```

- **开跑前置（硬门）**：先闭环 `ADVERSARIAL_REVIEW_20261029.md` 的 T1/T2/T4（读数归档、脚本去 `rm -rf`、LABEL_DIST 同流指纹比对），否则读数不可复核。
- **判定规则**：沿用 ±0.5pp 噪声带 + 多 seed（≥3）；主判据 grouped_auc_ctr / bce_ctcvr，护栏 CVR 不降。
- **与 F1 的关系**：F1（编码替换，~1 天）是便宜探针。若 F1 Δ 过带（search 编码方式有信号），F2 优先级上调；若 F1 无信号，F2 仍可做（两者假设不同：F1 测"单序列怎么编"，F2 测"多序列怎么合"），但预期管理相应下调。
- **T_max 纪律**：新臂记录实际 steps；若与 6541 偏差 >5%，按 `T_max = steps_per_epoch - warmup(1000)` 重算并在头注释标注（沿用 v6f 头注释既有惯例）。

## 五、风险表

| 风险                                                              | 等级 | 缓解                                                                                                                    |
| ----------------------------------------------------------------- | ---- | ----------------------------------------------------------------------------------------------------------------------- |
| 维度链连坐（fusion 输出 dim 错配 → EPNet/PPNet/component_ln 崩）  | 🔴   | 只增不改 + 组装处维度断言 + 单测覆盖 output_dim                                                                         |
| T_max 耦合：新增参数改变收敛节奏，Δ 混入调度效应                  | 🟡   | 记录实际步数；必要时重算 T_max 并双臂同调度                                                                             |
| 6 序列 padding 语义：chajia/search 变长 100，融合注意力需 mask    | 🟡   | 复用 DIN 侧 `sequence_length` 的 mask 逻辑（sequence.py `_attention_mask`）                                             |
| 与 kv 融合包（285 特征）交互：fusion 把 kv 增益与序列增益混在一起 | 🟡   | 判定时同时看 4/4 口径分解；若需纯净归因，可加"fusion × kv 二因子"后续臂                                                 |
| 期望过高                                                          | 🟡   | 可证伪预期：参考 kv 族量级 +0.04~0.55pp，**不承诺** HyFormer 论文量级（+0.293% 时长等是全量主干结果，不可迁移到增量臂） |

## 六、验收清单

- [ ] proto 编译通过（`protoc` 或 build 流水线）
- [ ] `MultiSeqFusion.output_dim()` 单测：T=2, d_fuse=128 → 256
- [ ] 维度断言单测：注入错误 dim 应 fail-fast
- [ ] mask 正确性：全 padding 序列不产生 NaN（`nan_to_num` 或等价处理，对齐 sequence.py L304 既有做法）
- [ ] 带 seq_fusion 的 config 能走通 train 单步 + export
- [ ] 逐位复现：同 seed 双跑 loss 一致（dropout=0 前提下）

## 七、工作量与排期

| 阶段 | 内容                                          | 估时   |
| ---- | --------------------------------------------- | ------ |
| P1   | proto + `seq_fusion.py` + 单测                | 2–3 天 |
| P2   | pepnet_dcn_ple.py 接线 + 维度断言 + config 臂 | 1–2 天 |
| P3   | train 单步冒烟 + 逐位复现验证                 | 1 天   |
| P4   | 3-seed 消融跑数 + 读数归档（依赖 T1/T2 闭环） | 依算力 |

合计 **~1–2 周**（与可行性判定一致）。
