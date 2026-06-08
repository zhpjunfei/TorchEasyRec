______________________________________________________________________

## date: 2026-06-07 tags: [architecture, modules, lhuc, cdot, cross, extraction] related: \["\[[pepnet-dcn-ple]\]"\]

# Model Components — LHUC / CDOT / CrossV2 / ExtractionNet

> PEPNetDCNPLE 模型的 5 大子模块详解. 代码位置 `tzrec/modules/`.

## LHUC (Learnable Hidden Unit Control)

**位置**: `tzrec/modules/lhuc_net.py` (160 行)

### LHUC_EPNet (Embedding Personalization)

```python
scale = tanh(gate * 0.2) * 5.0 + 1.0  # range: [-4, 6]
deep_input = deep_input * scale
```

- **作用**: domain-level 门控, 对 deep_input 做元素缩放
- **输入**: lhuc_group features
- **结构**: `Linear → ReLU → Linear → ... → Linear(output_dim)`, 末层无激活

### LHUC_PPNet (Parameter Personalization)

```python
for idx, nn_dim in enumerate(nn_dims):
    scale = tanh(gate * 0.2) * (5.0 + idx) + 1.0
    x = x * scale              # scale before Dense
    x = Linear(x)
    x = activation(x) if idx < num_layers - 1
```

- **作用**: per-layer scale-before-Dense 门控
- **关键**: gate output dim = current layer INPUT dim (不是 target nn_dim)
- **匹配 TF lhuc_pp_net 顺序**: scale → Dense → activation

## CDOT (Compressed Dense Over-all Tower)

**位置**: `tzrec/modules/cdot.py`

### 核心功能

- slot-level 动态特征压缩变换
- 输入: `[B, num_slots, slot_dim]` (经过 stack 后)
- 输出: `allint_out` (低维向量) + `allint_mid_out` (中间向量)
- 用于 domain group 的 slot 关系建模

### 流程

1. **Compress**: 每个 slot 独立压缩 (sub_compress_weight: `[slot_dim, mid_dim]`)
1. **Interaction**: slot 间交互 (mid_dim → output_dim)
1. **Output**: `[B, output_dim]`, 同时输出 mid 状态供 LN

## CrossV2 (DCNv2)

**位置**: `tzrec/modules/interaction.py`

```python
class CrossV2(nn.Module):
    def __init__(self, input_dim, cross_num, low_rank=32):
```

- **low_rank**: 低秩矩阵 `[low_rank, input_dim]` 替代完整 `[input_dim, input_dim]`
- **cross_num**: 交叉层数
- TF DCNv2 等价物

## ExtractionNet (PLE layer)

**位置**: `tzrec/modules/extraction_net.py`

### 架构 (CGC 路由)

```
输入: extraction_network_fea (per-task), shared_expert_fea (shared)
     ↓
[Task Expert]  [Shared Expert]  ← 多组, 每组独立 MLP
     ↓
[Gate] → weighted sum → per-task output + shared output
     ↓
(多层堆叠)
```

- `expert_num_per_task`: 每个任务的 expert 数
- `share_num`: 共享 expert 数
- `final_flag=True`: 最后一层, 不再生成 shared output

## Component LayerNorm

**位置**: `pepnet_dcn_ple.py:160-171`

```python
self.component_ln = nn.ModuleDict()
self.component_ln["main"] = nn.LayerNorm(self._main_group_dim)
self.component_ln["cross"] = nn.LayerNorm(self._main_group_dim)  # if cross_net
self.component_ln["allint_out"] = nn.LayerNorm(cdot_output_dim)
self.component_ln["bias"] = nn.LayerNorm(num_bias_features)  # if bias
self.component_ln["allint_mid"] = nn.LayerNorm(cdot_output_dim)
```

- **每组件独立 LN** 后 concat
- **优势**: 不同组件 scale 不同, 独立 LN 避免相互干扰

## 确定性属性 (eval 模式)

| 组件          | Dropout | BN  | 随机源 | eval 模式确定性 |
| :------------ | :-----: | :-: | :----- | :-------------: |
| LHUC_EPNet    |   ❌    | ❌  | 无     |       ✅        |
| LHUC_PPNet    |   ❌    | ❌  | 无     |       ✅        |
| CDOT          |   ❌    | ❌  | 无     |       ✅        |
| CrossV2       |   ❌    | ❌  | 无     |       ✅        |
| ExtractionNet |   ❌    | ❌  | 无     |       ✅        |
| LayerNorm     |   ❌    | ❌  | 无     |       ✅        |

**结论**: 模型在 eval 模式下**完全确定性**, 0.73pp noise **不来自模型本身**, 来自 \[[../20-experiments/5run-noise-investigation|eval pipeline]\].

## 文件清单

| 文件                              | 行数 | 用途                    |
| :-------------------------------- | ---: | :---------------------- |
| `tzrec/modules/lhuc_net.py`       |  160 | LHUC_EPNet + LHUC_PPNet |
| `tzrec/modules/cdot.py`           | ~120 | CDOT                    |
| `tzrec/modules/interaction.py`    |  ~80 | CrossV2 (DCNv2)         |
| `tzrec/modules/extraction_net.py` | ~150 | PLE ExtractionNet       |
