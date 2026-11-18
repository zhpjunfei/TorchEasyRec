# SID（语义ID）应用实现方案 v1（2026-11-04）

> **信息源对账**（本文 = 三路信息合成）：
> ① 钉钉《SID（语义ID）应用文档》（正鸿，10-14 编辑，5052 字）——已读：大纲全结构 / §一动机与两大落地方向 / §2.6 在线生成要点 / §4.1 u2i2sid2i 要点+配置 / §4.2 实时 u2i 配置 / 参考链接；**未读到**：§2.1 选型结论、§4.5 路径对比、§五实施步骤全文（浏览器标签页已失效，见 §10）。
> ② 外部证据：AKT-Rec（arXiv:2605.23310）、Snapchat SID（arXiv:2604.03949）、YouTube SPM-SID。
> ③ v19 实验线读数：序列线全线关闭（瓶颈在特征质量）、曝光族 +0.52pp（唯一开着的正向候选）、SQL-1~4 取证链（部分匹配 72.3%、q−s 残差工作面）、方法论（单变量/固定 seed/±0.5pp/分桶评估/SQL 逐条给）。
>
> **标注纪律**：【原始证据】【事实读数】【推断】三层分开；工作量为**人日量级估算，非排期承诺**。

______________________________________________________________________

## 追踪入口（相关文档链接）

| 文档                                                                                                                              | 内容                                                                                       |
| --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| [SQL_EVIDENCE_CHAIN_SID_20261104.md](SQL_EVIDENCE_CHAIN_SID_20261104.md)                                                          | **SID 线 SQL 取证链（唯一 SQL 追踪处）**：SQL-7/8/9 原文 + 结果表 + 读数 + 判定、P0 链结论 |
| [SQL_EVIDENCE_CHAIN_20261103.md](SQL_EVIDENCE_CHAIN_20261103.md)                                                                  | 原链 SQL-1~6（T0-T3 消融取证线，已收档）                                                   |
| [sid_rq_kmeans.config](sid_rq_kmeans.config)                                                                                      | P1 RQKMeans 训练配置草案 v2（title_vector 128 维输入，codebook [256]³）                    |
| [semantic_id_rqvae_v19_application.html](/Users/zhangjunfei/WorkBuddy/2026-11-04-13-16-13/semantic_id_rqvae_v19_application.html) | RQ-VAE 原理动画 + AKT-Rec 消融表 + v19 接入映射                                            |

## 0. 一句话结论

**三段式落地，P0 取证先行**：P1 生成管线（基建已有，照钉钉文档）→ P2 四路径召回（文档主线）→ P3 精排特征（v19 三档）。每段预注册门槛，不过门槛不进下一段。SID 与 v19 现有正向候选（曝光族 seed43）**并行不冲突**（不同特征域），训练资源排队即可。

## 1. 全景架构（数据流）

```
商品图/文/视频 ──► 万物向量(qwen3-vl-embedding, value_dim=1152/2560)
                        │  (PAI-FeatureStore 托管, fg_mode=normal, 特征名 item:embedding)
                        ▼
              量化器(RQKMeans 或 RQVAE, TorchEasyRec sid_* 工具链)
                        │  3~4 层离散码, 高碰撞设计(前缀=语义簇)
                        ▼
              item_sid_map (item_id → (c1,c2,c3[,c4]))
                        │
        ┌───────────────┼──────────────────────┐
        ▼               ▼                      ▼
   Step2 关联表      Step3 召回(4 路径)      精排特征(v19)
   sid_i2i_similar   路径一 u2i2sid2i 多跳   3A SID 码特征(config-only)
   U→SID 列表        路径二 实时 u2i         3B 簇匹配特征(打 72.3% 工作面)
                     路径三 属性聚合         3C CGAE-lite(二期)
                     路径四 sid2 直召
                        │
              评估闭环：分桶离线读数 → 线上 A/B
```

## 2. 信息源对账（关键一致性检查）

