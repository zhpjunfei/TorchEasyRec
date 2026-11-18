# v19 主文档 · 最新结论与进展（唯一入口）

> **定位**：本文件是 v19 实验线唯一"活文档"——**永远滚动更新为最新、最完整的结论与进展**。
> 其余全部文档均为**证据底稿**（append-only，记录当时证据与判决，不回头改写）。
> **维护规则**：每次读数落盘 / 判决变更 / 阶段推进后，必须同步更新本文件对应章节；底稿新增时在 §九 文档地图登记链接。
> **最后更新**：2026-11-12 11:36（SQL-17 判决：NULL 语义定谳 = **(a) 未打分/覆盖不足**（NULL 桶历史深度仅低分桶 39%、无历史率 6.2×，假说 b 强烈拒绝）→ **convert_probability 勘验链收档**；FG 反馈走覆盖路线；P1-6r 0 桶注释终稿）
> **文档目录**：`/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/config/v19/`

______________________________________________________________________

## §0 一页速览（TL;DR）

**基线**：`home_flow_2608_v19_multiscene_v6f_kv_fusion.config`（20261030 窗全场最优：ctr 0.723206 / cvr 0.744960；12 跑无一超过）。

**已收档的两个假说**（均不成立）：

1. "kv 已供给匹配信息" → **证伪**（SQL-1~6，F-B 检验）；
1. "下游 DCN/PLE 合成 target-aware 信号" → 判决实验点估计**未获支持**（4 臂 Δ≈0，T0−F1b≈0 是骨架性质）。

**当前主线**：P0 特征族单变量实验（20261109 窗，单 seed 已出）：

- ✅ **P0-2a 序列 ts 补全：符号闸 PASS 过闸（宣称级）**——3-seed 配对 Δctr = +0.2395/+0.2086/+0.3157pp（**mean +0.2546pp**，3/3 同号）；train==eval 债已清（用户多次核查一致），**宣称解锁**；
- P0-4 曝光 rt 标量：+0.081pp 灰区 → 哨兵 p04@43 +0.0655pp 同向 → **并组合臂因子**（不宣称）；
- ❌ P0-3 overlap 标量：−0.049pp → 弃；
- ❌ P0-2b time_gate×4：−0.198pp → 弃（time_gate 族两窗收档）。

**符号闸收账**（2026-11-11 晚）：seed43/44 两对补齐，**闸 PASS**——Δctr 3/3 同号（+0.2395/+0.2086/+0.3157pp），mean +0.2546pp ≥ 0.15pp；seed43 差异性检查过（种子生效）；train 批 3/3 同向。seed42 复跑曾验 bit 级确定性。**无需第 4 seed**（"模棱两可才决胜"分支未触发）。

**待办**：① 对外宣称 P0-2a（train==eval 债已清）；② p02a 定版合并新基线；③ P0-4 已拍板=并组合臂（下一梯队测 p02a+p04 叠加）；④ P1-6r config 已备好 + 组合臂，各需 1 run——预算 10/10 用满，**扩预算或排序让位等拍板**；⑤ FG 需求单照旧。

**口径红线**：20261109 窗与 20261030 窗**绝对值不可比**，一切结论只在同窗配对 Δ 内有效。

______________________________________________________________________

## §1 基线与归因（事实读数，已收档）

| 结论                        | 读数                                                                                       | 出处                                                               |
| --------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| 基线 = v6f_kv_fusion        | ctr 0.723206 / cvr 0.744960，20261030 全部 12 跑无一超过                                   | [SUMMARY_20261030_ALL_RUNS.md](SUMMARY_20261030_ALL_RUNS.md)       |
| exposure 族 kv 值钱         | +0.52pp（全场最大正向；形态收窄为"粗实体 × 曝光行为 × 实时窗"）                            | [PLAN_CTR_NEXT_20261105.md](PLAN_CTR_NEXT_20261105.md)             |
| DCNv2 是通用放大器          | 删掉均摊 −0.4~0.5pp，不偏袒任何读出形态                                                    | [READOUT_20261105_JUDGE_SYNTH.md](READOUT_20261105_JUDGE_SYNTH.md) |
| DIN 4 路读出形态值钱        | T2−T0 = +0.074pp                                                                           | [SUMMARY_20261030_ALL_RUNS.md](SUMMARY_20261030_ALL_RUNS.md)       |
| target-aware 点积读出无增益 | T0−F1b≈0 为骨架性质（删 kv / 删 DCN / 换骨干三种切法 Δ 一致 ≈0）                           | [READOUT_20261105_JUDGE_SYNTH.md](READOUT_20261105_JUDGE_SYNTH.md) |
| 线上精排融合公式            | `score = ctr × (1 + cvr) × 0.12`（用户口径；高 CVR 内容在均值口径吃亏，尾部高 cvr 可翻盘） | 用户长期记忆                                                       |

