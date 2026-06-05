# PEPNET_DCN_PLE 架构方案

## 设计目标

在 PEPNet_v2 的基础上，将多任务 tower 替换为 PLE 的 ExtractionNet（CGC），同时保留 DCNv2、CDOT、EPNet/LHUC 等 PEPNet 核心组件，实现渐进式任务分离。

## 数据流

```
embeddings
    │
    ├── DCNv2 ────────── cross_output
    ├── CDOT ─────────── allint_out + allint_mid
    ├── Bias ─────────── bias_vec
    └── main_embeddings
    │
    ▼
Component LayerNorm ─── concat ─── deep_input
                                        │
                                  EPNet(LHUC)
                                        │
                                  deep_input * ep_scale (personalized)
                                        │
                          ┌─────────────┴─────────────┐
                          │  shared_expert_fea         │
                          │  extraction_network_fea[0] │  (CTR copy)
                          │  extraction_network_fea[1] │  (CVR copy)
                          │                           │
                          ▼                           ▼
                  ExtractionNet Layer 1 ───── ExtractionNet Layer 1
                  (CGC: experts + gates)      (CGC: experts + gates)
                          │                           │
                          ▼                           ▼
                  ExtractionNet Layer 2 ───── ExtractionNet Layer 2
                          │                           │
                          ▼                           ▼
                  TaskTower(ctr) ─────── TaskTower(cvr)
                          │                           │
                          ▼                           ▼
                  final linear               final linear
                          │                           │
                          ▼                           ▼
                  ctr_logit          cvr_logit + ctr_logit
                  + bias_sum         + bias_sum
```

## Proto 定义

`tzrec/protos/models/multi_task_rank.proto` 新增：

```protobuf
message PEPNetDCNPLE {
    // PEPNet 组件
    optional uint32 epnet_hidden_unit = 1;
    optional float  epnet_gamma = 2 [default = 2.0];
    optional string epnet_scale_type = 3 [default = 'tanh'];
    repeated uint32 ppnet_hidden_units = 4;
    optional string ppnet_activation = 5 [default = 'nn.ReLU'];
    repeated float ppnet_dropout_ratio = 6;
    optional float  ppnet_gamma = 7 [default = 2.0];
    optional string ppnet_scale_type = 8 [default = 'tanh'];

    // CDOT
    optional CDOTConfig cdot = 9;
    optional string cdot_group_name = 10 [default = 'all'];
    // Bias
    optional string bias_group_name = 11 [default = 'all'];
    // LHUC group
    optional string lhuc_group_name = 12 [default = 'domain'];
    // Main group
    optional string main_group_name = 13 [default = 'all'];

    // DCNv2
    optional CrossV2 dcnv2 = 14;

    // PLE 组件
    repeated ExtractionNetwork extraction_networks = 15;

    // Task towers
    repeated TaskTower task_towers = 16;

    // CVR add CTR logits
    optional bool cvr_add_ctr_logits = 17 [default = true];
}
```

`tzrec/protos/model.proto` 注册：

```protobuf
PEPNetDCNPLE pepnet_dcn_ple = 209;
```

## 模型实现

`tzrec/models/pepnet_dcn_ple.py`：

```python
class PEPNetDCNPLE(MultiTaskRank):
    """
    PEPNet + DCNv2 + PLE (ExtractionNet) fusion architecture.
    """
    def __init__(self, ...):
        # 1. Input init (same as PEPNet_v2)
        self.init_input()

        # 2. PEPNet components:
        #    - DCNv2 CrossV2
        #    - CDOT
        #    - Bias
        #    - Component LayerNorm
        #    - EPNet (LHUC)

        # 3. PLE components:
        #    - ExtractionNet layers (shared experts + per-task experts + gates)
        #    - LHUC_PPNet per task tower (逐层个性化替换 TaskTower 的标 MLP)

        # 4. Output:
        #    - Tower final linear
        #    - cvr_add_ctr_logits
```

## 与 PEPNet_v2 的差异

| 维度       |         PEPNet_v2          |           PEPNET_DCN_PLE            |
| :--------- | :------------------------: | :---------------------------------: |
| 任务分离   |  独立 tower（LHUC_PPNet）  |     ExtractionNet 逐层 CGC 路由     |
| 参数共享   |     cvr_add_ctr_logits     | shared experts + cvr_add_ctr_logits |
| tower 内   |    LHUC_PPNet 逐层缩放     |     LHUC_PPNet 逐层缩放（保留）     |
| tower 输入 | EPNet 输出直接进入各 tower |  EPNet 输出先经多层 ExtractionNet   |
| tower MLP  | [512,256,128] + PPNet 缩放 |        [128,64] + PPNet 缩放        |
| PPNet      |    [512,256,128] (3层)     |           [256,128] (2层)           |

## 配置模板

`data/pepnet_demo/config/home_flow_2604_pepnet_dcn_ple.config`，基于 `home_flow_2604_pepnet.config` 修改。

与 PEPNet_v2 基线相比的关键变化：

| 配置项                   | PEPNet_v2       | PEPNetDCNPLE          | 原因                                   |
| ------------------------ | --------------- | --------------------- | -------------------------------------- |
| `model`                  | `pepnet_v2`     | `pepnet_dcn_ple`      | 切换架构                               |
| `epnet_gamma`            | `2.0`           | 省略（默认 2.0）      | 默认值等价                             |
| `ppnet_hidden_units`     | `[512,256,128]` | `[256,128]`           | ExtractionNet 已做路由，PPNet 层数减少 |
| Tower MLP `hidden_units` | `[512,256,128]` | `[128,64]`            | Extraction experts 承担大部分任务学习  |
| `extraction_networks`    | 无              | 2 层 CGC              | PLE 核心：逐层任务分离                 |
| `batch_size`             | `4096`          | `16384`               | 样本量 8x（3M→24M）                    |
| `T_max`                  | `6300`          | `10000`               | step-based 训练，长周期 cosine decay   |
| `warmup_size`            | `1000`          | `2000`                | 大 batch 需要更多 warmup               |
| `part_optimizers regex`  | ppnet/gate/cdot | + extraction_networks | 新增 expert MLP weight decay           |

## 实现状态

- [x] Proto 修改（multi_task_rank.proto + model.proto）+ 编译
- [x] `tzrec/models/pepnet_dcn_ple.py`（继承 MultiTaskRank）
- [x] LHUC_PPNet 替换 PLE 默认的 TaskTower MLP
- [x] ExtractionNet 输出适配 LHUC_PPNet 输入
- [x] 单元测试（4 条，含 base/cdot/dcnv2/cdot+dcnv2）
- [x] 配置模板 `home_flow_2604_pepnet_dcn_ple.config`