| 议题            | 钉钉文档                                     | 外部证据                                                    | v19 读数                        | 采纳结论                                                   |
| --------------- | -------------------------------------------- | ----------------------------------------------------------- | ------------------------------- | ---------------------------------------------------------- |
| SID 落地方向    | ①特征进精排 ②召回索引（本文重点）            | Snapchat：精排辅助特征已上线；YouTube：冷启动最优           | 特征质量是瓶颈；部分匹配 72.3%  | **两线都做**：召回照文档，精排按 3A→3B→3C                  |
| 量化器          | RQVAE vs RQKMeans（§2.1 有专节，结论未读到） | RQ-VAE 主流；Snapchat：码本塌缩是头号坑（STE/多模融合缓解） | —                               | **先 RQKMeans 打通链路，后评估是否换 RQVAE**（§4.2，推断） |
| 簇嵌入/头尾迁移 | 未见（文档聚焦生成+召回）                    | AKT-Rec：簇嵌入救尾部（GAUC −1.20%），stop-grad 防污染      | 尾部 item_id embedding 噪声假设 | 3C（二期）立项候选                                         |
| 评估            | 未见离线评估设计（待确认 §五）               | AKT-Rec 尾部 GAUC 被 TailNet 反超 → 不能只看整体            | ±0.5pp 带/单变量/分桶/固定 seed | **补 v19 预注册门槛**（§8）                                |

## 3. Phase 0：数据取证（SQL 逐条给，纪律沿用 SQL 链）

**目的**：立项前先量化"长尾问题有多大"和"学习簇的边际"。SQL 一条一条给，结果回贴后续写本节。
**表/口径**（沿用 SQL-1 定谳）：`mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set`，`dt='20261030'`；点击过采样口径，**只解读相对差**。

| SQL                   | 回答什么                                                                              | 状态                                                                                                       |
| --------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| SQL-7（见附录 A，v2） | item 活跃度分位分布：长尾 item 占比 / 样本占比 / 桶内 CTR——长尾问题是否成立           | **✅ 完成（2026-11-04），判定：长尾成立**                                                                  |
| SQL-8（见附录 B）     | 尾部低 CTR 机制诊断：活跃度 × 匹配层级交叉（缺行为借力 vs 商品固有）→ 定 3B/3C 优先级 | **✅ 完成（2026-11-05）：判定②触发 → 3C 优先、3B 条件化；机制修正=粒度×活跃度交互（详见链文档 §2.3）**     |
| SQL-9                 | 3_hit_cate3 弱证据带内剂量效应（候选 B eval 覆盖预估推后）                            | **✅ 完成（2026-11-05）：判定①触发 → 3B=强度形态+尾部阈值≥3；3C 主线不变（详见链文档 §3.4，P0 链已收档）** |

> 注：SQL 证据的**唯一追踪处 = [SQL_EVIDENCE_CHAIN_SID_20261104.md](SQL_EVIDENCE_CHAIN_SID_20261104.md)**（本节/附录为快照，原文+结果+读数全文以链文档为准，随链滚动更新）。原链 SQL-1~6 已收档于 [SQL_EVIDENCE_CHAIN_20261103.md](SQL_EVIDENCE_CHAIN_20261103.md)（SQL-6 于 20261104 定谳：F-B kv 版证伪）。

### 3.1 SQL-7 读数（2026-11-04 完成）

对账【事实读数】：samples 合计 3,077,988，与 SQL-2 总量逐位一致 ✓；items 合计 52,486。

| item_activity_bucket | n_items | item_ratio | samples   | sample_ratio | ctr     |
| -------------------- | ------- | ---------- | --------- | ------------ | ------- |
| a_01_lt10            | 30,313  | 57.75%     | 72,676    | 2.36%        | 0.35415 |
| b_02_10_50           | 10,962  | 20.89%     | 271,513   | 8.82%        | 0.36156 |
| c_03_50_200          | 7,786   | 14.83%     | 782,549   | 25.42%       | 0.37995 |
| d_04_200_1000        | 3,052   | 5.81%      | 1,187,757 | 38.59%       | 0.39076 |
| e_05_ge1000          | 373     | 0.71%      | 763,493   | 24.80%       | 0.36398 |

读数：

