# PEPNet_v2 模型逐行讲解

文件：`tzrec/models/pepnet_v2.py`（共 366 行）

______________________________________________________________________

## 一、类定义与架构总览（L1-71）

```python
class PEPNet_v2(MultiTaskRank):
```

继承自 `MultiTaskRank`，后者继承自 `RankModel`。继承链提供：

- `RankModel`: `init_input()` 构建 EmbeddingGroup、`build_input()` 做 embedding lookup
- `MultiTaskRank`: `_multi_task_output_to_prediction()` 将 logit 转成 predictions dict

### docstring 关键点（L59-71）

| 组件               | 位置                     | 功能                                |
| ------------------ | ------------------------ | ----------------------------------- |
| DCNv2 CrossV2      | `modules/interaction.py` | 低秩显式特征交叉                    |
| CDOT               | `modules/cdot.py`        | 动态特征压缩变换                    |
| Bias               | 首维提取                 | 每个特征首元素求和偏置              |
| Component LN       | 本文件                   | 每组件独立 LN 后 concat             |
| LHUC-EPNet         | `modules/lhuc_net.py`    | EPNet 级别的 tanh [-4,6] 个人化缩放 |
| LHUC-PPNet         | `modules/lhuc_net.py`    | 逐层递增 scale-before-Dense 个人化  |
| cvr_add_ctr_logits | 本文件                   | CVR logit 加 CTR logit              |
| Relation MLP       | 本文件                   | CVR tower 接收 CTR tower hidden     |

______________________________________________________________________

## 二、`__init__` 初始化（L73-243）

### L73-81：构造函数签名与基类调用

```python
def __init__(self, model_config, features, labels, ...):
    super().__init__(model_config, features, labels, sample_weights, **kwargs)
    self.init_input()
```

基类 `RankModel.__init__` 保存 `model_config`, `features`, `labels` 等。
`init_input()` 构建 `self.embedding_group`（`EmbeddingGroup`）：

- 根据 `features` 定义和 `feature_groups` 配置，将各特征分配到 named group
- 每个 group 的 embedding 按特征顺序 concat 成一个 tensor

### L84-87：Group 名称映射

```python
self._main_group_name = self._model_config.main_group_name      # "all"
self._lhuc_group_name = self._model_config.lhuc_group_name      # "domain"
self._cdot_group_name = self._model_config.cdot_group_name       # "domain"
self._bias_group_name = self._model_config.bias_group_name       # "domain"
```

4 个 group 各司其职：

| Group                   | role                   | 包含特征                    |
| ----------------------- | ---------------------- | --------------------------- |
| `main_group` ("all")    | EPNet + DCNv2 主体输入 | 全部特征                    |
| `cdot_group` ("domain") | CDOT 动态压缩输入      | mmb_id, item_id, f_req_page |
| `bias_group` ("domain") | Bias 首维提取          | 同上                        |
| `lhuc_group` ("domain") | LHUC 门控输入          | 同上                        |

同类目推荐中，domain group 的特征决定"今天用户想要什么"——CDOT 学特征级变换、LHUC 学塔级缩放、Bias 学全局偏移。

### L91-95：Main group 维度获取

```python
self._main_feature_dims = self.embedding_group.group_feature_dims(self._main_group_name)
self._main_group_dim = sum(self._main_feature_dims.values())
self._main_feature_dim_list = list(self._main_feature_dims.values())
```

`_main_feature_dims` 是一个 dict，key=特征名，value=该特征的 embedding_dim。
例：`{"item_id": 32, "mmb_id": 32, "page": 32, ...}`。
`_main_group_dim` 是 sum of all（~600 维）。
`_main_feature_dim_list` 用于 `torch.split` 拆回各特征。

### L97-124：CDOT 模块初始化

```python
if self.embedding_group.has_group(self._cdot_group_name):
    cdot_cfg = self._model_config.cdot
    cdot_input_dim = cdot_cfg.input_dim       # 16
    cdot_output_dim = cdot_cfg.output_dim      # 4
    cdot_mid_dim = cdot_cfg.mid_dim            # 32
    compress_hidden_units = list(cdot_cfg.compress_hidden_units)  # [512, 374]
    cdot_feature_dims = self.embedding_group.group_feature_dims(self._cdot_group_name)
    self.cdot = CDOT(
        num_slots=len(cdot_feature_dims),          # = domain 组特征数
        input_dim=cdot_input_dim,                   # 16
        output_dim=cdot_output_dim,                 # 4
        mid_dim=cdot_mid_dim,                       # 32
        compress_hidden_units=compress_hidden_units, # [512, 374]
    )
    self._cdot_concat_dim = self.cdot.output_dim() * 2  # 4 * 2 = 8
```

