# self-attn 丢 target-awareness：是否修复 + 修复方案评估（2026-11-01）

# 【问题界定】F1 判定的机制解释是"self-attn 丢 target-awareness 是主要代价"。本文回答：

# ① 这个"缺陷"有必要修复吗？② 若修，修复方案如何评估？

# 【关键定性】这不是修 bug——生效主线（v6f + DIN）没有任何缺陷；这是"要不要为 self-attn 线

# 再投一个新实验臂"的立项问题。F1a/F1b 是探针臂，探针已给出答案（无正收益）。

# 证据标注沿用三层：【原始证据】文件+行号 / 【事实读数】本次实测 / 【推断】分析。

______________________________________________________________________

## 一、判定：不必修复（建议关闭整条序列编码线）

**三条独立证据线收敛到同一结论：序列侧结构改动在本 setup 下上限 ≈ 0。**

### 证据线 1【原始证据·决定性】修复本体早已存在，且已被历史证否

"让 self-attn 具备 target-awareness"的修复形态 = **`TransformerEncoder`**（`tzrec/modules/sequence.py`
L437-585，git: `1714bdb v15: rewrite TransformerEncoder — target leakage fix`），架构正是
"self-attention 上下文化 + target-aware cross-attention 读出 + 门控融合"：

```
s -> proj_in_s -> TransformerEncoder -> h        # 序列内交互（F1 想要的）
q -> proj_in_q -> cross-attention(q, h)          # target-aware 读出（F1 丢掉的）
fused = attended*gate + mean(h)*(1-gate) -> LN -> proj_pooled
output_dim() = sequence_dim                      # 维度自动守恒（216/224 免调参）
```

**该架构在 v14（2026-06-30）已完整消融并正式关闭**（`20-experiments/v14-experiments.md`）：

| v14 臂（对照 ots012）                                                                  | 读数                                              | 结论（原文）                                                                               |
| -------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `ots012_seq_transformer`（single）                                                     | 表：−0.03pp / −0.10pp（双口径）；总结判定 −0.06pp | "❌ 中性，DIN 的 target attention 已充分"（L128）                                          |
| `ots012_seq_transformer_v2`（修复版：weight sharing + separate proj_in + clean query） | 表：−0.17pp / −0.21pp；总结判定 −0.09pp           | "仍中性噪声…TransformerEncoder 最终结论：**证否，DIN 的 target attention 已足够**"（L262） |
| `ots012_seq_transformer_all`（旧版含 bug）                                             | −0.24pp                                           | bug（item_id dim 不共享 + query 侧污染）额外贡献 −0.18pp（L249）                           |

v14 还给出了机制假设（L337，【原始证据】）："性能中性并非架构缺陷，而是 **DCNv2+CDOT 已充分覆盖
序列交叉能力**，Transformer 的 sequence modeling 增量被现有重度交叉淹没。⏹️ 所有 sequence 方向关闭。"

### 证据线 2【原始证据】v15 路线图继承该结论并写入设计约束

- `v15-experiments.md` L9："seq_transformer …均已证否（Δ\<0.1pp）"；L227 预期收益 0.3~0.8pp → 实测未过
- `v15-sie-cross-roadmap.md` L19："seq_transformer −0.06pp vs ots012，**DIN 已充分捕捉 item 交互，
  TransformerEncoder 替换无效**"；L112 设计红线："替代 DIN — DIN 已充分工作（seq_transformer 证否了替换方案）"

### 证据线 3【事实读数】v19 F1a/F1b 复证（本会话，2026-10-31/11-01）

query-free self-attn 裸换：F1a −0.111pp / F1b −0.165pp（带内负）。与 v14 合并解读：
**恢复 target-awareness（v14 TransformerEncoder）→ 回到中性；不恢复（v19 F1）→ 轻负**。
即 target-awareness 确实是承重件（F1 丢它付了 ~0.1pp 代价），但**补回它也只回到零**——
序列方向的收益上限在此 stack 下就是 0。

### 机制一致性（推断）

v14 的假设（DCNv2 重度交叉覆盖序列交互）在 v19 同样成立：`pepnet_dcn_ple` 同样带 DCNv2
（cross_num=4）+ PLE + CDOT 系门控。两代 setup 的共同瓶颈是特征质量而非序列结构
（v14 结论原文："瓶颈不在模型容量…在特征质量本身"）——这与曝光族 kv 特征 +0.52pp 的正向候选互相印证。

______________________________________________________________________

## 二、修复方案矩阵（若坚持要做，按此排序）