1. **长尾问题成立【判定，对照预注册两条】**：a+b = 78.64% item_ratio（>20% ✓）且 11.18% sample_ratio（>10% ✓，压线过）→ **P3C（CGAE-lite）优先级上调**。
1. 头部集中度【事实读数】：d+e 仅 6.52% 的 item 承载 63.39% 的样本——比 AKT-Rec 引言的天猫口径（95.8% 曝光\<10）温和但同构；a 桶平均仅 2.4 样本/item，item_id embedding 基本学不动。
1. CTR 梯度【事实读数】：a→d 单调升（0.354→0.391，+3.66pp），e 桶回落（0.364，vs d −2.68pp）。长尾桶 CTR 更低**与"尾部 embedding 噪声"假设相容，但不构成证明**——这是样本标签率（商品固有质量 + 模型打分质量混合），非模型排序读数【推断边界】。
1. 异常记录【事实读数】：e 桶回落（373 个超头部 item CTR 反低）——疑似运营坑位/大流量稀释效应，与 SQL-2 的 0_no_seq 异常同级记录，不过度解读。
1. 稀释面【推断】：3C 受益面（a+b）只占 11.2% 样本 → 效应进整体 AUC 必被稀释，**尾部桶主判据**再次被证实必要；整体 AUC 角色维持"护栏（不掉）"。

**门槛结论（预注册 → 已触发）**：长尾成立 → 3C 优先级上调；SQL-8 已裁定 **3C 优先、3B 条件化**（机制=粒度×活跃度交互）；SQL-9 补定 **3B=强度形态+尾部阈值≥3**。执行序：3A → 3C → 3B。

## 4. Phase 1：SID 生成管线（照钉钉文档 Step 1，基建已有）

### 4.1 Embedding 提取（文档 §2.0/§2.6，2026-11-05 全文补读后定稿）

- 服务：PAI-FeatureStore「万物向量」（LLM 多模态 Embedding），扫描文本+图像/视频帧全量产出 item embedding，落 FeatureDB。【原始证据：文档 §2.0】
- **模型二选一（文档 §2.0 定稿）**：`qwen3-vl-embedding`（**2560 维**，独立向量+融合向量 `mix_embedding_vec`）或 `tongyi-embedding-vision-plus`（1152 维，仅独立向量）。**SID 输入推荐融合向量**（多模态映射同一语义空间，语义更完整）→ 即 **value_dim=2560**；仅用 tongyi 则 1152。示例 512 仅占位禁用。
- 数据流程（文档 §2.0 五步）：①多模态源表（MaxCompute：item_id/text/image/image_array/video）→ ②注册大模型调用信息（MULTI_MODAL_EMBEDDING，EnableFusion=是）→ ③注册特征视图（LLMEmbedding 变换 → mix_embedding_vec）→ ④同步触发提取（实时 DataHub+Flink / 存量 Overwrite / 增量 Merge / 直接同步已有向量）→ ⑤导出 embedding 样本接 §2.2。
- 成本【原始证据】：LLM Gateway 自带智能缓存/限流/自动重试，存量+增量提取约 **0.25 元/百万 Tokens**。
- 对齐要点（文档 §2.6）：①特征名 `item:embedding` 与训练 config `raw_feature{expression:"item:embedding"}` 一致（fg_mode="normal"）；②**离在线共用同一份 checkpoint/码本**；③在线请求 EMBEDDING_DIM=value_dim；④实时 SID 即写 `item_sid_map`。

### 4.2 量化器选型（文档 §2.1 结论未读到，以下为独立建议【推断】）

| 维度              | RQKMeans（残差 KMeans 逐层聚类）   | RQVAE（残差量化 VAE）                  |
| ----------------- | ---------------------------------- | -------------------------------------- |
| 原理              | 每层对残差做 KMeans，码字=聚类中心 | 编码器+码本+重建损失端到端训练         |
| 训练复杂度        | O(L·N·K·d·iters)，CPU/Spark 可跑   | O(N·d·h·epochs)，需 GPU+调参           |
| 码本塌缩风险      | 无（聚类天然用满）                 | 有（Snapchat 头号坑，需 STE/多模融合） |
| 表达力            | 中（量化误差逐层累积）             | 强（重建目标自适应）                   |
| 工程量            | 小                                 | 中                                     |
| TorchEasyRec 支持 | sid_rqkmeans                       | sid_rqvae                              |

