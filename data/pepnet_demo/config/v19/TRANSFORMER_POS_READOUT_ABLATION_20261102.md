# 序列信号消融臂 T0-T3 设计与交付（pos 编码 + 4 路交互读出 + 时间门控）

日期：2026-11-02（T0-T2 首发）｜ 2026-11-03 修订（探针切换 click_50_seq + 新增 T3）｜ 状态：已交付（代码 + 4 config + 验证矩阵），待训练读数
对照血统：`home_flow_2608_v19_multiscene_v6f_kv_fusion.config`（20261030 样本集读数基线）

______________________________________________________________________

## 〇、20261103 修订记录（探针切换 + ts 事实修正）

1. **ts 事实修正**（用户指正后核对）：初版动机 1 称"顺序与时间信息在整个序列通路不可见"**过强，收回**。
   实际：`click_10/click_50/conversion_20/favorite_10_seq` 各含 `ts` 子特征（raw_feature，
   FG 层自动把 event_unix_time 转**近因秒数差**，19 边界≈1min~7d → 20 桶，emb=8，见
   `30-data/sample-v3-pipeline.md` §7）；**search_click_100_seq、chajia_click_100_seq 无 ts**
   （216=19 子特征 vs click_50 224=20 子特征，8 维差正是 ts）。缺的不是时间数据，而是
   **时间专属通路**：`DINEncoder.time_gate_dim` 未启用，ts 桶嵌入仅作普通内容特征拼入
   （8/224 维），且序列组内 ts 无 target 侧配对（DIN 4 路交互无时间交互项）。
   拼接顺序证据：embedding.py 按 `sequence_group.feature_names` 顺序 concat（L1197-1202 append
   → L1473 `torch.cat(dim=-1)`），`click_50_seq__ts` 恰为组内末项 → **ts 占序列嵌入末 8 维**，
   满足 time_gate_dim "末 N 维"约定。
1. **探针切换 search_click_100_seq → click_50_seq**（用户决策，T0-T2 就地改）：
   ①行为更稠密（F1 选型时已提出）；②ts 在场，T1/T3 依赖时间信号；③F1b（self_attn click_50，
   eval ctr −0.165pp）同位，构成 **din↔self_attn↔trans 三角对照**。
   代价：T1 解读变化，见臂矩阵注。
1. **新增 T3**（`..._v6f_dintimegate.config`）：DIN + `time_gate_dim: 8`，把 OneTrans 时间信号
   线索落成零代码消融臂（proto 现成，sequence.py 机制内建）。

## 一、动机（前两轮审核结论的落地）

1. **结构完整性审核**（20261102）：`TransformerEncoder` 的块结构（MHA + Add&Norm + FFN + Add&Norm，
   PyTorch `TransformerEncoderLayer` post-norm）本身完整，**唯一缺口是 pos embedding**——
   这是 Transformer 理论上唯一能做 DIN 做不到的事（顺序敏感性）的入口。
   [修订] 时间信息在 4/6 序列已部分在场（ts 桶），但无显式调制通路 → 由 T3 专项消融。
1. **读出打分审核**（20261102）："单点积 cross-attn 读出是 DIN 弱化版"——打分函数缺逐位置
   [q, s, q−s, q⊙s] 4 路交互（该论断限定为打分形态对比，详见审核记录；v14 TransformerEncoder
   −0.06/−0.09pp 与该因子方向一致但混杂）。
1. **加层（深度）已判定不优先**：v14 容量类旋钮（PLE expert ×4、CVR tower 扩宽）全证否，
   元结论"瓶颈不在模型容量"；预期效应量 < ±0.5pp 噪声带。本组不做，`num_layers` 字段本就可配，留待需要时单臂。

## 二、臂矩阵（探针位置：click_50_seq，20261103 起，与 F1b 同位）