**判据（预注册，先于实验，不挪门槛）**：Δctr ≥ +0.10pp 续投｜|Δ| ≤ 0.05pp 弃｜过闸走 3-seed 符号闸（3/3 同号 + |mean| ≥ 0.15pp）｜宣称级结论前必须清 train==eval 债。单 seed σ_Δ≈0.25pp，单 seed 点估计只可用于收档，**不可对外宣称**。

______________________________________________________________________

## §2 已收档假说（判决链，只读）

### 2.1 "kv 已供给匹配信息" → 证伪

SQL-1~6 取证链（[SQL_EVIDENCE_CHAIN_20261103.md](SQL_EVIDENCE_CHAIN_20261103.md)）：

- kv 列真实类型 = **原生 MAP\<STRING,FLOAT>**（客户端 JSON 渲染误导；列类型以执行报错/DESC 为准）；
- F-B 检验：k0 零历史带内 match 梯度 2.92× 不消失、梯度随 kv 档位不收敛（k4 仍 2.05×）→ 假说证伪；
- 副发现：绝大多数样本落在"同品类、不同商品"区（4 路打分与单点积拉开差距的区域，见 §8 演示）。

### 2.2 "下游 DCN/PLE 合成 target-aware 信号" → 未获支持

判决实验（[JUDGE_EXP_DOWNSTREAM_SYNTH_20261104_v2.md](JUDGE_EXP_DOWNSTREAM_SYNTH_20261104_v2.md)｜审核 [REVIEW\_…](REVIEW_JUDGE_EXP_DOWNSTREAM_SYNTH_20261104.md)｜读数 [READOUT_20261105_JUDGE_SYNTH.md](READOUT_20261105_JUDGE_SYNTH.md)）：

- Δ=T0−F1b：base −0.011pp / C1 删 dcnv2 −0.070pp / K1 摘 203 kv −0.037pp——三骨干一致 ≈0；
- 单 seed 未过符号闸 → 正式判决"未决"，但点估计下**强版假说无生存空间**，收档；
- 附带勘误档案：CrossV2 `cross_num=0` 恒等直通陷阱；favorite_10 的 ts emb=4（非 8）。

______________________________________________________________________

## §3 SQL 取证链总账（SQL-1~17，全部收档）

| SQL | 问题                              | 判决                                                                                                          |
| --- | --------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 1~3 | kv 值钱形态定位                   | 粗实体 × 曝光 × 实时窗才值钱（+0.52pp 由 exposure 支撑）；ID 级点击统计边际≈0                                 |
| 4~6 | kv 是否供给匹配信息               | **证伪**（MAP 类型勘误 + F-B 检验）                                                                           |
| 7   | exposure 家族盘点                 | 89 条 exposure / 731 条 kv 全景入册                                                                           |
| 8~9 | like_100 / sconv20 真实密度       | 占位符污染定谳：like 真实填充 **5.86%**（P0-1a 弃）；sconv 49.4%（P0-1b 二梯队）；fill=1.0 是 SIZE>0 口径假象 |
| 10  | chajia/search 真实密度 + ts 尺度  | 真实填充 44.9%/76.7%（≥20% 过闸）；ts = 近因秒数差（非裸 unix）→ P0-2a 回第一梯队                             |
| 11  | P0-2a 边界定标                    | 两序列各 19 分位点已定标（借位压扁风险解除）                                                                  |
| 12  | convert_probability 泄漏/校准勘验 | **泄漏排除**（无近完美校准桶）；值域无界（avg_cp=52.9）→ P1-6 as-is 暂停                                      |
| 13  | 值域定标（H_scale vs H_score）    | **H_scale 百分制确认**（j+k=0，值域 0~100）；非零段 cvr 严格单调（8/8 步升）→ **P1-6r 重启**（分桶序信号）    |
| 14  | 零点反转构成分解                  | **cp>0 100% 单品**；非单品结构性 N/A；构成效应解释 2.55× 断崖 → 1.30×                                         |
| 15  | 单品冷启动假说                    | 浅历史倾斜证实（深度 45%、无历史率 11.7×）；窄义冷启动**算术排除**                                            |
| 16R | 源头零值语义（源头表）            | **真实 0 分 0 行**（min=1.1）→ 编码 0 桶 100% NULL 填充，"真实 0 分"撤销                                      |
| 17  | NULL 语义判别                     | **(a) 未打分/覆盖不足坐实**（画像不同形）；(b) 打分为 0 强烈拒绝                                              |

详录：SQL-8~11 见 [PLAN_CTR_NEXT_20261107.md](PLAN_CTR_NEXT_20261107.md) §9.1–9.8；**SQL-12~17（convert_probability 勘验链）SQL 原文+结果表+结论** → [SQL_EVIDENCE_CHAIN_CONVERT_PROB_20261112.md](SQL_EVIDENCE_CHAIN_CONVERT_PROB_20261112.md)（论证与判读图见 PLAN §9.10–9.12）。