**推荐（文档 §2.1 已定论，与独立建议一致）【原始证据】**：**首期 RQKMeans 快速产出码本验证链路**（FAISS KMeans 逐层残差聚类、CPU 单进程、码本一次性拟合）；需要图文双视图对比学习（InfoNCE）或多卡 GPU 训练时再切 RQVAE。SQL 链粒度红线（叶簇细于 cate3、对齐 spu）与文档码本判据的结合：

| 判据                                                         | 来源                                           | 用法                                                                       |
| ------------------------------------------------------------ | ---------------------------------------------- | -------------------------------------------------------------------------- |
| 层语义 ≈ 一/二/三级类目个数，支持非均匀（如 [256,512,1024]） | 文档 §2.1                                      | 层宽初设                                                                   |
| **unique_sid_ratio（无冲突率）> 70%**                        | 文档 §2.1（与 Snapchat unique~70% 平台期互证） | 训练后实测回调 codebook 层宽                                               |
| 亿级物品参考 [8192,8192,8192]                                | 文档 §2.1                                      | 大池锚点                                                                   |
| 叶簇（整码 tuple）≈ spu 粒度、细于 cate3                     | SQL 链 §2.3/3.4 红线                           | 簇粒度抽查（簇内 cate3/spu 一致性）；粗粒度借力由 c1/c2 层承担（层级共享） |

**全量商品池规模是唯一未定输入**——估算表：≤100 万 → [1024,1024,1024]；100 万~1000 万 → [2048]³~[4096]³；亿级 → [8192]³；首跑可先 [256,256,256] 验证管线再按 unique_sid_ratio 回调。

### 4.3 训练与生成（命令已定稿，文档 §2.4）

- **输入格式（§2.2）**：`item_id(string) + embedding(array<double>)`（= 万物向量导出的 mix_embedding_vec，维度=value_dim），fg_mode: FG_DAG 直读数组列；RQVAE 对比学习才需 pair\_\* 列。**首跑输入源已定（2026-11-05）**：`title_vector`（128 维文本语义向量，STRING 逗号分隔 7 位小数，表 `feature_mall_feed_rec_flow_item_title_embedding_string_v5_offline`）——用 `raw_feature{expression:"item:title_vector" value_dim:128 separator:","}` 直读（v10 config 已跑通同款读法），无需 SQL 转 array；升级万物向量 2560 时换 FG_DAG 数组列口径。
- **离线训练**：`OMP_NUM_THREADS=$(nproc) torchrun --nproc-per-node=1 -m tzrec.train_eval --pipeline_config_path sid_rq_kmeans.config --train_input_path .../*.parquet --model_dir experiments/sid_rqkmeans`（约束：num_epochs=1、save_checkpoints\_\*=0、仅 CPU 单进程）。草案 config：**[v19/sid_rq_kmeans.config](sid_rq_kmeans.config)**（2026-11-05 新增）。
- **离线批量出码**：`torchrun ... -m tzrec.predict ... --checkpoint_path .../model.ckpt-{step} --predict_output_path .../sid_output --reserved_columns item_id`。读 ODPS：`data_config.dataset_type=OdpsDataset` + `odps://{project}/tables/{table}/{partition}` + ODPS_ENDPOINT。
- **输出（§2.5）**：`codes=array<int64>`（长度=码本层数）+ 透传 item_id；自动指标 mse / rel_loss / **unique_sid_ratio**。落表 `item_sid_map(item_id, sid_l1, sid_l2, sid_l3, sid_path="241_134_78")` 写回 FeatureStore/MaxCompute 供 P2/3A 消费。
- 在线：EAS 部署量化服务（TorchEasyRec Processor + eas_prediction.TorchRecRequest，示例 `eas_request_for_sid.py`；特征名固定 `embedding`/list<float>，批量返回 codes），新商品入库即算 SID（冷启动路径）。
- 增量：全量重刷 T+1（存量 Overwrite / 增量 Merge，文档 §2.0 ④）；码本冻结后可服务数月（YouTube：6 个月前 encoder 仍有效【原始证据】）。

### 4.4 质量验收（P1 门槛）