**CDOT 的核心公式：**

设 `x` 为 `[B, num_slots, input_dim]`（每个 slot 是 domain 组的一个特征，截断/pad 到 16 维）：

1. **Sub-compress**: `x` → transpose → reshape → `mm(sub_compress_weight)` → reshape → `[B, input_dim * mid_dim]`（把 slot 间的信息压缩到每个 slot 的 channel 内）
1. **Compress MLP**: `[input_dim * mid_dim]` → MLP`[512, 374]` → `[num_slots * output_dim]`（生成每个 slot 的动态变换权重）
1. **Bilinear transform**: `allint_out = bmm(x, bmm(x^T, compress_wt) + bias)` → flat `[B, num_slots * output_dim]`

输出两路：

- `allint_out (B, 8)` — 变换后的特征，过 LN 后 concat
- `allint_mid_out (B, num_slots * output_dim)` — 压缩权重本身，过 LN 后 concat（提供显式的权重信号）

这就是 CDOT 的"动态特征交叉"——每个样本根据自身 domain 特征，生成不同的交叉变换矩阵。

### L126-134：DCNv2 CrossV2 初始化

```python
if self._model_config.HasField("dcnv2"):
    dcnv2_cfg = self._model_config.dcnv2
    self.cross_net = CrossV2(
        input_dim=self._main_group_dim,
        cross_num=dcnv2_cfg.cross_num,     # 4
        low_rank=dcnv2_cfg.low_rank,       # 256
    )
```

CrossV2 是 low-rank DCNv2：`x_{l+1} = x_0 * (W_l * (V_l^T * x_l) + b_l) + x_l`。

- `low_rank=256`：将 full-rank 权重 `[d, d]` 分解为 `W[d, r] * V[r, d]`（r=256），参数量从 d² 降到 2*d*r
- 输入是 main group 的全部特征（~600 维），输出同维度
- 实现文件：`modules/interaction.py`

### L136-143：Bias group 维度获取

```python
if self.embedding_group.has_group(self._bias_group_name):
    self._bias_feature_dims = self.embedding_group.group_feature_dims(self._bias_group_name)
    self._num_bias_features = len(self._bias_feature_dims)
```

`_num_bias_features` 用于控制 bias LN 和 concat。

### L148-153：Deep concat 维度汇总

```python
deep_concat_dim = (
    self._main_group_dim       # main group 全部特征
    + self._cross_concat_dim  # DCNv2 输出（=main_group_dim 或 0）
    + self._cdot_concat_dim   # CDOT 两路输出（8 或 0）
    + self._num_bias_features # bias feature 数（或 0）
)
```

这个 `deep_concat_dim` 是 EPNet/LHUC 之后进入 PPNet tower 的输入维度。

### L155-165：Component LayerNorm

```python
self.component_ln = nn.ModuleDict()
self.component_ln["main"] = nn.LayerNorm(self._main_group_dim)
if self.cross_net is not None:
    self.component_ln["cross"] = nn.LayerNorm(self._main_group_dim)
if self.cdot is not None:
    self.component_ln["allint_out"] = nn.LayerNorm(self.cdot.output_dim())
    if self._num_bias_features > 0:
        self.component_ln["bias"] = nn.LayerNorm(self._num_bias_features)
    self.component_ln["allint_mid"] = nn.LayerNorm(self.cdot.output_dim())
```

每组件独立 LN，匹配 TF 实现。将 `main`、`cross`、`allint_out`、`bias`、`allint_mid` 各自 LN → concat。这样避免了把所有特征塞进一个大 LN 导致的信息混淆。

### L167-183：LHUC-EPNet 初始化

```python
if self.embedding_group.has_group(self._lhuc_group_name):
    self._lhuc_group_dim = self.embedding_group.group_total_dim(self._lhuc_group_name)
    epnet_hidden = self._model_config.epnet_hidden_unit  # 256
    self.epnet = LHUC_EPNet(
        lhuc_dim=self._lhuc_group_dim,     # domain 组总维度
        output_dim=deep_concat_dim,         # ↑ 计算的 deep_concat_dim
        hidden_units=[epnet_hidden],        # [256]
    )
```