**convert_probability 终局结论**：百分制"预估出单概率"（0~100）；**0 桶 = 源头 NULL 填充（未打分/覆盖不足）+ 非单品 N/A**，非真实 0 分；打分器有分段序有效（cvr 严格单调）、校准差 → **只作序信号不作概率**；"零点反转" = 缺分人群高转化（覆盖缺口），bug 假说排除。P1-6r（boundaries 1e-08/1/5/10/20/40/60/80/100 分桶）已备 config；FG 备注：−1 哨兵必须 + 打分覆盖扩展建议。

______________________________________________________________________

## §4 P0 特征族实验（当前主线）

### 4.1 第一梯队读数与判决（20261109 窗，单 seed，[READOUT_20261111_P0_FIRST_BATCH.md](READOUT_20261111_P0_FIRST_BATCH.md)）

eval 同指纹逐位一致（mean_target / LABEL_DIST / 1,638,400 样本五跑相同）→ 配对有效；train 批 auc 排序与 eval 排序逐位一致。

| 臂                                                       | config                    | Δctr                           | Δcvr                 | 判决                                                                      |
| -------------------------------------------------------- | ------------------------- | ------------------------------ | -------------------- | ------------------------------------------------------------------------- |
| **P0-2a seqts**（chajia/search 补 ts，SQL-11 定标边界）  | `..._v6f_p02a_seqts`      | **+0.240pp**                   | +0.044pp             | ✅ **续投 → 3-seed 符号闸**（超预期上限；⚠ 约 1σ，过闸前不宣称）          |
| P0-4 exposurert5（曝光 rt 标量 5 条）                    | `..._v6f_p04_exposurert5` | +0.081pp（42）/+0.0655pp（43） | +0.009pp / −0.0009pp | 哨兵 triage 正 → **组合臂因子**（2/2 同号均灰区，不宣称）                 |
| P0-3 overlap10（offline_like/order common_ratio 10 条）  | `..._v6f_p03_overlap10`   | −0.049pp                       | −0.046pp             | ❌ 弃（"密度无关标量通道"假设未兑现）                                     |
| P0-2b timegate4（四序列 time_gate + grad_clipping 搭车） | `..._v6f_p02b_timegate4`  | −0.198pp                       | −0.127pp             | ❌ 弃（time_gate 族收档：T3 单序列 −0.062pp → 本次 −0.198pp，两窗同向负） |

生成与验证：[GEN_P0_FIRST_BATCH_20261109.md](GEN_P0_FIRST_BATCH_20261109.md)（diff 纯新增 4/4、proto 冒烟 5/5、边界 2/2、time_gate_dim 4/4；脚本 `gen_p0_first_batch_20261109.py` 幂等可重跑）。

### 4.2 后续队列（未启动）

| 臂                                  | 状态                       | 说明                                                                                                        |
| ----------------------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------- |
| P0-1b sconv20_seq                   | 二梯队末位（试探档 1 run） | 真实填充 49.4% 但均长 3.2，保守不升档                                                                       |
| P0-1a like_100_seq                  | **弃（终审）**             | 真实填充 5.86%，占位符污染 94%                                                                              |
| P1-1…6（item 先验/价格/订阅画像等） | 排队                       | 详见 [PLAN_CTR_NEXT_20261107.md](PLAN_CTR_NEXT_20261107.md) §二；convert_probability 先过泄漏核查           |
| P2 观察项                           | 登记                       | Self-vs-历史标量门（Relation 借鉴 A）、seqtrans_rel（借鉴 C）、HiRank 兴趣检索（需新写 seq encoder）——见 §6 |

### 4.3 需求单（FG/数据面，与训练并行）

- R1 cfr 扩展 / R2 exposure 窗口细化（[PLAN_CTR_NEXT_20261105.md](PLAN_CTR_NEXT_20261105.md)）；
- R3/R4 新行为序列、场景曝光序列——**数据面判死**（fg 后编码表无此列），转 FG 需求单；
- R5 人群比率族 219 个 `__kv_ratio_*`（样本表有、pyfg 编码丢弃）→ 试点级待定；
- like 序列真实稀疏（5.86%）→ 佐证 FG 侧"序列覆盖优先"需求（HiRank 借鉴 C 同向印证）。

______________________________________________________________________

## §5 特征盘点结论（[UNUSED_FEATURES_FG_V5_20261105.md](UNUSED_FEATURES_FG_V5_20261105.md)）

- fg_v5.json 共 1186 条目：**81 个命名特征未用**（6 族）+ like_100_seq / search_conversion_20_seq 两条整序列未接（后经 SQL-8/9 判：前者弃、后者二梯队）；
- DDL 双表对账（fg 前 1502 列 → fg 后 1358 列）：232 消失列定谳；P0 全部臂"纯 config 可跑、零 FG 依赖"前提成立（SQL-8~11 补齐密度/边界前置）；
- kv 全景：731 条 kv 全在用，其中 exposure 89 条是值钱形态。

______________________________________________________________________

## §6 外部借鉴评估（两篇知乎，均已收档）

