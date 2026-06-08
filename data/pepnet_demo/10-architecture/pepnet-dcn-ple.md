______________________________________________________________________

## date: 2026-06-07 tags: [architecture, pepnet, ple, v6_ple_d, production-candidate] status: production-candidate related: \["\[[pepnet-v2]\]", "\[[model-components]\]", "\[[../20-experiments/v6-design-matrix]\]"\]

# PEPNetDCNPLE — 本项目主模型 ⭐

> **PEPNet_v2 + DCNv2 + PLE (ExtractionNet) fusion architecture**. 本项目生产候选 = v6_ple_d (= v7_ple_d), 离线 CVR (确定性) = **0.791069** (2026-06-08 验证, 4× bitwise identical, Std=0pp). 修复前 5-run mean 0.7852 ± 0.73pp 有系统性低估偏差 -0.59pp.

## 架构 (PEPNet_v2 + PLE middle)

```
PEPNet frontend
  ├── main_group (all) → LN
  ├── cdot_group (domain) → CDOT → LN
  ├── bias_group (domain) → Bias → LN
  ├── dcnv2_group (all) → CrossV2 → LN
  └── lhuc_group → LHUC-EPNet → scale ──→ deep_input *= scale
                          ↓
       PLE middle: ExtractionNet layers with CGC routing
                          ↓
       LHUC_PPNet towers: per-task personalization + final linear
                          ↓
       CVR logit-level addition with CTR logits
```

**vs PEPNet_v2**: 在 deep_input 之后, tower 之前, 插入 1+ 层 PLE (ExtractionNet) 处理多任务共享.

## 关键代码位置

- `tzrec/models/pepnet_dcn_ple.py` — `PEPNetDCNPLE` 类 (372 行)
- `__init__` L83-257: 5 个子模块构造 (CDOT / CrossV2 / Bias / EPNet / ExtractionNets / PPNet)
- `predict` L267-372: forward pass, 见下方

## predict() 流程 (L267-372)

1. `build_input(batch)` → 4 个 grouped feature tensor
1. `main_features` split into per-feature tensors
1. **Bias** 提取: `bias_vec, bias_sum = _extract_bias(...)` (各特征首维 1-dim, 取 sum)
1. **DCNv2**: `cross_output = self.cross_net(main_features)`
1. **CDOT**: `allint_out, allint_mid_out = self.cdot(cdot_input)`
1. **Concat**: `concat_parts = [LN(main), LN(cross), LN(cdot_out), LN(bias), LN(cdot_mid)]`
1. **EPNet**: `deep_input = deep_input * ep_scale`
1. **PLE ExtractionNets**: 多层 CGC 路由
1. **LHUC_PPNet towers**: per-task hidden states
1. **Final logits**: `tower_output + bias_sum` (or `+ ctr_logits_val` if cvr_add_ctr_logits)

## 配置 (v6_ple_d.config)

关键字段:

```protobuf
model_config: pepnet_dcn_ple
main_group_name: "main"
lhuc_group_name: "lhuc"
cdot_group_name: "cdot"
bias_group_name: "bias"
cvr_add_ctr_logits: true

eval_config {
  num_steps: 123           # 25W / 2048 ≈ 123
  log_step_count_steps: 50
}

data_config {
  batch_size: 2048         # per-GPU
  num_workers: 18
  dataset_type: OdpsDataset
}
```

## 已知修复 (2026-06-07)

模型本身在 eval 模式下**完全确定性** (无 Dropout/BN). 之前 0.73pp noise 来自 \[[../20-experiments/5run-noise-investigation|eval pipeline]\], 与本模型代码无关. 修复见 \[[../20-experiments/eval-pipeline-fix|eval-pipeline-fix]\].

## 实验结果 (5-run)

详见 \[[../20-experiments/v6-design-matrix|v6 设计矩阵]\] 和 \[[../20-experiments/v7-ple-d-variants|v7 变种]\].

| 指标                 |            数值 | 备注                                           |
| :------------------- | --------------: | :--------------------------------------------- |
| **CVR AUC (确定性)** |    **0.791069** | 2026-06-08 验证, 4× bitwise identical, Std=0pp |
| CTR AUC (确定性)     |        0.790610 | 同上                                           |
| 修复前 CVR (5-run)   | 0.7852 ± 0.73pp | 系统性低估偏差 -0.59pp                         |
| 训练耗时             |           ~3.5h | 2×A10, 1 epoch                                 |

## 部署脚本

`data/pepnet_demo/sql/sample_v2/tran_v6_ple_d.sh` (含 1.2.16 wheel 修复)

## 下一步

- \[[../20-experiments/v7-ple-d-variants|v7 变种]\] — d=8/16/32, dpage, ph
- \[[../20-experiments/eval-pipeline-fix|修复记录]\] — eval 非确定性修复
