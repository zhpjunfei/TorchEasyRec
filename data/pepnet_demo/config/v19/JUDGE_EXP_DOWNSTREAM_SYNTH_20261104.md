# 判决实验方案：「下游合成」假说的模型侧判决（20261104）

> **来源**：SQL 取证链收档结论（`SQL_EVIDENCE_CHAIN_20261103.md` §5.7）——F-B（kv 替代）证伪后改判【推断】：
> T0−F1b≈0 的真实机制是**下游合成**：DCNv2+PLE 从 (target emb, seq 池化 emb, kv) 的粗交叉里合成 target-aware 信号，
> 显式 cross-attn 读出通路的边际被下游容量吸收；T2 的 +0.074pp 是下游**难以**合成的部分（per-position `q−s`/`q⊙s` 残差视图）。
> 本实验在模型侧判决该假说（非 SQL）。
> **状态**：方案待立项。config 均为新增文件，不改任何既有 config；无代码改动。

______________________________________________________________________

## 一、判决逻辑（预注册，先写判据再跑）

**操作化**：把"合成能力"拆掉，看 target-aware 读出（T0）相对无 target 读出（F1b）的**配对差值**是否拉开。

- 基线事实【事实读数】：标准骨干下 T0−F1b = **−0.011pp**（ctr）/ −0.047pp（cvr）≈ 0（READOUT_20261030_T0_T3.md）。
- **若合成假说成立**：切断合成后 F1b 失去"追赶机制"，T0 的显式 cross-attn 变珍贵 → **T0−F1b 应显著转正**。
- **若仍 ≈ 0**：假说证伪 → 替代方向 = 序列编码输出进主干的通路容量/信息密度问题（另立项）。

**判决规则（预注册，跑前定死）**——以 Δ = (T0−F1b) 的 ctr 差为主判据，cvr 同向为佐证：

| 读数                                            | 判决                                             |
| ----------------------------------------------- | ------------------------------------------------ |
| Δ ≥ **+0.10pp** 且 ctr/cvr 同向、train 口径同向 | **坐实**：切断的这条通路就是吸收器               |
| \|Δ\| ≤ **0.05pp**（噪声带内）                  | **证伪**：合成不是 T0≈F1b 的原因                 |
| 0.05~0.10pp 之间、或 ctr/cvr 方向不一           | **未决** → 触发 ≥3 seed 收符号（收档纪律不豁免） |

阈值依据：单 seed 噪声尺度 ~0.07pp≈0.3σ（T2−T0 量级），0.05pp 以下视为不可分辨，0.10pp 以上视为单 seed 可读。

## 二、臂矩阵（2 干预 × 2 读出臂，4 个新 run + 已有基线）

| 骨干干预                                     | T0 臂（target-aware 读出） | F1b 臂（self-attn，无 target） | 判据                      |
| -------------------------------------------- | -------------------------- | ------------------------------ | ------------------------- |
| **base**（已有 20261030 读数，不用重跑）     | 0.721449                   | 0.721560                       | T0−F1b = −0.011pp（起点） |
| **C1 去 DCN**（删 `dcnv2` 块）               | 新 run                     | 新 run                         | Δ_C = (T0−F1b)ₙₒ𝒹𝒸ₙ       |
| **K1 去 target-keyed kv**（all 组摘除 5 族） | 新 run                     | 新 run                         | Δ_K = (T0−F1b)ₙₒₖᵥ        |

- T0 = `v6f_seqtrans_base` 形态（transformer h=128/heads=4/L=1 + 门控 + 点积读出）；
- F1b = `v6f_seqattn_click50` 形态（din_encoder + self_attention_encoder(multihead_attn_dim=224)）；
- 两臂共享同一骨干干预，**决策指标只看带内配对差**，绝对 AUC 不跨骨干比较。

**为什么两个干预**：C1 直接拆"合成器"（DCN 乘性交叉），K1 拆"合成原料"（target-keyed kv）。两者独立判决、互为佐证：

- Δ_C 拉开、Δ_K 拉开 → 合成路径 = kv×target 经 DCN 交叉，完整坐实；
- 只 Δ_C 拉开 → 合成器是 DCN，但原料主要是 target emb × seq 池化（非 kv）；
- 只 Δ_K 拉开 → kv 通过非 DCN 通路（如 PLE/门控）供给替代信号；
- 都不拉开 → 合成假说整体证伪。

## 三、config 改动明细（全部新增文件；diff 级描述）

基座规则与 T0-T3 相同：以 `home_flow_2608_v19_multiscene_v6f_kv_fusion.config` 或对应臂 config 字节级拷贝，只动指定块 + 头注释。

### C1 臂（去 DCN）×2

**改动**：删除 `pepnet_dcn_ple` 块内整个 `dcnv2 { cross_num: 4 \n low_rank: 256 }` 子块（L18735-18738 附近）。
**代码依据**【事实读数】：`pepnet_dcn_ple.py` L228 用 `HasField("dcnv2")` 分支——删块 → `cross_net=None` → concat 里不再有 cross 分量（`_cross_concat_dim=0`），干净移除。

> ⚠️ **重要修正：不能用 `cross_num: 0`**。`CrossV2.forward`（interaction.py）0 层循环直接 `return x_0`——恒等直通，
> 且 `component_ln["cross"](cross_output)` 仍会把 LN(main_features) 拷贝进 concat。那是"多一条恒等路径"，不是"切断交叉"。
> 若想做剂量对照，可另加 cross_num∈{1,2} 臂，但判决主臂必须是**删块**。