LHUC-EPNet 输入 domain group embedding，输出一个 `[B, deep_concat_dim]` 的 scale 向量，对 deep_concat tensor 做 element-wise multiply。

**LHUC-EPNet 内部（`modules/lhuc_net.py`）：**

```python
def forward(self, x):
    gate = self.gate_mlp(x)        # 单 MLP，输出 dim = output_dim
    scale = torch.tanh(gate * 0.2) * 4.0 + 1.0    # [-4, 4]*tanh + 1 → [-3, 5]
    return scale
```

`tanh(gate * 0.2)` 将 gate 压缩到约 [-1, 1] → `* 4.0 + 1.0` → 范围 [-3, 5]。
最终 scale 范围 ≈ [-3, 5]，可正可负。

### L185-215：PPNet 配置与 Tower 构建

```python
ppnet_activation = self._model_config.ppnet_activation  # "nn.ReLU"
ppnet_lhuc_hidden = [self._model_config.ppnet_hidden_units[0]]  # [512]
self._relation_mlps = nn.ModuleDict()
self._tower_final = nn.ModuleDict()
self._ctr_tower_name = None

for tower_cfg in self._task_tower_cfgs:
    mlp_cfg = tower_kwargs.get("mlp", {"hidden_units": [512, 256, 128]})
    hidden_units = list(mlp_cfg.get("hidden_units", [512, 256, 128]))
    self._task_towers.append(
        LHUC_PPNet(
            input_dim=deep_concat_dim,
            lhuc_dim=self._lhuc_group_dim,
            nn_dims=hidden_units,        # [512, 256, 128]
            nn_activation=ppnet_activation, # "nn.ReLU"
            lhuc_hidden_units=ppnet_lhuc_hidden,  # [512] — 所有层共享同个 gate hidden dim
        )
    )
    if tower_name == "ctr":
        self._ctr_tower_name = "ctr"
```

每个 task_tower 独立拥有一个 LHUC_PPNet，参数不共享。
`hidden_units = [512, 256, 128]` 定义 3 层 MLP，最终输出 dim = 128（penultimate hidden）。

**LHUC-PPNet 结构（`modules/lhuc_net.py` L91-160）：**

对每层 `idx`：

1. Gate MLP（独立于每层）：`lhuc_features` → Linear[·, cur_dim] → scale
1. `scale = tanh(gate * 0.2) * (5.0 + idx) + 1.0`
   - idx=0: `tanh * 5.0 + 1.0` → 范围 [-4, 6]
   - idx=2: `tanh * 7.0 + 1.0` → 范围 [-6, 8]
   - 深层具有更大的缩放自由度
1. `x = x * scale`（scale-before-Dense，匹配 TF）
1. `x = Dense(x)`
1. `x = activation(x)`（最后一层无激活）

### L217-241：Tower Final 与 Relation MLP

```python
tower_hidden_dim = hidden_units[-1]  # 128
for tower_cfg in self._task_tower_cfgs:
    if tower_cfg.HasField("relation_mlp"):
        relation_input_dim = tower_hidden_dim  # 本 tower hidden (128)
        for rel_name in tower_cfg.relation_tower_names:
            if rel_name in self._relation_mlps:
                relation_input_dim += self._relation_mlps[rel_name].output_dim()
            else:
                relation_input_dim += tower_hidden_dim  # related tower hidden (128)
        self._relation_mlps[tower_name] = MLP(
            in_features=relation_input_dim,  # 256 (cvr 128 + ctr 128)
            **config_to_kwargs(tower_cfg.relation_mlp),  # hidden_units [64, 32], use_ln
        )
        self._tower_final[tower_name] = nn.Linear(
            self._relation_mlps[tower_name].output_dim(),  # 32 → 1
            tower_cfg.num_class,
        )
    else:
        self._tower_final[tower_name] = nn.Linear(
            tower_hidden_dim, tower_cfg.num_class  # 128 → 1
        )
```

**两分支对比：**

|                       | 无 relation_mlp         | 有 relation_mlp                             |
| --------------------- | ----------------------- | ------------------------------------------- |
| tower_hidden (B, 128) | → Linear(128→1) = logit | → concat(own_hidden, rel_hidden) = (B, 256) |
|                       |                         | → Relation MLP [64, 32] + LN → (B, 32)      |
|                       |                         | → Linear(32→1) = logit                      |

