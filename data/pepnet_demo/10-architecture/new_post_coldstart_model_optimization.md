# 新帖冷启动模型侧优化方案

## 背景

当前新老帖子在 PVCTR 与 UVCTR/UVCVR 之间存在辛普森悖论：

| 指标       | 新帖          | 非新帖 | 问题         |
| ---------- | ------------- | ------ | ------------ |
| PVCTR      | **4.99%** ✅  | 3.92%  | 新帖更高     |
| UVCTR      | **28.49%** ❌ | 45.82% | 新帖更低     |
| 购买UV占比 | **9.63%** ❌  | 22.14% | 新帖更低     |
| 曝光UV占比 | **71.46%** ❌ | 99.96% | 新帖覆盖不足 |

根因：新帖集中暴露给少量用户（曝光量占 16.88%，曝光UV仅占 71.46%），单用户疲劳导致 UV 级指标差，但 PV 级指标被同用户反复曝光稀释后反而好看。

以下方案从**模型侧**入手，配合服务端分发策略优化。

______________________________________________________________________

## 方案一：特征增强 — pub_hours_fg 交叉特征（工作量：低）

### 现状

`pub_hours_fg = max((event_unix_time - pub_time)/3600, 0.0)` 已作为单独的 bucketized 特征存在（20个分桶，embedding_dim=8），在 `all` 组中与其他 ~1200 个特征拼接。

### 改造

在 config 中新增组合特征，让新帖与品类/价格/品牌等信号做显式交叉：

**方案 1A：pub_hours_fg × 品类（推荐优先）**

```protobuf
feature_configs {
    combo_feature {
        feature_name: "pub_hours_fg_x_cate_id_path"
        combiner: "mul"
        feature_names: ["pub_hours_fg_emb", "cate_id_path_emb"]
        embedding_dim: 8
        hash_bucket_size: 200000
    }
}
```

**方案 1B：pub_hours_fg × 价格段**

```protobuf
feature_configs {
    combo_feature {
        feature_name: "pub_hours_fg_x_price_tag"
        combiner: "mul"
        feature_names: ["pub_hours_fg_emb", "price_tag_emb"]
        embedding_dim: 8
        hash_bucket_size: 500
    }
}
```

**方案 1C：pub_hours_fg × 发布者**

```protobuf
feature_configs {
    combo_feature {
        feature_name: "pub_hours_fg_x_publish_user"
        combiner: "mul"
        feature_names: ["pub_hours_fg_emb", "publish_user_emb"]
        embedding_dim: 8
        hash_bucket_size: 2170
    }
}
```

### 预期收益

- 模型能学到"不同品类的新帖冷启曲线不同"（如服装新帖可能比数码产品更容易被点击）
- 品类 × 新帖的交叉只在冷启阶段显著，模型自然给不同冷启阶段的帖子不同打分策略
- 纯 config 改动，无需写代码

### 工作量

- 新增 3-5 个 combo_feature 定义（config 修改）
- 在 `feature_names` 列表中加入相应特征名

______________________________________________________________________

## 方案二：样本级别 Loss 加权 — 新帖在 Loss 中获得更高权重（工作量：低）

### 现状

当前只有 `search_weight` 作为 CVR 的样本权重，加上 CVR task space indicator（click=1 权重 1.0，click=0 权重 0.12）。对新帖没有特殊加权。

### 改造

#### 2A：利用 sample_weight_fields（纯 config 方案）

如果上游数据 pipeline 可以为新帖样本生成一个 `fresh_weight`（如 `pub_hours_fg < 5 时 weight=2.0，否则 weight=1.0`），在配置中直接使用：

```protobuf
task_towers {
    tower_name: "ctr"
    label_name: "is_click"
    sample_weight_name: "fresh_weight"
    weight: 4.5
    ...
}
```

**优点**：零代码改动
**缺点**：需要数据 pipeline 侧产出字段

#### 2B：在 multi_task_rank.py 中增加 freshness-aware 加权（代码改动）

在 `loss()` 方法的 weight 计算逻辑中，将 `pub_hours_fg` 作为 freshness 信号引入：

