______________________________________________________________________

## date: 2026-05-30 tags: [archive, pepnet-v2, dbmtl, comparison] status: archived related: ["[[../10-architecture/pepnet-v2]]"]

**PEPNet_v2 vs DBMtl_DCNv2 优化点总结**

| 方面           | DBMtl_DCNv2 (v1c)                   | PEPNet_v2 (pepnet)                                    | 优化说明                                                                       |
| -------------- | ----------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------ |
| **模型架构**   | DCNv2 cross + shared bottom MLP     | EPNet + PPNet + CDOT + LHUC + Bias                    | 摒弃硬交叉(DCNv2)，改用软个性化(PEPNet)架构                                    |
| **特征交叉**   | DCNv2 cross_num=4, low_rank=256     | CDOT (input_dim=16, output_dim=4, mid_dim=32)         | CDOT 压缩式动态交叉，参数更少、可学习性更强                                    |
| **个性化**     | 无独立个性化模块                    | LHUC-EPNet (gate tanh) + LHUC-PPNet (per-layer scale) | 基于 mmb_id/item_id/f_req_page 的软个性化调控                                  |
| **特征分组**   | 只有 `all` 组                       | `all` + `domain` 组 (mmb_id, item_id, f_req_page)     | domain 组专用于 LHUC 个性化缩放                                                |
| **新增特征**   | —                                   | `f_req_page` (用户请求页面 embedding_dim=4)           | 增强请求页面感知能力                                                           |
| **优化器**     | Adam (lr=0.001)                     | Adam + **AdamW** (weight_decay=0.01)                  | dense MLP 权重 + cdot.sub_compress_weight 带 weight_decay，其余(emb/bias/LN)无 |
| **Tower MLP**  | [128,64,32] + use_ln + dropout(0.1) | [512,256,128] 无 LN/dropout                           | 更宽但无正则化，依赖 AdamW 防止过拟合                                          |
| **CVR 融合**   | DBMTL relation_mlp [64,32]          | ESMM式 + **cvr_add_ctr_logits=true**                  | logit 级加 CTR logits 到 CVR，更直接的信息传递                                 |
| **序列编码器** | 6× DIN (同)                         | 6× DIN (同)                                           | 无变化                                                                         |
| **底部 MLP**   | bottom_mlp [512,256,128,64]         | 无 bottom MLP（EPNet+PPNet 代替）                     | 去共享底层，改专家网络+个性化网络                                              |

**核心优化路线**: DCNv2+DNN → EPNet(专家塑性)+PPNet(个性化)+CDOT(动态交叉)+LHUC(缩放)+Bias(偏置)，配合 AdamW 正则化。
