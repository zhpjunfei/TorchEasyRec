# F1a/F1b NaN 崩溃根因报告（2026-11-01）

> 事件：`home_flow_2608_v19_multiscene_v6f_seqattn_search.config`（F1a）与
> `home_flow_2608_v19_multiscene_v6f_seqattn_click50.config`（F1b）在 20261030 样本集上双双训练崩溃
> （loss=nan、probs=nan、AUC≈0.5 退化）。本报告给出根因、修复与验证。
> 结论分层标注：【原始证据】= 代码/配置原文；【事实读数】= 本次实测输出；【推断】= 分析判断。

______________________________________________________________________

## 一、判定：读数作废，不是"self-attn 效果差"

【事实读数】两臂日志指纹：

| 项                     | F1a (search)        | F1b (click50)       | 对照（2604 multifusion） |
| ---------------------- | ------------------- | ------------------- | ------------------------ |
| eval AUC ctr           | 0.49962174892425537 | 0.49962174892425537 | 0.7232064008712769       |
| eval AUC cvr           | 0.4996945261955261  | 0.4996945261955261  | 0.7449601292610168       |
| bce_ctr                | nan                 | nan                 | 2.55261                  |
| probs                  | 全 nan              | 全 nan              | 正常                     |
| GRAD_CONFLICT 梯度范数 | 全 nan              | 全 nan              | 正常                     |

【事实读数】两臂 eval AUC **逐位相同到小数点后 17 位**。两个不同模型（不同序列换编码器）不可能产生逐位一致的 AUC；
这是"预测张量全 NaN → AUC 计算确定性退化"的指纹（全 NaN 输入使排序/比较行为确定性坍缩）。

**⇒ 该读数不携带任何"编码器孰优"信息，必须作废重跑。** 判定 F1a/F1b 方向为负或无效都是错误解读。

______________________________________________________________________

## 二、根因链（带复现）

### 2.1 缺陷代码

【原始证据】`tzrec/modules/sequence.py` `_attention_mask`（修复前）：

```python
mask = (mask < sequence_length.unsqueeze(1)).int()          # key 有效位
mask = ~(torch.multiply(mask.unsqueeze(2), mask.unsqueeze(1)).type(torch.bool))
#        ^ query_valid[q] × key_valid[k] 再取反
```

对 **pad 位置的 query 行**（`query_valid=0`）：整行全 True（全屏蔽）→ `nn.MultiheadAttention`
内部将 bool mask 转为 **-inf** additive bias → 该 query 行 softmax(全 -inf) = **NaN**。

【原始证据】`SelfAttentionEncoder.forward`（修复前）：

```python
attn_output = torch.nan_to_num(attn_output, nan=0.0)   # L304：只挡前向
...
output = attn_output.sum(dim=1) / sequence_length...   # 前向因此"干净"
```

`nan_to_num` 把前向 NaN 归零——**前向看似正常**；但反向传播中，
`dL/dV = attn_weightsᵀ @ grad_out`，其中 attn_weights 该行为 NaN、grad_out 该行为 0，
IEEE 语义 **NaN × 0 = NaN** ⇒ V/K/Q 投影梯度 NaN ⇒ 一步 optimizer 后全模型权重 NaN
⇒ loss/probs 全 NaN。

### 2.2 复现实验（2026-11-01，修复前后对照）

【事实读数】直接实例化 `SelfAttentionEncoder`（dim=216，与 F1a 同构）：

| 实验 | 批内容                                   | 修复前 grad nan | 修复后 grad nan |
| ---- | ---------------------------------------- | --------------- | --------------- |
| A    | 含零长序列行（无 search 历史用户）       | **True**        | False           |
| B    | 无零长行、但有 padding（长度 [5,2,3]）   | **True**        | False           |
| D    | 10 步 Adam 模拟（混合长度含 0，lr=3e-4） | —               | CLEAN           |

**关键读数（B）：不需要零长序列——只要 batch 里有 padding 就中招。** 真实数据序列长短不一，
几乎每个 batch 都有 padding ⇒ 第一个 backward 即 NaN ⇒ 与"跑满 5500 步后全 nan"的现场一致
（NaN 在训练早期即发生，之后全程污染）。

### 2.3 为什么 DIN 从来没这个问题

【原始证据】`DINEncoder.forward` 掩码用**有限大负数**而非 -inf：

```python
padding = torch.ones_like(attn_output) * (-(2**31) + 1)   # 有限值
scores = torch.where(sequence_mask.unsqueeze(1), attn_output, padding)
```

全屏蔽行 softmax(全等值) = uniform 分布（有限）⇒ 前向反向都干净。这是 SelfAttentionEncoder
（bool → -inf）与 DIN 的本质差别。

### 2.4 为什么之前的交付审计没抓到

【推断·认领】上一轮"F1/F2 交付物自审"做了编码器运行时构造测试，但**只验了 forward 形状与 forward NaN，
没有跑 backward**——而这个 bug 恰好只存在于反向路径（前向被 `nan_to_num` 伪装干净）。
测试盲区 = 交付物盲区。教训已固化：**编码器验证必须含 `loss.backward()` + 梯度 NaN 断言**。

【推断】该缺陷在代码库中长期潜伏的原因：`SelfAttentionEncoder` 此前从未在真实变长序列数据上
训练过（v19 F1a/F1b 是它的首次实用）。等长合成数据（无 padding）不会触发。

______________________________________________________________________

## 三、一处声明修正（对我自己）