```python
# in multi_task_rank.py loss()
if task_tower_cfg.HasField("freshness_weight_name"):
    freshness_val = batch.sparse_features.get("pub_hours_fg.emb")
    if freshness_val is not None:
        # pub_hours_fg 越小（帖子越新），权重越大
        fresh_weight = torch.sigmoid(2.0 - freshness_val)  # 归一化到 [0.5, 0.88]
        loss_weight = loss_weight * fresh_weight
```

需要：

1. 在 `TaskTower` proto 中增加字段 `freshness_weight_name`
1. 在 `multi_task_rank.py` 中读取和计算
1. 在 config 中配置

#### 2C：在 PEPNetDCNPLE.predict() 中修改 CVR Shortcut 的个性化偏置

利用 EPNet 已有的 LHUC 能力，在 `deep_input = deep_input * ep_scale` 之后，对新帖的 deep feature 做一个提升：

```python
# in predict(), after epnet
if self.training and self._freshness_aware_gate is not None:
    pub_hours = grouped_features.get("pub_hours_fg.emb")
    if pub_hours is not None:
        fresh_bias = self._freshness_aware_gate(pub_hours)  # Linear(8, deep_concat_dim)
        deep_input = deep_input + fresh_bias * fresh_bias_scale
```

### 预期收益

- 新帖样本在训练中获得更高的梯度占比，模型更关注新帖的预测准确率
- 结合辛普森悖论的分析，新帖的点击信号其实更积极（PVCTR 更高），上提权重有助于模型学习这个信号

### 工作量

- **2A**：数据 pipeline 产出字段（天数）
- **2B**：proto 新增字段 + multi_task_rank.py 约 15 行逻辑 + config 配置
- **2C**：pepnet_dcn_ple.py 约 20 行 + 初始化代码

______________________________________________________________________

## 方案三：启用 + 增强对比学习，改善冷启表征（工作量：中）

### 现状

PEPNetDCNPLE 有完整的 contrastive learning 框架（Phase 1a / Phase 2），当前 `contrastive_loss_enabled = false`。框架能力：

- behavior embedding（来自 click_50_seq DIN 输出）
- title semantic embedding
- column/bidirectional 对齐模式
- HardNegative + LogQ 采样

### 改造

#### 3A：启用对比学习（最小改动）

```protobuf
pepnet_dcn_ple {
    ...
    contrastive_loss_enabled: true
    contrastive_alignment_mode: "column"  # 或 "bidirectional"
}
```

#### 3B：新帖 HardNegative 增强

在 `pepnet_dcn_ple.py` 的对比学习部分，对 pub_hours_fg 小的样本强制增加 HardNegative 采样比例：

```python
# in loss(), after topk hard negatives
pub_hours = batch.sparse_features.get("pub_hours_fg_id")
if pub_hours is not None:
    # pub_hours_fg < 1 的样本（新帖），增加 hard negative 数量
    is_fresh = (pub_hours < 12).float()  # 12-hour bucket index
    K_fresh = K + (is_fresh * 50).int()  # 新帖多采 50 个 hard negative
    K_actual = min(K_fresh.max().item(), B - 1)
    _, topk = torch.topk(sim_c, K_actual + 1, dim=-1)
```

#### 3C：新帖特殊温度系数

新帖因为行为序列短（seq_len 小），对比学习温度会自动变大（`tau = 0.07 + 0.43 * exp(-0.1 * seq_len)`）。效果是：新帖对比 loss 更大，模型更关注拉近新帖的行为和语义。

这个机制已经存在，启用即可受益。

### 预期收益

- 新帖 item_id 通过标题语义和同类行为做 embedding 对齐 → 冷启 embedding 质量提升
- 新帖即使没有交互记录，也可以通过品类/标题找到语义近邻→行为相似用户的迁移
- 新帖的 item_id embedding 初始化不再是随机的，而是有语义先验

### 工作量

- proto 修改：无需（字段已存在）
- config 修改：开启 `contrastive_loss_enabled`
- 代码修改：可选（3B 约 20 行）

______________________________________________________________________

## 方案四：EPNet (LHUC) — 个性化新帖容忍度建模（工作量：中-高）

### 现状

EPNet 以 `domain` 组（mmb_id, item_id, f_req_page, f_req_domain）作为输入，生成 element-wise scale 作用于 concat 后的 deep feature。当前对所有帖子做统一缩放。

### 改造

#### 4A：将 pub_hours_fg 加入 LHUC Group

在 `domain` 组中增加 `pub_hours_fg`：