| 臂     | config                               | 编码器（唯一变量）                                        | 对照          | 归因问题                                |
| ------ | ------------------------------------ | --------------------------------------------------------- | ------------- | --------------------------------------- |
| **T0** | `..._v6f_seqtrans_base.config`       | transformer（hidden=128, heads=4, L=1, dot_product 读出） | v6f_kv_fusion | transformer 读出 vs DIN，本线基线重建   |
| **T1** | `..._v6f_seqtrans_pos.config`        | T0 + `use_pos_encoding: true`                             | **T0**        | 位置编码的边际（解读见下注）            |
| **T2** | `..._v6f_seqtrans_dinreadout.config` | T0 + `readout_type: "din_mlp"`（attn_mlp 128→64 Dice）    | **T0**        | 4 路交互打分 vs 单点积的边际贡献        |
| **T3** | `..._v6f_dintimegate.config`         | din + `time_gate_dim: 8`（非 Transformer 系）             | v6f_kv_fusion | 时间门控通路的边际（OneTrans 线索落地） |

- T2 打分头与被替换的 DIN 打分头**同构同容量**（128→64 Dice）——对比的是打分形态，不是容量。
- Transformer 系 output_dim 经 `proj_pooled` 自动守恒 =224（click_50 20 子特征 emb 之和，末 8 维=ts），
  EPNet/PPNet/component_ln/AFP 维度链不动（BUG_FIX_MLP_DIMENSION.md 前科防线）。
- **T1 解读变化**（探针切换代价）：click_50_seq 按 event_unix_time 排序且 ts 近因桶已在场，
  pos 与时间信号**部分冗余**——T1 测的是"顺序在时间桶之外的边际"（部署问题）；
  若 T1 为零**不能**断言顺序无用（可能被 ts 吸收），纯顺序归因需另跑 search 侧臂（可选 T1s）。
- **T3 双因子警示**：`time_gate_dim` 同时改变①打分受 gate 调制、②DIN 输出 224→216
  （ts 8 维退出输出；`output_dim()=content_seq_dim` 自洽，下游维度链**动态适配**不连坐——
  `_group_feature_dims` 按 `seq_encoder.output_dim()` 构建，embedding.py L352-361）。
  与基线差值含"ts 退出输出"份量，机制内不可拆；若读数显著需补对照归因到"门控"本身。
- 交叉对照矩阵（click_50 同序列）：DIN（v6f）↔ self_attn（F1b，−0.165pp）↔ trans（T0）
  ↔ trans+pos（T1）↔ trans+dinreadout（T2）；search_click_100_seq 侧留有 F1a（−0.111pp）参考点。

## 三、代码改动（全部 opt-in，默认关闭 → 既有逻辑逐位不变）