`relation_hidden[rel_name]` 的取值规则：

- 如果 related tower 自身也有 relation_mlp，用它的 post-MLP 输出
- 否则，用 raw tower_hidden

这就是为什么 config 中 CTR tower 必须在 CVR 之前定义（L199-215 的第一次 for 循环保证 Tower 自身先建好，L219-241 的第二次循环才建 relation_mlp）。

### L243：cvr_add_ctr_logits

```python
self._cvr_add_ctr_logits = self._model_config.cvr_add_ctr_logits  # true
```

独立于 relation_mlp 的 logit 级 CTR→CVR 加法。CVR logit 计算完后，再加上 CTR logit 输出。

______________________________________________________________________

## 三、`predict` 前向推理（L253-366）

### L262：特征输入

```python
grouped_features = self.build_input(batch)
```

调用 `RankModel.build_input`：

1. `embedding_group(batch)` — ODPS 数据经 DataLoader 产出 batch，embedding_group 根据 feature_groups 定义做 embedding lookup，输出 dict
1. 返回 `{"all": tensor, "domain": tensor, "click_10_seq": tensor, ...}`

### L264-268：Main features 准备

```python
main_features = grouped_features[self._main_group_name]           # [B, sum(all_dims)]
main_feature_tensors = torch.split(main_features, self._main_feature_dim_list, dim=1)
```

`main_features` ~ [B, 600+]，是 "all" 组所有 feature embedding 的 concat。
`torch.split` 按每个特征的 dim 拆分列表，用于后续 bias 提取。

### L270-288：Bias 提取

```python
if self._num_bias_features > 0:
    if self._bias_group_name == self._main_group_name:
        bias_feature_tensors = main_feature_tensors          # domain ⊆ all，共享 tensor
    else:
        ...                                                   # 单独 lookup
    bias_vec, bias_sum = self._extract_bias(bias_feature_tensors)
else:
    bias_sum = torch.zeros(main_features.size(0), 1)          # 无 bias group 时填充 0
```

`_extract_bias`（L28-37）是 `@torch.fx.wrap` 函数：

```python
def _extract_bias_fn(feature_tensors):
    bias_vec_list = [ft[:, 0:1] for ft in feature_tensors]   # 每特征取首维
    bias_vec = torch.cat(bias_vec_list, dim=1)                # [B, num_bias_features]
    bias_sum = bias_vec.sum(dim=1, keepdim=True)              # [B, 1]
    return bias_vec, bias_sum
```

每个特征的首维作为 bias，求和得一个 scalar bias。这是对 TF 实现中每个特征独立 bias 的模拟。

### L290-291：DCNv2 Cross

```python
if self.cross_net is not None:
    cross_output = self.cross_net(main_features)  # [B, main_group_dim]
```

CrossV2 对 main group 所有特征做显式交叉。输出维度 = 输入维度。

### L293-307：CDOT 输入准备

```python
if self.cdot is not None:
    if self._cdot_group_name == self._main_group_name:
        cdot_feature_tensors = main_feature_tensors
    else:
        cdot_features = grouped_features[self._cdot_group_name]
        ...  # split into per-feature tensors
    cdot_input = self._extract_cdot(cdot_feature_tensors)    # [B, num_slots, 16]
    allint_out, allint_mid_out = self.cdot(cdot_input)       # [B, 8], [B, 12]
```

`_extract_cdot`（L40-55）是 `@torch.fx.wrap` 函数：

```python
def _extract_cdot_fn(feature_tensors, cdot_input_dim):
    slots = []
    for ft in feature_tensors:
        if ft.size(1) >= cdot_input_dim:    # 特征 dim ≥ 16 → 截断首 16 维
            slots.append(ft[:, :16])
        else:
            pad = zeros(B, 16 - ft_dim)      # 特征 dim < 16 → 左 pad 到 16
            slots.append(cat([ft, pad], dim=1))
    return stack(slots, dim=1)               # [B, 3, 16]
```

domain 组 3 个特征（mmb_id=32, item_id=32, f_req_page=4）→ pad/截断到 16 → `[B, 3, 16]`。
CDOT 输出两路：allint_out`[B, 8]` + allint_mid_out`[B, 12]`。

### L309-320：多组件 concat（Component Concat）