| 指标                      | 门槛                                                         | 依据                                                |
| ------------------------- | ------------------------------------------------------------ | --------------------------------------------------- |
| 无冲突率 unique_sid_ratio | **>70%**（predict 自动输出），死码率监控                     | 文档 §2.1 判据 + Snapchat ~70% 平台期【原始证据】   |
| 簇内语义纯度              | 同簇 item 的 cate3/spu 一致性显著高于随机基线；叶簇≈spu 粒度 | SQL 链粒度红线 + 【推断】簇要能借力，先要"同簇同类" |
| 覆盖率                    | 95%+ item 有 SID；新商品 T+0 可得                            | 冷启动卖点                                          |
| 碰撞度                    | 平均簇大小分布可控（Top 簇截断阈值定好）                     | 文档 §4.1 要点：sid2i 表内按质量分/新鲜度截断 TopN  |

## 5. Phase 2：召回四路径（钉钉文档 Step 3，主线）

| 路径               | 机制（已读要点）                                                                                               | 建议顺序                 | 评估                                                          |
| ------------------ | -------------------------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------- |
| 4.1 u2i2sid2i 多跳 | 行为 item → `item_sid_map` Join（**免物化 U→SID 画像**）→ `sid2i` TopN；与协同过滤区别：这是 u2i2x2i(x=sid)    | **第 1**（最稳、免画像） | Recall@K、重叠率 vs 现有 i2i/u2i、新增触达（尾部/新商品占比） |
| 4.2 实时 u2i       | FeatureStore 行为序列视图触发（TriggerCount 100/窗口 86400s，时间衰减 exp(-0.2)·(click:1;play:2)）→ sid2sid 表 | 第 2（实时增益）         | 同上 + 时延（召回引擎内编排，P99 可控）                       |
| 4.3 物品属性聚合   | 属性→SID 聚合触发                                                                                              | 第 3                     | 冷启动场景专项                                                |
| 4.4 sid2 直召      | `sid_i2i_similar` 语义协同（SID→SID）                                                                          | 第 4                     | 与 3.1 表质量绑定                                             |
| 4.5 四路径对比     | **文档有对比表，未读到**——排期前必须补读/补齐                                                                  | —                        | —                                                             |

**工程量级【估算】**：路径一 3-5 人日（PAI-Rec 召回引擎配置 + sid2i 表生产）；路径二 2-3 人日（FeatureStore 视图接入）；三/四各 2-3 人日。评估需粗排承接后的端侧 CTR，不只看召回池指标。

## 6. Phase 3：精排特征三档（v19 线，单变量消融）

> 对应钉钉文档"两大落地方向①作为特征进精排"，也是 v19"特征质量瓶颈"结论的直接进攻面。

| 档                       | 做法                                                                                                                                                                           | 工作量                | 判定（预注册）                                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------- | -------------------------------------------------------------------------------- |
| **3A SID 码特征**        | (c1,c2,c3[,c4]) 作 item 侧 id 特征各挂 embedding（8/8/8/8 维），拼 item 塔；**config-only 单变量臂** `home_flow_2608_v19_multiscene_v6f_sid.config`（新增文件不动现有 config） | 1-2 人日              | 整体 AUC 不掉（护栏，±0.5pp 带内）**且** 尾部桶（item 样本数\<50）方向正 → 进 3B |
| **3B 簇匹配特征**        | 用户行为簇直方图/最近簇序列 × 候选簇 → 匹配特征（类比 kv 族工程）；直接打 SQL-2"3_hit_cate3 占 46.3%/部分匹配 72.3%"的 q−s 残差面                                              | 3-5 人日（数据侧）    | 尾部桶主判据；与 SQL-8 簇代理结论互锁                                            |
| **3C CGAE-lite（二期）** | item embedding 拆簇嵌入 c + 个体嵌入 d + 活跃度门控 + stop-grad（embedding.py 小改，参照 AKT-Rec 消融：删 c 伤尾部 −1.20% GAUC、删 d 伤头部）                                  | 3-5 人日（代码+验证） | 尾部桶 GAUC 显著正且头部不掉；需 fx trace + backward 验证（T 线教训）            |

**读数协议（沿用 v19）**：20261030 同流同评估集；固定 seed 单变量；±0.5pp 带内只说"方向、不判符号"；多 seed 仅在宣称正收益上线时补；**必须报曝光分桶**（整体 AUC 会稀释尾部效应，AKT-Rec 收益集中在尾部【原始证据】）。