```protobuf
feature_groups {
    group_name: "domain"
    feature_names: "mmb_id"
    feature_names: "item_id"
    feature_names: "f_req_page"
    feature_names: "f_req_domain"
    feature_names: "pub_hours_fg"  # 新增
}
```

这样 EPNet 可以学到：对于不同用户，新帖应该被放大多少。例如：

- 活跃用户对新帖容忍度高 → scale > 1.0
- 挑剔用户对新帖容忍度低 → scale < 1.0

#### 4B：新增 freshness gate（更精细）

在 EPNet 输出的基础上，增加一个并行的 freshness gate：

```python
# in predict(), parallel to epnet
if self._freshness_gate is not None:
    pub_hours_feat = grouped_features["pub_hours_fg"]
    fresh_scale = self._freshness_gate(pub_hours_feat)  # Linear(8, 1) + Sigmoid
    fresh_scale = fresh_scale * self._freshness_boost_ratio  # e.g. 1.2
    deep_input = deep_input * fresh_scale  # 所有 tower 共享
```

### 预期收益

- 对不同用户实现个性化的新帖 tolerance 建模
- 不喜欢新帖的用户不会因为统一加噪而影响体验
- 喜欢新帖的用户的 CTR signal 被放大，模型学到正确模式

### 工作量

- EPNet group 增加 feature：config 修改
- freshness gate：pepnet_dcn_ple.py 新增约 30 行 + proto 新增 2 个字段

______________________________________________________________________

## 方案五：DCNv2 交叉网络显式加强新帖交互（工作量：低）

### 现状

DCNv2 有 4 层 cross network, low_rank=256，对所有 ~1200 个特征做自动交叉。pub_hours_fg 只是其中之一。

### 改造

#### 5A：pub_hours_fg 复制多份（Feature Duplication）

在 `all` group 中将 `pub_hours_fg` 重复列出 3-5 次：

```protobuf
feature_names: "pub_hours_fg"
feature_names: "pub_hours_fg"
feature_names: "pub_hours_fg"
```

DCNv2 的 cross layer 会对这些重复特征做更多显式交叉（feature crossing），让模型更关注 freshness 信号。

**注意事项**：需要在 `expr_feature` 中确认是否支持多份 embedding 复用（通常 hash embedding 共享参数，多次出现只增加交叉路径，不增加参数量）。

#### 5B：pub_hours_fg 放入单独的 cross-only group

如果 DCNv2 输入可以分 group（当前是全部 `all`），可以将 pub_hours_fg 放入一个专门的 small group 并在 DCNv2 前 concat。不过当前架构下比较困难。

### 预期收益

- DCNv2 的 cross network 会多学到 pub_hours_fg 与其他特征的交叉模式
- 新帖 × 用户偏好、新帖 × 时段、新帖 × 品类等交叉更充分

### 工作量

- config 修改：在 `feature_names` 中增加 2-4 行

______________________________________________________________________

## 方案六：CDOT 对生命周期做 domain 变换（工作量：高）

### 现状

CDOT 以 `domain` 组特征作为输入做 cross-domain output transformation，当前是 mmb_id + item_id + f_req_page + f_req_domain。

### 改造

将 `pub_hours_fg` 加入 CDOT group，使其参与 CDOT 的 domain-specific output 变换：

```protobuf
cdot_group_name: "domain"  # domain 组已包含 pub_hours_fg
```

CDOT 会对不同 freshness 的 item 学习不同的 output transformation（allint_out + allint_mid_out）。效果上相当于：

> CDOT 对"新帖 domain" 学习一套 output 缩放，对"老帖 domain"学习另一套。

### 预期收益

- CDOT 自适应不同生命周期的 output 分布
- 新帖的 logit 分布与老帖的分布对齐或差异化

### 工作量

- CDOT group 增加 pub_hours_fg：config 修改（如果已加入 domain 组则自动生效）
- 可能需要调整 CDOT input_dim 和 param 以容纳更多 slot

______________________________________________________________________

## 方案七：训练采样策略 — 新帖过采样（工作量：低）

### 现状

训练数据中新帖占比远低于老帖（曝光量 16.88%），模型天然偏向老帖。

### 改造

#### 7A：基于 pub_hours_fg 的 Negative Sampling 调整

在数据 pipeline 或 dataset 层，对新帖样本做上采样：