| 方案                                       | 内容                                                                  | 成本      | 维度守恒                        | 判定                                                                                      |
| ------------------------------------------ | --------------------------------------------------------------------- | --------- | ------------------------------- | ----------------------------------------------------------------------------------------- |
| **0. 不修，关闭线**                        | 把"序列编码方向证否"写进路线图，资源转曝光族 seed43 / T2              | 0         | —                               | ✅ **推荐**（三线证据支持）                                                               |
| **A. transformer_encoder 消融臂**          | 新增 config：某序列 `din_encoder → transformer_encoder`（代码零改动） | ~1 天     | 自动（output_dim=sequence_dim） | 🟡 唯一有理由做的形态，但仅当"想做 v19 特设确认"或序列建模重回战略焦点                    |
| B. 改 SelfAttentionEncoder 加 target 池化  | 在 self-attn 后接 DIN 式池化                                          | ~1 天代码 | 需显式对齐                      | ❌ 与 A 等价但要写代码——重复造轮子                                                        |
| C. target-token / 双路门控 / F2 多序列融合 | 更大的结构改动                                                        | 3 天~2 周 | 风险高（维度链连坐）            | ❌ v14"更好的 attention 整体被证否"不支持再投入                                           |
| （诊断）target-shuffle 消融                | 破坏 DIN 的 target 条件化看掉幅                                       | ~1 天     | —                               | ⏹️ 不再必要：机制问题已被 v14+F1 合并回答（恢复 target-awareness 也只回中性），无行动价值 |

**方案 A 若做，实验规范**：对照臂 v6f（20261030 已有基线读数可复用）；建议序列选 `click_50_seq`
（与 v15 seq_transformer 同口径，可跨代对照）；`transformer_hidden` 默认 64 即可（output_dim 不随它变）；
判定门沿用 ±0.5pp + 多 seed；预期管理：历史量级是 −0.09~−0.06pp，别期待正收益。

## 三、本次新核验（事实读数）

1. **TransformerEncoder backward 安全性实测**（吸取 F1 NaN 前科，216/224 两维）：混合长度含零长行、
   全有效行两种批次，forward/grad 均无 NaN。掩码用有限大负数 `-(2^31)+1`（L565），不用 -inf。
1. 两个小瑕疵（不修，理由同"休眠对比学习分支"：非生效路径不动）：
   - `seq_mean = h.mean(dim=1)`（L573）含 pad 位置输出 → 短序列 mean 被轻微稀释；
   - 零长行输出非零（实测 `out[zero_row] != 0`，来自 bias/门控通路）。
     两者均不致崩，且该编码器当前不在任何生效 config 中（v19 全线 din_encoder）。
1. proto 兼容：`transformer_encoder` 已在 `SeqEncoderConfig` oneof（seq_encoder.proto L90），config 直接可用。

## 四、对抗面（保留意见）

1. **2604 vs v19 setup 差异**【推断】：v14 证否是在 2604 管线（ots 系）上做的，v19 是多场景 + kv 融合包。
   机制假设（DCNv2 交叉覆盖）迁移度高，但严格说不是同一 setup。若要 v19 特设证据，方案 A 是唯一便宜探针——
   这是"不修"结论唯一的软肋，也已给出兜底方案。
1. **举证责任方向**：F1 已花掉一次实验给出负向；历史 v14 花掉三次。继续投入的举证责任在新方法侧，不在保守侧。
1. F1 判定为"带内负 + 单 seed"，与 v14"带内中性"量级一致，不存在"再跑一次就翻正"的合理预期。

## 五、路线图更新（取代上一轮"F2 暂缓"的开放式表述）

| 线                                  | 状态                                          | 依据                                                     |
| ----------------------------------- | --------------------------------------------- | -------------------------------------------------------- |
| 序列编码替换（F1a/F1b）             | **关闭**                                      | 带内负 + v14 历史证否                                    |
| 序列编码"修复"（target-aware 化）   | **不立项**（= v14 TransformerEncoder 已证否） | 本文                                                     |
| F2 多序列统一解码                   | **关闭**（非暂缓）                            | "更好的 attention"整体被证否，叠加 HyFormer 收益不可迁移 |
| HyFormer 主干级                     | **关闭**                                      | 同上；设计文档（F2_MULTISEQ_FUSION_DESIGN.md）留档作参考 |
| **曝光族 +0.52pp（seed43 收符号）** | **唯一开着的正向候选**                        | READOUT_20261030_EXPOSURE_FAMILY.md                      |
| T2（训练脚本 rm -rf / train==eval） | 仍是后续一切读数的复核前提                    | ADVERSARIAL_REVIEW_20261029                              |

**一句话**：不必修复——"修复"等于重跑 v14 已证否的 TransformerEncoder；self-attn 线及其修复线
均应关闭，序列侧的结论沉淀为"DIN target attention 在本 stack 下已饱和"，资源集中到特征侧（曝光族）与证据链（T2）。