## 7. Phase 4：可选延伸（不在本版承诺内）

- 生成式召回（TIGER/FORGE 式 beam search）：等 P2 四路径读数后再议；
- 用户侧 SID（文档 §3.2 U→SID 列表）：3C 之后评估；
- 语义协同过滤（sid_i2i_similar 替换 sid2i）：文档 §4.1 要点已给接入方式，随 4.4 一并验。

## 8. 评估设计与预注册门槛（总表）

| 阶段 | 主判据                                    | 护栏                                         | 不过门槛的处置             |
| ---- | ----------------------------------------- | -------------------------------------------- | -------------------------- |
| P1   | 码本利用率/纯度/覆盖（§4.4）              | 离在线 SID 一致                              | 换 RQVAE 或调碰撞率        |
| P2   | 新增触达（尾部/新商品占比）+ 粗排承接 CTR | 时延 P99、召回池重叠不过高                   | 砍路径/调 TopN             |
| P3A  | 尾部桶 AUC 方向正                         | 整体 AUC 不掉                                | 停 3A，转向 3B             |
| P3B  | 尾部桶 AUC/GAUC 主判据                    | 整体不掉、bce_ctcvr 记副作用账（曝光族教训） | 与 SQL-8 结果互证后决定 3C |
| 3C   | 尾部 GAUC 显著                            | 头部不掉（AKT-Rec 非对称约束）               | 收档，转 SQL 线继续找特征  |

## 9. 风险与对策（三层标注）

| 风险                                                                   | 层                              | 对策                                                               |
| ---------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------ |
| 码本塌缩 → SID 表达力枯竭                                              | 【原始证据：Snapchat】          | RQKMeans 天然免疫；若 RQVAE 用 STE+多模融合；unique 率监控         |
| 尾部收益不及预期（AKT-Rec 尾部 GAUC 被 TailNet 反超 0.6397 vs 0.6448） | 【原始证据】                    | 目标定为"尾部改善、头部不掉"而非全面领先；分桶评估                 |
| SID 碰撞歧义（一码多品）                                               | 【原始证据：Snapchat】          | 两段式：SID 粗桶 + 桶内质量分/新鲜度排序截断（文档 §4.1 要点已含） |
| 整体 AUC 稀释尾部效应 → 误判"无收益"                                   | 【推断，基于 AKT-Rec 收益分布】 | 曝光分桶主判据写进预注册门槛                                       |
| 离在线 SID 不一致                                                      | 【事实读数：文档 §2.6 要点】    | 共用 checkpoint/码本；一致性抽检                                   |
| 维度错配（512 占位 vs 1152/2560 生产）                                 | 【事实读数：文档 §2.6】         | 配置模板里 value_dim 参数化，上线前 checklist                      |
| 样本点击过采样口径                                                     | 【事实读数：SQL-1】             | 一切读数只解读相对差                                               |
| 与曝光族候选抢训练资源                                                 | 【事实读数】                    | 并行排队；曝光族 seed43 收符号优先级不变                           |

## 10. 待确认清单（开工前补齐）

1. ~~文档 §2.1 选型~~ ✅ **已补读（2026-11-05 用户贴出 §2 全文）**：文档定论 = 首期 RQKMeans（需对比学习/多卡再切 RQVAE），与本文独立建议一致；命令/输入输出/在线部署均已定稿入 §4.1/4.3；
1. **文档 §4.5** 四条路径对比表——决定 P2 上线顺序是否调整；
1. **文档 §五** 落地实施步骤全文（工作量/排期口径）；
1. ~~value_dim~~ ✅ **已定**：推荐 qwen3-vl-embedding 融合向量 = **2560**（tongyi-embedding-vision-plus 独立向量 = 1152）；示例 512 禁用；
1. `sid2i`/`sid_i2i_similar` 表的生产调度与存储归属（文档 §3.1 标题可见，内容未读）；
1. ~~全量商品池规模~~ ✅ **已获（2026-11-05）**：title_vector 覆盖池 **80,164 items**（dt=20261030 快照，dim=128 全量一致）→ codebook 定稿 **[256,256,256]** 首跑（唯一回调判据 unique_sid_ratio\<70%）；title_vector 池 × home_flow 样本池覆盖率对账 = SQL-10（已给，待结果）。