我在初判时曾据 C 项实验（len-1 序列在 L=100 窗口输出 norm 3.2 vs 有效嵌入 14.2）声称存在
"pooling `sum(dim=1)/length` 被 pad 行污染"的第二 bug。**该解读是错的**：
修复前后 C 项输出逐位一致（3.2479…）——因为 pad query 行输出本就被 `nan_to_num` 清零，
前向语义其实一直是对的（有效位置均值）。norm 差只是随机初始化 attention 输出与原始嵌入的尺度差。
真正的 bug 只有一个：**反向 NaN 梯度陷阱**。本次顺手加的 masked pooling（显式只累加有效位置）
是卫生改进（不再依赖 NaN 副作用保证正确性），**前向与修复前等价**，不构成新的行为变化。

______________________________________________________________________

## 四、修复（已完成，2026-11-01）

【原始证据】`tzrec/modules/sequence.py`（git diff 仅此 26 行，其余文件未动）：

1. `_attention_mask`：改为 **key-only 的 additive float bias**（pad key = -1e4，有限值）。
   - pad query 行不再被整行屏蔽 → 无全 -inf 行 → 无 NaN（前向反向都干净）
   - 零长行：全 -1e4 → softmax uniform（有限）→ 输出随后被 valid_mask 清零
   - -1e4 在 fp32/fp16 下均为有限值（fp16 min=-65504），不复现 -inf 溢出
1. `SelfAttentionEncoder.forward`：显式 `valid_mask` 只累加有效 query 位置（前向等价，语义显式化）
1. `nan_to_num` 保留（双保险）

### 验证矩阵（2026-11-01 实测）

| 验证项                                             | 结果             |
| -------------------------------------------------- | ---------------- |
| A 零长行：forward 干净、输出=0、梯度干净           | ✅               |
| B 带 padding：梯度干净                             | ✅               |
| C len-1-in-L100 输出与修复前一致（前向等价）       | ✅ 3.248 = 3.248 |
| D 10 步 Adam（混合长度含 0）loss/梯度/参数全程有限 | ✅ CLEAN         |
| E DIN 回归（未触碰路径）forward/梯度干净           | ✅               |

### 隔离性保证

【事实读数】`_attention_mask` 全仓库唯一调用方 = `SelfAttentionEncoder.forward`（L300）；
`DINEncoder` / `MultiWindowDINEncoder` / `TransformerEncoder` 均不使用它（各有独立掩码/模块）。
v19 活跃 config 全部只用 `din_encoder` ⇒ **当前生效逻辑零影响**。git diff 确认只动 `sequence.py`。

______________________________________________________________________

## 五、同场读数点评：2604 两臂（multifusion vs multinoexp）

【事实读数】20261030 同一评估集（mean_target 完全一致：ctr 0.3663366734981537 / cvr 0.12034362554550171，1,638,400 样本）：

| 指标                          | multifusion | multinoexp | Δ           |
| ----------------------------- | ----------- | ---------- | ----------- |
| eval AUC ctr                  | 0.72321     | 0.71800    | **+0.52pp** |
| grouped_auc_ctr（train 窗口） | 0.71903     | 0.71368    | +0.54pp     |
| eval AUC cvr                  | 0.74496     | 0.74403    | +0.10pp     |
| grouped_auc_cvr               | 0.74228     | 0.74146    | +0.08pp     |

【推断】ctr 侧 +0.52pp 恰在 ±0.5pp 噪声带边缘（刚过/压线），cvr 侧带内中性；
单 seed 单日读数，按既有判定规则**不可定案**——尤其 multinoexp 的 GRAD_CONFLICT 显示
ema_grad_norm_cvr=0.019（CVR 塔梯度极小），两臂 CVR 差异可能未充分训练。
若 multifusion 是"融合包"变量的 2604 口径复验，值得补 seed 看符号稳定性。

## 六、证据链状态更新（对抗审核 T1/T2/T4）

【事实读数】`train_v19_multiscene.sh` 现状（2026-11-01）：

- ✅ 已支持 `bash train_xxx.sh <config>` 传参（本轮 4 个 run 依赖它）
- ❌ T2 未修：L35 `rm -rf "${MODEL_BASE}"` 仍在；L46 日志固定 `v19_multiscene.log`
  （**同一台机器串行跑会互相覆盖 ckpt 与日志**——本轮 F1b(14:14)/F1a(14:19) 相隔 5 分钟，
  贴片能保住说明日志被及时拷走或分机跑；下次未必有这运气）
- ❌ T3 未修：L14-15 `eval_input_path == train_input_path`（训练表上评估）
- ⚠️ T4：20261030 样本流的 LABEL_DIST 指纹（is_click 0.3667 / is_conversion 0.1248）需与 v5/v6
  历史跑的指纹比对确认同流，否则跨臂 Δ 仍带 2.6pp 级漂移风险。

## 七、下一步（按序）

1. **重跑 F1a/F1b**（修复后首次有效读数）；开跑前强烈建议先把 T2 的 `rm -rf` 与日志名按 config 分离，
   否则读数仍可能丢。
1. **跑 v6f_kv_fusion 基线**（20261030 同流）作对照臂——F1 的 Δ 必须相对 v6f，不是相对 2604。
1. LABEL_DIST 指纹比对（T4）后再看 Δ；判定沿用 ±0.5pp 带 + ≥3 seed。
1. F2（多序列统一解码）立项门不变：F1 过带才推进。