| 文章                                         | 结论                                                                                             | 落地                                                                                                                                                                                                                                                                                                           |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Relation Is All You Need（arXiv 2608.20172） | **借鉴有限，不进 P0**——近因修正与 P0-2a/P0-2b 功能重叠；效率卖点对 L≈40 无意义；LM PPL ≠ CTR AUC | P2 观察项：Self-vs-历史标量门（A）、seqtrans_rel 换打分算子（C）；动画 [relation_attention_vs_din_borrowing.html](/Users/zhangjunfei/WorkBuddy/2026-10-29-15-06-17/relation_attention_vs_din_borrowing.html)                                                                                                   |
| HiRank（arXiv 2610.35318，淘宝精排）         | **近期最有借鉴价值**，但不改 P0 跑序                                                             | ✅ 零预算即刻：eRank 表示审计（A）、eval 补 GAUC 口径（B）、序列覆盖优先印证（C）；⚠ P2：互补检索（D，需新写 seq encoder，消融最大结构件）、HSTU 门控（E）；⛔ P3：场景压缩/High-Rank（F）。动画 [hirank_vs_v19_borrowing.html](/Users/zhangjunfei/WorkBuddy/2026-10-29-15-06-17/hirank_vs_v19_borrowing.html) |

| MORE（arXiv 2609.07273，MOMO/CIKM 2026） | **借鉴有限，不进下一步策略**——任务发散度不匹配（他们 13 个高发散社交/互动任务收益 +1.2~1.6%，我们仅 ctr/cvr 2 个同漏斗任务；Click 档 +0.44% 全表最小）；六大组件四个与 PLE/PPNet/5 条分序列重叠或被超越，唯一缺口"任务 query 读序列"无 proto 需代码级立项（同 HiRank-D）。可拿走：GAUC 按任务评估（同借鉴 B）、"防污染>加容量"洞察 | P2/P3 登记：task-query 读出最小探针；仅当场景辅助任务（bijia/haojia/trend）复活为多任务时才立项 MORE-lite。动画 [more_multitask_vs_v19_borrowing.html](/Users/zhangjunfei/WorkBuddy/2026-10-29-15-06-17/more_multitask_vs_v19_borrowing.html) |

诚实边界：三文收益数字均为作者自报、跨域/单业务；搬我们数据可能过不了 +0.10pp 闸，必须拆单变量臂逐个验。

______________________________________________________________________

## §7 当前状态与下一步（2026-11-11）

### 7.1 seed 机制与执行单（已就绪）

- 机制：环境变量 `TORCH_MANUAL_SEED` / `NUMPY_MANUAL_SEED` / `EVAL_SEED`（默认均 **42**，即历史全部实验的固定种子），**不改代码**（[READOUT_20261111_P0_FIRST_BATCH.md](READOUT_20261111_P0_FIRST_BATCH.md) §六）；
- 训练脚本 seed 版已建：`sql/2609/shell/home_flow_2604_sorter_train_export_multifusion_seed`（原文件未动；`SEED=42` 硬编码一行改 43/44；产物路径 `${train_ymd}_seedN/`；日志头有 `[seed]` 锚）；
- 配对纪律：同一 seed 下 base 与臂必须同 env 各跑一次。

### 7.2 符号闸结果（2026-11-11 20:50 收账）

**闸 PASS，P0-2a 过闸（宣称级）**。3-seed 配对 Δ 账（20261109 窗，eval All-ranks）：

| seed     | Δctr          | Δcvr      |
| -------- | ------------- | --------- |
| 42       | +0.2395pp     | +0.0436pp |
| 43       | +0.2086pp     | −0.0219pp |
| 44       | +0.3157pp     | +0.0031pp |
| **mean** | **+0.2546pp** | +0.0082pp |

预注册对表全过：3/3 同号 ✓、|mean| 0.2546 ≥ 0.15pp ✓、seed43 差异性检查过（种子生效）✓、train 批 3/3 同向 ✓。**无需第 4 seed**（"模棱两可才决胜"分支未触发）。cvr 中性（+/−/+，mean ≈ 0）——收益在 ctr 侧，与 ts 近因机制自洽。

P0-4 已拍板（哨兵 triage）：p04@43 Δctr=+0.0655pp 正向、量级未升级 → **并组合臂**（②号方案落地）；不收全闸不宣称。

### 7.3 下一步队列

1. ~~清 train==eval 债~~ **已清**（20261111 用户核查确认）→ P0-2a 可对外宣称；
1. **p02a 定版合并新基线**（`v6f_p02a_seqts` 取代 kv_fusion 成为对照基线）；
1. P0-4 已拍板=并组合臂 → 下一梯队在 p02a 新基线上测 p02a+p04 叠加（1 run，配对 p02a@42/43 已在账）；
1. P1 队列 + P0-1b 试探档 + FG 需求单（R1/R2）照旧——**P1-6r 已重启（SQL-13：H_scale 百分制确认 + 非零段 cvr 严格单调，泄漏已排除）**：convert_probability 分桶 raw_feature（boundaries 1e-08/1/5/10/20/40/60/80/100，emb=8，**只作序信号不作概率**；0 桶 = **源头 NULL 填充（未打分/覆盖不足）+ 非单品 N/A**，SQL-16R/17 定谳，非真实 0 分——缺分=高转化人群规则，注意漂移敏感），config `home_flow_2608_v19_multiscene_v6f_p02a_p16cpbucket.config` 已生成+冒烟（对照 = p02a 新基线），与 p02a+p04 组合臂各需 1 run（预算 10/10 用满）——**扩预算或排序让位等拍板**；
1. 零预算随手项：HiRank 借鉴 A（eRank 审计脚本）/ 借鉴 B（AUDIT SQL 加用户分组 GAUC，[AUDIT_SQL.md](AUDIT_SQL.md)）。