> 补读方式：钉钉文档标签页在 WorkBuddy 浏览器中重新打开后我可继续逐节读取；或直接粘贴三段原文。

## 11. 立即行动清单（按序）

1. ~~跑 SQL-7~~ **✅ SQL-7/8/9 全部完成（2026-11-04/05），P0 取证链已收档**——结论：长尾成立、3C 优先、3B=强度形态+阈值≥3（全文见 [SQL_EVIDENCE_CHAIN_SID_20261104.md](SQL_EVIDENCE_CHAIN_SID_20261104.md)）；
1. 补齐 §10 待确认 3 处（重开钉钉文档或粘贴）；
1. **P1 启动（工程细节已齐）**：①万物向量注册（qwen3-vl-embedding + EnableFusion）→ 源表/特征视图/同步（存量 Overwrite、增量 Merge）→ 导出 embedding 样本；②RQKMeans 训练 + predict 出 `item_sid_map`（草案 config 已备：[sid_rq_kmeans.config](sid_rq_kmeans.config)）；③过 §4.4 质量门槛（unique_sid_ratio>70% 等）；
1. **补全量商品池规模** → 定 codebook 层宽（§4.2 估算表）；§4.5/§五/sid2i 调度三项待补读；
1. **3A config 臂**（`v6f_sid.config`，新增文件）：item_sid_map 落表后即可起草，SID 码 join 进样本作 item 侧 id 特征。

______________________________________________________________________

## 附录 A：SQL-7（item 活跃度分位普查）— ✅ 结果表+读数+判定见 [SQL_EVIDENCE_CHAIN_SID_20261104.md](SQL_EVIDENCE_CHAIN_SID_20261104.md) §1

```sql
-- SQL-7 (v2): item 侧活跃度（样本数）分位普查 —— SID/长尾立项前置
-- 表/口径沿用 SQL-1 定谳：点击过采样样本集，以样本数近似相对活跃度，只解读相对分布
-- v2 修复（2026-11-04）：ODPS-0130252 笛卡尔积禁令 —— 去掉 CROSS JOIN total，
--   占比改用窗口函数 SUM(...) OVER ()；原 v1 的 /*+ MAPJOIN */ hint 方案弃用（多一次广播不如纯窗口）
SET odps.sql.type.system.odps2=true;

WITH item_stat AS (
    SELECT
        item_id,
        COUNT(1)           AS samples,
        SUM(is_click)      AS clicks,
        SUM(is_conversion) AS convs
    FROM mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE dt = '20261030'
    GROUP BY item_id
),
bucketed AS (
    SELECT
        CASE
            WHEN samples < 10   THEN 'a_01_lt10'
            WHEN samples < 50   THEN 'b_02_10_50'
            WHEN samples < 200  THEN 'c_03_50_200'
            WHEN samples < 1000 THEN 'd_04_200_1000'
            ELSE                     'e_05_ge1000'
        END AS item_activity_bucket,
        samples,
        clicks
    FROM item_stat
),
agg AS (
    SELECT
        item_activity_bucket,
        COUNT(1)     AS n_items,
        SUM(samples) AS samples,
        SUM(clicks)  AS clicks
    FROM bucketed
    GROUP BY item_activity_bucket
)
SELECT
    item_activity_bucket,
    n_items,
    ROUND(n_items / SUM(n_items) OVER (), 4) AS item_ratio,
    samples,
    ROUND(samples / SUM(samples) OVER (), 4) AS sample_ratio,
    ROUND(clicks / samples, 5)               AS ctr
FROM agg
ORDER BY item_activity_bucket;
```

**判读标准（预注册）**：

- `a_01_lt10`+`b_02_10_50` 的 **item_ratio > 20% 且 sample_ratio > 10%** → 长尾问题成立，3C 优先级上调；
- 各桶 ctr 单调性：若长尾桶 ctr 显著更低 → 与"尾部 embedding 噪声"假设互证；
- 对照口径警示：绝对 CTR 仅解读相对差（点击过采样）。