```python
concat_parts = []
concat_parts.append(self.component_ln["main"](main_features))     # LN(all) [B, 600+]
if self.cross_net is not None:
    concat_parts.append(self.component_ln["cross"](cross_output)) # LN(cross) [B, 600+]
if self.cdot is not None:
    concat_parts.append(self.component_ln["allint_out"](allint_out)) # [B, 8]
    if self._num_bias_features > 0:
        concat_parts.append(self.component_ln["bias"](bias_vec))    # [B, 3]
    concat_parts.append(self.component_ln["allint_mid"](allint_mid_out)) # [B, 12]
deep_input = torch.cat(concat_parts, dim=1)
```

输入到 EPNet 的 tensor 结构：

```
[LN(main): ~600, LN(cross): ~600, LN(allint_out): 8, LN(bias): 3, LN(allint_mid): 12]
→ deep_input: [B, ~1223]
```

每个组件独立 LN 后再 concat，确保各组件分布独立，不被大维度的 main/cross 主导。

### L322-325：LHUC-EPNet 缩放

```python
if self.epnet is not None:
    lhuc_features = grouped_features[self._lhuc_group_name]   # domain group embedding
    ep_scale = self.epnet(lhuc_features)                      # [B, deep_concat_dim]
    deep_input = deep_input * ep_scale                         # element-wise
```

domain group 特征 → LHUC-EPNet → scale 向量（~1223 维）→ 逐元素乘 deep_input。
这是**全局性**的个人化——用一个域（domain）决定整个 deep_input 每个维度的放大/缩小。

### L327-332：Step 1 — Tower PPNet 隐层

```python
tower_hidden = {}
for i, task_tower_cfg in enumerate(self._task_tower_cfgs):
    tower_name = task_tower_cfg.tower_name
    lhuc_input = lhuc_features if self.epnet is not None else deep_input
    tower_hidden[tower_name] = self._task_towers[i](deep_input, lhuc_input)
```

- `lhuc_input` = domain group embedding（EPNet 已用，PPNet 各层 gate 也要用）
- `self._task_towers[i]` = LHUC_PPNet(deep_input, lhuc_input) → [B, 128]
- 每个 tower 独立计算，参数不共享

**LHUC-PPNet 内部逐层：**

```
layer 0: gate = GateMLP_0(lhuc_input)  → scale = tanh(gate*0.2)*5.0 + 1.0
         deep_input *= scale            → Linear(1223→512)  → ReLU
         → [B, 512]
layer 1: gate = GateMLP_1(lhuc_input)  → scale = tanh(gate*0.2)*6.0 + 1.0
         [B, 512] *= scale             → Linear(512→256)   → ReLU
         → [B, 256]
layer 2: gate = GateMLP_2(lhuc_input)  → scale = tanh(gate*0.2)*7.0 + 1.0
         [B, 256] *= scale             → Linear(256→128)   → 无激活
         → [B, 128]
```

每层的 gate MLP 都是独立的 `[domain_dim → 512 → cur_dim]`。

### L336-347：Step 2 — Relation MLP

```python
relation_hidden = {}
for task_tower_cfg in self._task_tower_cfgs:
    if task_tower_cfg.HasField("relation_mlp"):
        rel_inputs = [tower_hidden[tower_name]]               # 本 tower hidden
        for rel_name in task_tower_cfg.relation_tower_names:
            rel_inputs.append(relation_hidden[rel_name])       # 关联 tower 的 post-MLP hidden
        relation_hidden[tower_name] = self._relation_mlps[tower_name](
            torch.cat(rel_inputs, dim=1)
        )
    else:
        relation_hidden[tower_name] = tower_hidden[tower_name]  # 透传
```

对 CVR tower：

```
rel_inputs = [tower_hidden["cvr"](B,128), relation_hidden["ctr"](B,128)]  # (B, 256)
→ Relation MLP: 256 → 64 → 32 → (B, 32)
→ relation_hidden["cvr"] = (B, 32)
```

对 CTR tower（无 relation_mlp）：

```
relation_hidden["ctr"] = tower_hidden["ctr"]  # (B, 128)，直接透传
```

### L349-364：Step 3 — 最终 logit 计算

```python
tower_outputs = {}
ctr_logits_val = None
for task_tower_cfg in self._task_tower_cfgs:
    tower_output = self._tower_final[tower_name](relation_hidden[tower_name])

    if ctr_logits_val is not None and self._cvr_add_ctr_logits:
        tower_output = tower_output + ctr_logits_val       # CVR logit += CTR logit
    else:
        tower_output = tower_output + bias_sum              # 加 bias

    tower_outputs[tower_name] = tower_output

    if tower_name == self._ctr_tower_name:
        ctr_logits_val = tower_output                       # 缓存 CTR logit 供后续 tower 使用
```