______________________________________________________________________

## §8 演示与讲义（HTML，浏览器直接打开）

| 文件                                                                                                                                    | 内容                                                       |
| --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [din_4way_vs_dotproduct_same_cate.html](/Users/zhangjunfei/WorkBuddy/2026-10-29-15-06-17/din_4way_vs_dotproduct_same_cate.html)         | 同品类下 4 路打分 vs 单点积差距几何（7 步动画 + 碰撞实验） |
| [relation_attention_vs_din_borrowing.html](/Users/zhangjunfei/WorkBuddy/2026-10-29-15-06-17/relation_attention_vs_din_borrowing.html)   | Relation 论文 → 我们 DIN 的借鉴映射                        |
| [hirank_vs_v19_borrowing.html](/Users/zhangjunfei/WorkBuddy/2026-10-29-15-06-17/hirank_vs_v19_borrowing.html)                           | HiRank → v19 借鉴映射（含消融数字）                        |
| [fixed_seed_comparable_vs_significant.html](/Users/zhangjunfei/WorkBuddy/2026-10-29-15-06-17/fixed_seed_comparable_vs_significant.html) | 固定种子下"可比 vs 显著"辨析（符号闸动机）                 |

______________________________________________________________________

## §9 文档地图（链接索引）

### 9.1 主线（当前有效）

| 文档                                                                     | 角色                                                                  |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| **本文件 MASTER.md**                                                     | ⭐ 唯一入口：最新最全结论与进展                                       |
| [PLAN_CTR_NEXT_20261107.md](PLAN_CTR_NEXT_20261107.md)                   | 主线方案：6 臂变更单（行号级）、判据、SQL-8~11 读数判决、边界定标终版 |
| [READOUT_20261111_P0_FIRST_BATCH.md](READOUT_20261111_P0_FIRST_BATCH.md) | P0 第一梯队读数与判决 + seed 执行单                                   |
| [SUMMARY_20261030_ALL_RUNS.md](SUMMARY_20261030_ALL_RUNS.md)             | 20261030 窗 12 跑一张表                                               |
| [AUDIT_SQL.md](AUDIT_SQL.md)                                             | 审计口径 SQL（probs_ctr/probs_cvr 口径锚）                            |

### 9.2 证据底稿（append-only）

| 文档                                                                                                                                                                                              | 角色                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| [SQL_EVIDENCE_CHAIN_20261103.md](SQL_EVIDENCE_CHAIN_20261103.md)                                                                                                                                  | SQL-1~7 取证链（kv MAP 类型、F-B 证伪）                                                                                     |
| [SQL_EVIDENCE_CHAIN_CONVERT_PROB_20261112.md](SQL_EVIDENCE_CHAIN_CONVERT_PROB_20261112.md)                                                                                                        | **SQL-12~17 convert_probability 勘验链**（SQL 原文+结果表+结论；泄漏排除→H_scale→构成分解→冷启动排除→填充实锤→NULL=未打分） |
| [SQL_EVIDENCE_CHAIN_SID_20261104.md](SQL_EVIDENCE_CHAIN_SID_20261104.md)                                                                                                                          | SID 专题取证链                                                                                                              |
| [READOUT_20261105_JUDGE_SYNTH.md](READOUT_20261105_JUDGE_SYNTH.md)                                                                                                                                | 判决实验四臂读数（T0−F1b≈0 归因）                                                                                           |
| [READOUT_20261030_EXPOSURE_FAMILY.md](READOUT_20261030_EXPOSURE_FAMILY.md)                                                                                                                        | exposure 族 +0.52pp 读数                                                                                                    |
| [READOUT_20261030_T0_T3.md](READOUT_20261030_T0_T3.md) / [READOUT_20261030_F1_SEQATTN.md](READOUT_20261030_F1_SEQATTN.md)                                                                         | 20261030 窗各臂读数                                                                                                         |
| [UNUSED_FEATURES_FG_V5_20261105.md](UNUSED_FEATURES_FG_V5_20261105.md)                                                                                                                            | 81 未用特征清单 + DDL 双表定谳（§六）                                                                                       |
| [GEN_P0_FIRST_BATCH_20261109.md](GEN_P0_FIRST_BATCH_20261109.md)                                                                                                                                  | P0 四 config 生成记录与验证                                                                                                 |
| [JUDGE_EXP_DOWNSTREAM_SYNTH_20261104.md](JUDGE_EXP_DOWNSTREAM_SYNTH_20261104.md) / [\_v2](JUDGE_EXP_DOWNSTREAM_SYNTH_20261104_v2.md) / [REVIEW\_…](REVIEW_JUDGE_EXP_DOWNSTREAM_SYNTH_20261104.md) | 判决实验方案 + 对抗式审核                                                                                                   |
| [PLAN_CTR_NEXT_20261105.md](PLAN_CTR_NEXT_20261105.md)                                                                                                                                            | 旧版路线图（已被 1107 版吸收，留档）                                                                                        |
| [CONFIG_GUIDE.md](CONFIG_GUIDE.md)                                                                                                                                                                | config 书写指南                                                                                                             |