```python
# in dataset
is_new = (pub_hours_fg < 5.0).float()
sample_weight = is_new * (new_boost_ratio - 1.0) + 1.0  # new_boost_ratio = 2.0~5.0
```

#### 7B：Online Hard Negative Mining 改造成 freshness-aware

在训练过程中，对 pub_hours_fg 小的样本更可能被选为 hard negative。

### 预期收益

- 训练集中的新帖有效样本比例提升
- 模型不会因为新帖样本稀疏而欠拟合

### 工作量

- dataset 层改动：约 20 行
- 或 config 配置 sample_weight_fields

______________________________________________________________________

## 方案八（长期）：新增新帖 Exploration 辅助任务（工作量：高）

### 现状

当前只有 CTR 和 CVR 两个任务。

### 改造

新增第三个任务 tower：

```protobuf
task_towers {
    tower_name: "new_post_ctr"
    label_name: "is_click"
    sample_weight_name: "new_post_weight"
    weight: 1.0
    losses {
        binary_cross_entropy {}
    }
    metrics { auc {} }
}
```

并在 `PEPNetDCNPLE` 的 forward 中增加一个新的 tower 输出。这个 tower 只在 pub_hours_fg < 5 的样本上有 loss（其余样本 loss mask 掉），专门学习新帖的 CT R pattern。

```protobuf
# 配合 sample weight：新帖 weight=1.0，老帖 weight=0.0
# 在数据中产出 new_post_weight
sample_weight_fields: ["search_weight", "new_post_weight"]
```

### 预期收益

- 独立 tower 专门建模新帖的 CTR 模式，不受老帖数据干扰
- CVR tower 仍然共享底层表征（PLE extraction layers），但 tower 参数专属
- 可以通过 PLE 的 CGC routing 实现"新帖专用 expert + 共享 expert" 的组合

### 工作量

- proto 修改：PEPNetDCNPLE 增加 task tower 配置
- pepnet_dcn_ple.py 修改：forward 和 loss 增加 tower
- config 修改：新增 tower 配置
- 数据 pipeline：产出 new_post_weight

______________________________________________________________________

## 方案优先级矩阵

| 方案                          | 工作量 | 预期收益 | 风险           | 优先级 |
| ----------------------------- | ------ | -------- | -------------- | ------ |
| **一**：pub_hours_fg 交叉特征 | 低     | 中       | 极低           | P0     |
| **三**：启用对比学习          | 低     | 高       | 低（已有框架） | P0     |
| **二**：Loss 加权             | 低     | 高       | 低             | P0     |
| **五**：DCNv2 特征重复        | 低     | 中低     | 极低           | P1     |
| **七**：过采样                | 低     | 中       | 低             | P1     |
| **四**：EPNet 增强            | 中     | 中高     | 中             | P1     |
| **六**：CDOT 增强             | 高     | 中       | 高             | P2     |
| **八**：新帖辅助任务          | 高     | 高       | 中             | P2     |

### 推荐首发组合（P0）：最小改动，最大收益

```
方案一（交叉特征）+ 方案三（对比学习）+ 方案二/七（加权）
```

- **纯 config 改动**：方案一 + 方案三（仅开启开关）
- **代码改动**：方案二（multi_task_rank.py 约 20 行）
- **预期效果**：模型对新帖预测准确率提升 + 新帖 embedding 质量改善

### 验证方式

1. **离线 AUC 对比**：对新帖子集（pub_hours_fg < 5）计算独立 AUC
1. **GAUC 分组**：G roup AUC 按用户分组后，看新帖 GAUC 是否有提升
1. **Long-tail 排序**：新帖在 top-20 中的占比变化
1. **在线 AB**：对比新帖曝光 UV 占比、UV CTR、买 购 UV 占比

______________________________________________________________________

## 配套服务端策略（补充）

模型侧优化解决的是**预测准确率**问题，要彻底解决辛普森悖论还需服务端配合：

1. **UV 曝光上限**：每个新帖每天最多展示给 N 个用户（如 1000 UV）
1. **新帖探索配额**：每次请求中新帖占比不低于 5%（探索 + exploit）
1. **分阶段冷启**：0-1h 小流量试探 → 1-5h 加速放量 → 5h+ 正常分配
1. **新帖疲劳控制**：同一用户每天看到同一新帖不超过 3 次