| 文件                                    | 改动                                                                                                                                                                                                                                                 |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tzrec/protos/seq_encoder.proto`        | `TransformerEncoder` 新增字段：`use_pos_encoding=8 [default=false]`、`readout_type=9 [default='dot_product']`、`attn_mlp=10`（可选）；`DINEncoder.time_gate_dim=7 [default=0]`（**原有字段，非本次新增**）                                           |
| `tzrec/protos/seq_encoder_pb2.py(.pyi)` | 重新生成（grpc_tools.protoc，仅此一个 proto）                                                                                                                                                                                                        |
| `tzrec/modules/sequence.py`             | ① `_sinusoidal_pos_encoding` 助手（正弦、**零参数**、不进 checkpoint）；② `TransformerEncoder`：forward 在投影后按开关加 PE；读出按 `readout_type` 分支（din_mlp = 逐位置 MLP([q,h,q−h,q⊙h])→标量分，尾部 mask/softmax/pooling 与 dot_product 共用） |

- `readout_type` 非法值 / `din_mlp` 缺 `attn_mlp` → 构造即抛错（fail fast）。
- 既有 config 不写新字段 → 默认值流入构造函数 → 代码路径与改动前完全一致。
- 对比学习分支、`_attention_mask` 修复（20261101）均未触碰。T3 为纯 config 改动，零代码。

## 四、验证矩阵

**20261102（T0-T2 代码，本地 python3.11 / torch 2.11.0，5/5 全过）**

| #   | 项                                                                                 | 结果                                                                  |
| --- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 1   | 默认路径回归（改动前后 train 模式，同 state_dict 同输入，含 padding/零长行 batch） | **逐位一致**（max_diff=0.0，Transformer 与 DIN 双双 bitwise）         |
| 2   | `use_pos_encoding=True`                                                            | 输出有限、维度守恒、输出确实变化（PE 生效）、fwd/bwd 无 NaN、梯度干净 |
| 3   | `readout_type='din_mlp'`                                                           | 维度守恒、fwd/bwd 无 NaN、梯度干净                                    |
| 4   | 工厂传参（`create_seq_encoder` ← proto 新字段）                                    | 字段正确流入构造函数                                                  |
| 5   | 零长行 batch（全 pad，din_mlp 读出）                                               | 前向有限、梯度干净                                                    |

**20261103（探针切换 + T3，全过）**

| #   | 项                                                             | 结果                                                                                                                 |
| --- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| 6   | pb2 解析 5 config（v6f + T0-T3），click_50 编码器回读          | din / trans(pos=F,dot) / trans(pos=T) / trans(din_mlp) / din(tg=8) 全部正确                                          |
| 7   | 字节级校验 T0-T3 vs v6f                                        | 唯一差异=头注释+编码器块（single_swap_tail_identical=True）                                                          |
| 8   | DIN `time_gate_dim=8` 运行时                                   | 输出 (B,216) 与 `output_dim()`=216 自洽；fwd/bwd 无 NaN；含零长行 batch；ts 尾 8 维扰动改变输出（gate 通路实测激活） |
| 9   | TransformerEncoder 224 维（click_50）构造+前向反向，T1/T2 开关 | 输出 224 维守恒、无 NaN                                                                                              |

**工况说明（审计盲区记录）**：20261102 首轮回归曾误报不一致（max_diff≈1.96），根因是比对误用 `.eval()`——
`Dice` 内嵌 `BatchNorm1d` 且 eval 触发 nested-tensor 快路径，均为改动前就存在的模式效应；train 模式逐位一致。
另：本地 protobuf 7.35 与仓库 `config_util` 旧参数名不兼容属本地环境问题（训练机老 protobuf 正常），未改仓库。

## 五、读数方案（待执行）

- 样本集：**20261030**（与 2604/F1 同流）；LABEL_DIST 同流指纹、实际步数核对 T_max=6541 调度失配。
- 纪律：单变量（T1/T2 只对 T0；T3 对 v6f）、±0.5pp 噪声带、**≥3 seed**；先 T0 收基线，再 T1/T2 归因；T3 独立可并行。
- 判定：
  - T1 或 T2 对 T0 过带为正 → 该组件保留，评估叠加（T1+T2 合臂）与 F2/主干级立项的相对优先级；
  - T3 对 v6f 过带为正 → 时间通路值得深挖（如 Transformer 系加时间门控、search/chajia 补 ts 的数据侧改造）；
    显著为正时按双因子警示补对照拆分归因；
  - 全部带内/为负 → 写入与 v15"替代 DIN 证否"同级的红线结论，序列编码维持 DIN。
- 前置：ADVERSARIAL_REVIEW_20261029 的 T1/T2/T4 闭环（读数归档、训练脚本去 `rm -rf`、固定 log 名改带时间戳）。

## 六、部署注意

1. 训练机需同步三件：`sequence.py`、`seq_encoder.proto`、`seq_encoder_pb2.py`。
   若训练机 protobuf runtime 与本地生成不兼容，**在训练机上跑 `scripts/gen_proto.sh` 重新生成即可**。
1. 四个 config（T0-T3）中 T0-T2 为**就地改探针**（20261103，此前未跑读数，无作废读数），
   T3 为新增文件；字节级校验：除头注释与编码器块外与 v6f 逐字节一致。
1. 数据侧遗留缺口（另立项，非本组）：search_click_100_seq / chajia_click_100_seq 缺 ts 子特征
   （RT_SEQ_FEATURE 管道差异，见 sample-v3-pipeline.md §7a）；若 T3 为正可评估补齐。

______________________________________________________________________

## 读数归档（2026-11-03）

T0-T3 首批读数（20261030 样本集，单 seed）已归档至 `READOUT_20261030_T0_T3.md`。要点：T2−T0=+0.074pp（打分形态是唯一正向因子）、T1−T0≈0（pos 无边际）、T3−v6f 无正收益、T0−F1b≈0（target 通路不值钱，修正 F1 时代归因）。全部差值带内单 seed，不判符号；序列线红线候选待多 seed 收尾。