### 9.3 历史专题归档（阶段工作底稿）

| 主题               | 文档                                                                                                                                                                                                                                                                             |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 标签泄漏           | [LABEL_LEAK_FIX.md](LABEL_LEAK_FIX.md) / [LABEL_LEAK_FIX_V2.md](LABEL_LEAK_FIX_V2.md) / [LABEL_LEAK_FIX_FINAL.md](LABEL_LEAK_FIX_FINAL.md)                                                                                                                                       |
| trend 数据质量     | [TREND_DATA_CRITICAL_ISSUE.md](TREND_DATA_CRITICAL_ISSUE.md) / [TREND_DATA_QUALITY_AUDIT.md](TREND_DATA_QUALITY_AUDIT.md) / [TREND_DUPLICATE_ANALYSIS.md](TREND_DUPLICATE_ANALYSIS.md) / [TREND_DUPLICATE_FIX_REPORT.md](TREND_DUPLICATE_FIX_REPORT.md)                          |
| CVR/校准           | [CVR_CALIBRATION_ISSUE.md](CVR_CALIBRATION_ISSUE.md) / [CVR_CALIBRATION_CORRECTED.md](CVR_CALIBRATION_CORRECTED.md) / [CALIBRATION_ANALYSIS.md](CALIBRATION_ANALYSIS.md) / [CVR_AUX_TASK_ANALYSIS.md](CVR_AUX_TASK_ANALYSIS.md)                                                  |
| AUC/GAUC           | [AUC_GAUC_EXPLANATION.md](AUC_GAUC_EXPLANATION.md) / [AUC_GAUC_DETAILED_ANALYSIS.md](AUC_GAUC_DETAILED_ANALYSIS.md) / [GAUC_DECAY_OPTIMIZATION.md](GAUC_DECAY_OPTIMIZATION.md)                                                                                                   |
| 序列/Transformer   | [SEQUENCE_ANALYSIS.md](SEQUENCE_ANALYSIS.md) / [SEQUENCE_ANALYSIS_REVISED.md](SEQUENCE_ANALYSIS_REVISED.md) / [TRANSFORMER_POS_READOUT_ABLATION_20261102.md](TRANSFORMER_POS_READOUT_ABLATION_20261102.md) / [F2_MULTISEQ_FUSION_DESIGN.md](F2_MULTISEQ_FUSION_DESIGN.md)        |
| target-aware 演进  | [TARGET_AWARENESS_FIX_EVAL_20261101.md](TARGET_AWARENESS_FIX_EVAL_20261101.md) / [CLARIFICATION_DEGENERATION.md](CLARIFICATION_DEGENERATION.md)                                                                                                                                  |
| F1/F2 事故与审计   | [F1_NAN_ROOT_CAUSE_20261101.md](F1_NAN_ROOT_CAUSE_20261101.md) / [F1_F2_DELIVERY_AUDIT_20261031.md](F1_F2_DELIVERY_AUDIT_20261031.md) / [BUG_FIX_MLP_DIMENSION.md](BUG_FIX_MLP_DIMENSION.md)                                                                                     |
| 数据核查           | [DATA_ANALYSIS_20261003.md](DATA_ANALYSIS_20261003.md) / [DATA_CLARIFICATION.md](DATA_CLARIFICATION.md) / [DATA_ISSUE_ANALYSIS.md](DATA_ISSUE_ANALYSIS.md) / [DATA_SAMPLING_ANALYSIS.md](DATA_SAMPLING_ANALYSIS.md) / [DATA_VALIDATION_COMPLETE.md](DATA_VALIDATION_COMPLETE.md) |
| Phase1 / SID       | [PHASE1_EXPERIMENT.md](PHASE1_EXPERIMENT.md) / [PHASE1_EXECUTION.md](PHASE1_EXECUTION.md) / [PHASE1_FINAL_SUMMARY.md](PHASE1_FINAL_SUMMARY.md) / [SID_APPLICATION_PLAN_20261104.md](SID_APPLICATION_PLAN_20261104.md)                                                            |
| 评审记录           | [ADVERSARIAL_REVIEW.md](ADVERSARIAL_REVIEW.md) / [ADVERSARIAL_REVIEW_20261029.md](ADVERSARIAL_REVIEW_20261029.md) / [REVIEW_RESPONSE.md](REVIEW_RESPONSE.md) / [REVIEW_TREND_CVR_SWAP_PLAN.md](REVIEW_TREND_CVR_SWAP_PLAN.md) / [EXPERT_ANALYSIS.md](EXPERT_ANALYSIS.md)         |
| 特征与优化（早期） | [FEATURE_ANALYSIS.md](FEATURE_ANALYSIS.md) / [OPTIMIZATION_ANALYSIS.md](OPTIMIZATION_ANALYSIS.md) / [P0_FEATURE_ADDITION.md](P0_FEATURE_ADDITION.md) / [P0_FEATURE_CRITERIA.md](P0_FEATURE_CRITERIA.md) / [UNUSED_FEATURES_LIST.md](UNUSED_FEATURES_LIST.md)                     |
| 其他               | [AUX_ABLATION_PLAN.md](AUX_ABLATION_PLAN.md) / [TREND_CVR_SWAP_PLAN.md](TREND_CVR_SWAP_PLAN.md) / [NEXT_STEPS.md](NEXT_STEPS.md) / [FIX_SUMMARY.md](FIX_SUMMARY.md) / [README.md](README.md)（v19 立项设计，历史）                                                               |