## 附录 B：SQL-8（活跃度 × 匹配层级交叉）— ✅ 结果表+读数+判定见 [SQL_EVIDENCE_CHAIN_SID_20261104.md](SQL_EVIDENCE_CHAIN_SID_20261104.md) §2.2/2.3；SQL-9（剂量效应）全文与结果见其 §3

```sql
-- SQL-8: item 活跃度 × 序列匹配层级 交叉分桶 × CTR
-- 目的（基于 SQL-7 结果转向）：尾部 a+b 桶 CTR 低 3.7pp——是"缺行为借力"还是"商品固有"？
--   借力代理 = SQL-2 的 click_50_seq 匹配层级；活跃度桶 = SQL-7 同口径（item 样本数）
-- 预注册判读：
--   ① 尾部桶内 match lift（如 3_hit_cate3 vs 6_no_hit）≥ 头部桶 → 借力面对尾部有效 → 3B（簇匹配特征）优先
--   ② 尾部桶内梯度明显更平 → 低 CTR 主因是商品固有/曝光不足 → 3C（簇嵌入共享统计强度）优先
--   ③ 尾部 lift 更大 → 3B+3C 双双有据，按工作量 3B 先行
SET odps.sql.type.system.odps2=true;

WITH item_stat AS (
    SELECT item_id, COUNT(1) AS item_samples
    FROM   mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE  dt = '20261030'
    GROUP BY item_id
),
flagged AS (
    SELECT
        CASE
            WHEN s.item_samples < 10   THEN 'a_01_lt10'
            WHEN s.item_samples < 50   THEN 'b_02_10_50'
            WHEN s.item_samples < 200  THEN 'c_03_50_200'
            WHEN s.item_samples < 1000 THEN 'd_04_200_1000'
            ELSE                            'e_05_ge1000'
        END AS item_activity_bucket,
        CASE
            WHEN t.click_50_seq__item_id IS NULL OR t.click_50_seq__item_id = '' THEN '0_no_seq'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__item_id, ';'), t.item_id)  THEN '1_hit_item'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__spu_id,  ';'), t.spu_id)   THEN '2_hit_spu'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__third_cate_id, ';'),
                                CAST(t.third_cate_id AS STRING))                 THEN '3_hit_cate3'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__second_cate_id, ';'),
                                CAST(t.second_cate_id AS STRING))                THEN '4_hit_cate2'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__first_cate_id, ';'),
                                CAST(t.first_cate_id AS STRING))                 THEN '5_hit_cate1'
            ELSE '6_no_hit'
        END AS match_bucket,
        t.is_click
    FROM mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set t
    JOIN item_stat s ON t.item_id = s.item_id
    WHERE t.dt = '20261030'
)
SELECT
    item_activity_bucket,
    match_bucket,
    COUNT(1)                          AS samples,
    SUM(is_click)                     AS clicks,
    ROUND(SUM(is_click) / COUNT(1), 5) AS ctr
FROM flagged
GROUP BY item_activity_bucket, match_bucket
HAVING COUNT(1) >= 2000          -- 小格防噪声（a 桶 × 细匹配桶可能很小），阈值可调
ORDER BY item_activity_bucket, match_bucket;
```

## 参考链接（版本时效：以官方最新文档为准，2026-11-04 记录）

- TorchEasyRec SID 总览 / RQVAE / RQKMeans：torcheasyrec.readthedocs.io/zh-cn/latest/models/sid_model.html、sid_rqvae.html、sid_rqkmeans.html
- PAI-FeatureStore 万物向量最佳实践：help.aliyun.com/zh/pai/use-cases/featurestore-llm-multimodal-embedding-best-practices
- 多模态向量 API：help.aliyun.com/zh/model-studio/embedding
- PAI-Rec 召回链路定义：help.aliyun.com/zh/pai/recall-link-definition
- 论文：FORGE (arXiv:2509.20904)、TIGER (arXiv:2305.05065)、RQ-VAE (arXiv:2203.01941)、AKT-Rec (arXiv:2605.23310)、Snapchat SID (arXiv:2604.03949)
- 原理动画（上一轮交付）：[semantic_id_rqvae_v19_application.html](/Users/zhangjunfei/WorkBuddy/2026-11-04-13-16-13/semantic_id_rqvae_v19_application.html)（RQ-VAE 10 步动画 + AKT-Rec 消融表 + v19 接入映射）