**CTR logit:**

```
self._tower_final["ctr"](relation_hidden["ctr"])     # Linear(128→1)
→ logit_ctr = Linear(B,128→1) + bias_sum              # (B, 1)
```

**CVR logit:**

```
self._tower_final["cvr"](relation_hidden["cvr"])     # Linear(32→1)
→ logit_cvr_raw = Linear(B,32→1)                      # (B, 1)
→ logit_cvr = logit_cvr_raw + logit_ctr               # (B, 1)  — cvr_add_ctr_logits
→ logit_cvr += bias_sum                                # (B, 1)  — 实际是 bias_sum 只加一次
```

注意：L356-359 的逻辑是：

- 如果 `ctr_logits_val is not None AND cvr_add_ctr_logits` → CVR logit + CTR logit（不含 bias_sum）
- 否则 → CVR logit + bias_sum

所以 CVR tower 的最终 logit = `tower_final(relation_hidden) + ctr_logits`（没有额外 bias_sum）。这是符合预期的——CTR logit 已经包含了 bias_sum。

### L366：输出转换

```python
return self._multi_task_output_to_prediction(tower_outputs)
```

调用基类方法：对每个 tower，取 loss 配置 → `_output_to_prediction_impl` → 输出 `{logits_ctr, probs_ctr, logits_cvr, probs_cvr}`。

______________________________________________________________________

## 四、完整数据流图

```
Batch
  │
  ▼
build_input → EmbeddingGroup → grouped_features
  │
  ├── "all" ──────→ main_features (B, ~600)
  │                    ├── CrossV2 ──→ cross_output (B, ~600)
  │                    ├── extract_bias ──→ bias_vec (B, num_bias)
  │                    │                      └── bias_sum (B, 1)
  │                    └── ComponentLN ──┐
  │                                     │
  ├── "domain" ──→ cdot_input (B, 3, 16)       │
  │                    └── CDOT ──→ allint_out (B, 8) ──→ ComponentLN ──┐
  │                              └→ allint_mid (B, 12) ─→ ComponentLN ──┤
  │                                                                      │
  └── "domain" ──→ lhuc_features ──→ LHUC-EPNet ──→ ep_scale (B, ~1223) │
                                             │                          │
                                             ▼                          ▼
                                       deep_input = cat(components) (B, ~1223)
                                             │
                                             ▼
                                       deep_input *= ep_scale (B, ~1223)
                                             │
                                   ┌─────────┴─────────┐
                                   │                    │
                              PPNet_CTR            PPNet_CVR
                              [512,256,128]        [512,256,128]
                                   │                    │
                              tower_hidden          tower_hidden
                              ["ctr"] (B,128)      ["cvr"] (B,128)
                                   │                    │
                                   │           concat(cvr, ctr_hidden) (B,256)
                                   │                    │
                                   │           Relation MLP [64,32] (B,32)
                                   │                    │
                              Linear(128→1)       Linear(32→1)
                                   │                    │
                              logit_ctr (B,1)      logit_cvr_raw (B,1)
                                   │                    │
                                   └────── add ─────────┘
                                             │
                                        logit_cvr (B,1)
                                             │
                                        sigmoid → probs
```

## 五、关键设计要点总结

| 设计                            | 位置               | 意图                                           |
| ------------------------------- | ------------------ | ---------------------------------------------- |
| Component LN                    | L155-165, L309-318 | 各组件分布独立标准化，防大维度主导             |
| LHUC-EPNet scale 范围 [-3,5]    | lhuc_net.py:L63    | 可正可负，Flexible 门控                        |
| LHUC-PPNet scale per-layer 递增 | lhuc_net.py:L154   | 深层更大自由度                                 |
| scale-before-Dense              | lhuc_net.py:L156   | 匹配 TF 实现顺序                               |
| Bias 首维提取                   | L28-37             | 每个特征首维专做 bias                          |
| CDOT 两路输出                   | cdot.py:L110       | allint_out（变换结果）+ allint_mid（权重本身） |
| Relation MLP 读 relation_hidden | L341-342           | 支持链式依赖（A→B→C）                          |
| cvr_add_ctr 是 logit 级加法     | L356-357           | 独立于 hidden 级的 relation_mlp                |