______________________________________________________________________

## §10 债务清单（未清）

| 债                                           | 内容                                                                                                                              | 影响                                                                           |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| ~~train==eval 债~~                           | ~~训练与 eval 口径未隔离~~ **20261111 清账**：用户多次核查，train 与 eval 结论一致                                                | 已清，不再阻塞宣称                                                             |
| ~~sampler cluster 种子~~                     | ~~`launch_sampler_cluster` 是否吃 torch 种子未核验~~ **20261111 大幅缓解**：seed42 复跑跨提交时间 bit 级一致 → 采样顺序种子可复现 | 剩余风险很小；seed43 差异性检查兜底                                            |
| P0-4 组合臂未验                              | 哨兵 triage 正（2 seed mean +0.073pp）但叠加收益未验                                                                              | 下一梯队 1 run 测 p02a+p04 vs p02a                                             |
| P0-2b 三因子捆绑                             | time_gate×4 + 维度变化 + grad_clipping 搭车                                                                                       | 已弃不追查（弃置成本最低），留档                                               |
| convert_probability 缺分人群高转化（已收档） | SQL-17 定谳 NULL=**(a) 未打分/覆盖不足**（深度 39%/无历史率 6.2×，假说 b 拒绝）；勘验链 12→17 全收档                              | FG（P3）终稿：−1 哨兵**必须** + 打分覆盖扩展建议（浅历史人群）+ 缺分高转化反馈 |
| 组合臂未验                                   | 判决实验 C1K1 组合臂 2 run、P0 组合臂                                                                                             | 预算内可选                                                                     |

______________________________________________________________________

## §11 更新日志