| 新文件                                                           | 基座                  | 改动        |
| ---------------------------------------------------------------- | --------------------- | ----------- |
| `home_flow_2608_v19_multiscene_v6f_nodcn_seqtrans_base.config`   | `v6f_seqtrans_base`   | 删 dcnv2 块 |
| `home_flow_2608_v19_multiscene_v6f_nodcn_seqattn_click50.config` | `v6f_seqattn_click50` | 删 dcnv2 块 |

### K1 臂（去 target-keyed kv）×2

**改动**：从 `feature_groups { group_name: "all" ... }`（L17312 起，1096 条 feature_names）中摘除 5 个 target 实体族的 `user__kv_*` 引用：
`user__kv_item_id_*`（73 条）、`user__kv_spu_id_*`（45）、`user__kv_third_cate_id_*`（45）、`user__kv_second_cate_id_*`（45）、`user__kv_first_cate_id_*`（44）≈ **252 条**。
特征定义（input_config 里的 lookup_feature）**保留不删**（不进组即不进模型，删定义反而扩大改动面）。

**设计取舍**：

- 为什么是 target-keyed 5 族而不是全量 740 条 kv：这 5 族是 F-B 主角、也是 DCN 交叉"kv×target"原料的核心；其余 kv（site/price/brand/…）是环境/偏好统计，剔除它们会把干预面扩大到与判决无关的通路。
- **domain 组不动**：domain 组的 10 个 `user__kv_*` + 标量走 cdot/bias/lhuc 门控（调制通路，不是交叉原料），保持单变量。此限定写进头注释。

| 新文件                                                                | 基座                  | 改动             |
| --------------------------------------------------------------------- | --------------------- | ---------------- |
| `home_flow_2608_v19_multiscene_v6f_notargetkv_seqtrans_base.config`   | `v6f_seqtrans_base`   | all 组摘 5 族 kv |
| `home_flow_2608_v19_multiscene_v6f_notargetkv_seqattn_click50.config` | `v6f_seqattn_click50` | all 组摘 5 族 kv |

生成后按 T0-T3 纪律做**字节级 diff 校验**（唯一差异 = 头注释 + 指定块），并跑 config 解析冒烟。

## 四、读数协议（沿用 20261030 口径，保证可对账）

1. **同评估集指纹**：`mean_target`、样本数 1,638,400 须与基线逐位一致（去 kv/去 DCN 不动评估集）；
1. **主读数**：eval All-ranks AUC ctr/cvr + train@5500 同向性；
1. **辅助**：`grouped_auc(is_home_scene)`、GRAD_CONFLICT、LABEL_DIST、PRED_STATS（probs mean vs label）、NaN/退化指纹（0.49962… 那个签名）；
1. **对账表**：仿 `READOUT_20261030_T0_T3.md`，每骨干内做 T0−F1b 配对差，跨骨干只比**差值的变化量**（Δ_C、Δ_K 与 −0.011pp 起点比）；
1. 正交读数（预测登记）：若合成假说坐实，**T2−T0 在 C1 骨干下应变大**（无合成环境下 per-position 残差视图更值钱）——可作第三批验证（T2×C1 一跑）。

## 五、执行顺序（按判决价值/成本排序）

| 批次               | run 数 | 内容         | 何时跑                                         |
| ------------------ | ------ | ------------ | ---------------------------------------------- |
| **P0（判决核心）** | 2      | C1×{T0, F1b} | 立项即跑（DCN 是合成假说主角）                 |
| **P1（原料归因）** | 2      | K1×{T0, F1b} | 与 P0 并行有算力就并行；算力紧则 P0 出结果后定 |
| P2（可选验证）     | 1      | T2×C1        | 仅当 P0 坐实，验证"T2 增益随合成拆除变大"预测  |

每 run = 1 个独立训练 job，超参/样本/seed 全部沿用 20261030 口径（固定 seed，配对对比）。

## 六、风险与已知混杂（读数时必须带着看）

1. **绝对 AUC 必降**（去 DCN/去 kv = 容量损失）——这不构成任何判决信息，只看配对差；
1. **cross_num=0 陷阱**（§三已述）——执行时若有人图省事改成 0，实验作废重跑；
1. **单 seed 符号风险**——判决阈值已按噪声尺度设三段；落在"未决"带不许硬解释；
1. K1 的 domain 组限定——若 Δ_K≈0 且 Δ_C≈0，不能排除"kv 经门控通路供给"的残余假说（弱版本），届时补 K2 臂（domain 组 kv 也摘）；
1. 与 SQL 链的口径衔接：SQL 侧已排除 kv 替代（F-B 证伪），本实验的 K1 检验的是"kv 作为**交叉原料**"，与 F-B（kv 作为**替代供给**）是不同命题，结论不许混用。

## 七、产出物清单

- P0/P1 跑完 → `READOUT_<date>_JUDGE_SYNTH.md`（对账表 + 两判据判决 + 预测验证状态）；
- 判决结果回写 `SQL_EVIDENCE_CHAIN_20261103.md` §5.7 的【推断】标注（坐实/证伪/未决）；
- 坐实且 P2 验证通过 → 后续优化方向锁定"残差视图扩展到 search/chajia 序列"；证伪 → 立项"序列输出通路容量"排查。

______________________________________________________________________

*创建：2026-11-04。预注册方案；config 生成与训练执行待立项确认。*