| 日期             | 更新                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-11-11       | 建立本文件；整合至 P0 第一梯队读数判决 + seed 执行单（最新进展：等方案 A/B/C 拍板）                                                                                                                                                                                                                                                                                                                                                                  |
| 2026-11-11 16:25 | seed=42 复跑验证：bit 级确定性成立 + seed 脚本正确性通过；Δ_42 = +0.2395pp（符号闸 1/3 同号）；sampler 债务缓解；新增 seed43 差异性预注册检查                                                                                                                                                                                                                                                                                                        |
| 2026-11-11 18:00 | MORE 论文（CIKM 2026）借鉴评估：借鉴有限，不进下一步策略，登记 P2/P3；主线不变（P0-2a 收闸 → P0-4 拍板 → P1/FG 需求单）                                                                                                                                                                                                                                                                                                                              |
| 2026-11-11 20:50 | **符号闸 PASS：P0-2a 过闸（宣称级）**——3-seed Δctr +0.2395/+0.2086/+0.3157pp（mean +0.2546pp，3/3 同号）；seed43 差异性检查过；无需第 4 seed；下一步：清 train==eval 债 → p02a 定版新基线 → P0-4 拍板                                                                                                                                                                                                                                                |
| 2026-11-11 21:05 | train==eval 债清账（用户多次核查 train/eval 结论一致，记入长期记忆）→ P0-2a 宣称解锁；SQL-12（convert_probability 泄漏勘验）交付；哨兵 1 run 释义 + P1/P0-1b/FG 需求单方案                                                                                                                                                                                                                                                                           |
| 2026-11-11 22:10 | SQL-12 判决：convert_probability 泄漏排除（无近完美校准桶）但值域无界（g 桶 avg_cp=52.9）→ P1-6 as-is 暂停；SQL-13（百分制 vs 无界打分定标）已给，判读图预注册（PLAN §9.10/§9.11）                                                                                                                                                                                                                                                                   |
| 2026-11-12 12:21 | 文档体系补链（用户指正）：建 [SQL_EVIDENCE_CHAIN_CONVERT_PROB_20261112.md](SQL_EVIDENCE_CHAIN_CONVERT_PROB_20261112.md)（SQL-12~17 原文+结果+结论一文收档）；MASTER §3 扩账至 SQL-1~17 + convert_probability 终局结论、§9.2 登记、§7.3 旧措辞（"真实 0 分"/9-10 预算）修正                                                                                                                                                                           |
| 2026-11-12 11:36 | SQL-17 判决：NULL 语义定谳 = **(a) 未打分/覆盖不足**——NULL 桶 vs 低分桶(0,5\]：深度 158.4 vs 402.9（39%）、no_hist 2.69% vs 0.44%（6.2×）、cvr 0.1450 vs 0.0681（2.13×），画像显著不同形；假说 (b) 打分为 0→NULL 强烈拒绝（应近似最低真分桶，实际差 2.5×/2.13×/6.2×）；有分段 b→c→d cvr 单调自检过；互证：非单品 NULL 200,649=非单品总数（与 SQL-14 逐位）。**convert_probability 勘验链收档**（SQL-12→17），FG 走覆盖路线，P1-6r 不动（PLAN §9.12） |
| 2026-11-12 11:12 | SQL-16R 判决（源头表 dt=20261030，2,691,204 行闭合）：NULL 43.88%、zero_cnt=**0**、min_cp=1.1 → 命中"缺省填充实锤"分支且更强：编码 0 桶 **100% NULL 填充**，"真实 0 分"语义撤销（0 桶二拆=单品缺分+非单品 N/A）；零点反转终局改判**缺分人群高转化**（打分器有分段 b→i 单调无质量问题）；NULL 语义 (a) 未打分 vs (b) 打分为 0 二分待 SQL-17 判；FG −1 哨兵建议→**必须**；P1-6r 结构判据不动、0 桶注释改定"0=缺分填充"（PLAN §9.12）                   |
| 2026-11-12 11:03 | 源头口径补勘（用户质询）：fg_v5.json 1186 特征中 998 个 default_value=0（含 convert_probability）→ **编码表 0 桶=真实 0∪缺省填充不可分辨**，SQL-13 无 NULL 仅证编码后；口径纪律固化（模型所见→编码表/源头语义→源头表）；SQL-16R（源头 NULL/0 率定标）判读图预注册（PLAN §9.12），原 hist_band 分层顺延 SQL-17 且可能须在真实 0 子集重跑；P1-6r 判据不动、0 桶语义注释待源头定标                                                                      |
| 2026-11-11 23:57 | SQL-15 判决：零分段 avg_item_click_24h 136.7（有分段 45%）、no_hist_rate 2.90% vs 0.25%（11.7×）→ 浅历史倾斜证实；但**窄义冷启动算术排除**（97.1% 有历史，无历史子集 cvr=100% 时均值上限 0.1276 < 实测 0.1315）→ 残余反转必须在有历史人群内部（①深度梯度 vs ②真零点反转，SQL-16 判别）；FG 反馈稿定稿，P1-6r 结构判据不动（PLAN §9.12）                                                                                                              |
| 2026-11-11 23:51 | P0-4 哨兵 triage（p04@43 vs base@43）：Δctr=**+0.0655pp**（Δcvr −0.0009pp，train 批 +0.073pp 同向，eval set 逐位同）→ 两 seed 账 42=+0.081/43=+0.0655，2/2 同号均灰区 mean +0.073pp → 命中预注册"正→并组合臂"分支：**P0-4 降级组合臂因子**，不收全闸；run 预算 10/10 用满，P1-6r/组合臂各需 1 run 待拍板（READOUT §九）                                                                                                                              |
| 2026-11-11 23:45 | SQL-14 判决：**cp>0 100% 单品**，非单品（促销 0.209/福利 0.276/文章≈0）结构性 N/A 恒 0 → 零桶构成效应证实（2.55× 断崖解释到 1.30×）；单品内残余反转仍在（cp=0 单品 0.1315 > 最高分桶 0.1266）→ 冷启动/打分口径待查；P1-6r 结构不变（item_type 交叉消歧），FG 备注升级，可选 SQL-15（PLAN §9.12）                                                                                                                                                     |
| 2026-11-11 23:15 | 语义更正（用户域知识）：convert_probability=真实预估出单概率百分制（0=预估 0 分，上限 100），**非缺省填充值**→撤销"default/missing"措辞；0 独立成桶结构不变（断崖 2.55×，并桶淹没 (0,1\] 段）；零点反转（0 分 cvr 全表最高）改判上游打分质量待勘验（假说①打分口径/窗不一致 ②特殊流量）；缺省填 0 规则列 FG 备注（建议 −1 哨兵）；判读图盲区解释性裁决已透明化（PLAN §9.12）                                                                          |
| 2026-11-11 23:40 | SQL-13 判决：**H_scale 百分制确认**（j+k=0，计数 90,988,963 闭合）+ 非零段 b→i cvr 严格单调 → **P1-6r 重启**（分桶序信号，boundaries 1e-08/1/5/10/20/40/60/80/100）；零桶 default/missing（cvr 最高 0.148）独立成桶；config `v6f_p02a_p16cpbucket.config` 生成+冒烟 PASS；排期与 P0-4 哨兵争最后 1 run（PLAN §9.12）                                                                                                                                 |
