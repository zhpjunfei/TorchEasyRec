______________________________________________________________________

## date: 2026-07-02 tags: [experiment, v15, sie-cross, side-info, roadmap] status: proposed related: \["\[[v14-experiments]\]", "\[[v14-optimization-plan-codex]\]", "\[[v14-optimization-plan]\]"\]

# Side-Info Element-Wise Cross (SIEC) — 路线图

> 基于 v14 全量实验积累（28+ 实验、ots 全扫、seq_transformer 证否、BCE 校准分析）的新方向探索。

______________________________________________________________________

## 一、动机与背景

### 1.1 v14 积累的完整知识

| 维度                | 结论                                                                                     |
| ------------------- | ---------------------------------------------------------------------------------------- |
| **ots 全扫**        | GAUC_cvr 严格单调递增（0.005→0.50），ots050 +4.56pp，但边际衰减至 0.025pp/0.01           |
| **BCE 校准偏移**    | ots 越高 BCE_cvr 越低（0.494→0.384），校准恶化抵消线上收益；ots002 是校准-排序最佳平衡点 |
| **seq_transformer** | −0.06pp vs ots012，DIN 已充分捕捉 item 交互，TransformerEncoder 替换无效                 |
| **PLE 容量**        | 扩 4x（ots012_plebig −0.04pp, ple4x −0.07pp），瓶颈不在 PLE                              |
| **CVR tower 扩宽**  | [512,256,128]→[1024,512] −0.18pp，瓶颈不在 tower MLP                                     |
| **CDOT/DCNv2**      | output_dim 4→8（−0.11pp）、cross_num 4→6（−0.19pp），config-only 杠杆已穷尽              |
| **CTCVR/ESMM**      | +0.29pp GAUC_cvr, −0.07pp CTR，中性偏负                                                  |
| **UV 级优化**       | 从未启动——所有 v6~v14 实验都以 pv 级 auc 为目标，uv 级 GAUC 优化尚未开始                 |

### 1.2 未探索的空间

**side-info 交叉是完全空白的区域。**

当前架构中，每个 sequence_group（如 click_50_seq）包含 17-20 个 side info 字段（item_id、cate_id_path、brand、core_entity、price_tag 等），embedding 后 concat 成 216 维向量，直接喂给 DIN。

**问题**：DIN 的 attention 机制学的是"选哪些 token"，不是"不同语义维度如何交互"。item_id 的 24 维和 cate_id_path 的 12 维混在一个 216 维向量里，它们之间的交互完全依赖后续非线性层隐式学习，没有任何模块**显式地**对不同 side info 维度做元素级交叉。

**类比**：

- DCN/FM 对**静态特征**做了元素级交叉 → 有效
- DIN/Transformer 对**序列 token** 做了 attention → 有效但已饱和
- **side info 之间的元素级交叉** → 完全未探索

### 1.3 为什么现在是好时机？

1. **ots002 校准最优**：BCE_cvr 几乎不变（−0.003），线上 A/B 验证最优。在此基准上做 side-info 交叉，不破坏校准的前提下提升 GAUC。
1. **所有 config-only 杠杆已穷尽**：Phase 3 全部证否，需要新的架构级创新。
1. **seq_transformer 证否了"更好的 attention"**，但那是针对整个序列 embedding 的 attention 替换，与 side-info 交叉正交。

______________________________________________________________________

## 二、方案设计

### 2.1 核心思路：SIEC (Side-Info Element-Wise Cross)

```
click_50_seq 的 20 个 side info（各自不同 embedding_dim）
    │
    ├─ item_id        [N, 50, 24]
    ├─ cate_id_path    [N, 50, 12]
    ├─ brand           [N, 50, 16]
    ├─ core_entity     [N, 50, 16]
    ├─ price_tag       [N, 50, 8]
    ├─ spu_id          [N, 50, 24]
    │  ... 其余 14 个
    │
    ▼
Step 1: 对齐嵌入维度 (Linear 投影到 D=32)
    │
    ├─ item_id        [N, 50, 32]  ← 24→32
    ├─ cate_id_path    [N, 50, 32]  ← 12→32
    ├─ brand           [N, 50, 32]  ← 16→32
    ├─ core_entity     [N, 50, 32]  ← 16→32
    ├─ price_tag       [N, 50, 32]  ← 8→32
    ├─ spu_id          [N, 50, 32]  ← 24→32
    │
    ▼
Step 2: 有选择的 pairwise 交叉（只选 3 对 × 3 种操作 = 9 个子序列）
    │
    ├─ item_id × cate_id_path:  +, −, ×  → 3 个子序列 [N, 50, 32]
    ├─ item_id × brand:        +, −, ×  → 3 个子序列 [N, 50, 32]
    ├─ item_id × price_tag:    +, −, ×  → 3 个子序列 [N, 50, 32]
    │
    ▼
Step 3: 交叉后降维 (3×32 → 32) + Dropout
    │
    ▼
Step 4: Concat 交叉产物 + 原始 main_group
    │
    ├─ 原始 main:    [N, 216] (DIN 输出)
    ├─ 交叉产物:     [N, 96] (9 个子序列均值池化)
    └─ Concat dim=1: [N, 312]
    │
    ▼
    接现有 PEPNet 管道（DCNv2 → CDOT → Bias → EPNet → PLE → Tower）
```

### 2.2 关键设计决策

| 决策                    | 选择                                         | 理由                                                                  |
| ----------------------- | -------------------------------------------- | --------------------------------------------------------------------- |
| 交叉哪些 side info 对？ | 只选 3 对：item×cate、item×brand、item×price | 语义互补性强；避免 20×20×3=1200 个交叉序列的爆炸                      |
| 对齐维度 D？            | D=32（取最大 embedding_dim）                 | 不损失任何 side info 信息；最小投影开销                               |
| 三种操作 +/−/×？        | 全部保留                                     | +融合、−对比、×协同，覆盖三种交互模式                                 |
| 交叉产物如何接入？      | 均值池化后 concat 到 DIN 输出                | 不破坏现有 DIN 路径；DIN 做 token 选择，SIEC 做维度交互，正交         |
| 放在 DIN 前还是后？     | DIN 后                                       | DIN 已经完成 token 级聚合，SIEC 在 pooled 层面做 side-info 交叉更自然 |
| 是否跨 sequence_group？ | 不跨                                         | click_10 和 click_50 用户群体不同，交叉意义不大                       |

### 2.3 为什么不做更多？

| 不做的事                    | 原因                                                                  |
| --------------------------- | --------------------------------------------------------------------- |
| 全量 20×20 pairwise         | 1200 个交叉序列，计算和存储爆炸                                       |
| 在 DIN attention 之前做交叉 | 时序不对，attention 还没做 token 选择                                 |
| 改 embedding 层维度         | 现有 embedding_dim 经过大量实验确定，不应改动                         |
| 替代 DIN                    | DIN 已充分工作（seq_transformer 证否了替换方案），SIEC 是补充而非替代 |

______________________________________________________________________

## 三、与 v14 实验记录的关联

### 3.1 配置文件的实际数据结构

`home_flow_2604_v14_config_c_ots002.config` 中 `click_50_seq` 的 side info embedding_dim：

| Side Info          | embedding_dim | Hash Size | 语义角色     |
| ------------------ | :-----------: | --------- | ------------ |
| item_id            |      24       | 1.96M     | 物品标识     |
| cate_id_path       |      12       | 200K      | 三级类目路径 |
| related_goods_ids  |      24       | 3M        | 关联商品     |
| brand              |      16       | 207K      | 品牌         |
| core_entity        |      16       | 145K      | 核心实体     |
| first_cate_id      |       8       | 300       | 一级类目     |
| second_cate_id     |       8       | 2K        | 二级类目     |
| third_cate_id      |      12       | 20K       | 三级类目     |
| price_tag          |       8       | 500       | 价格带       |
| spu_id             |      24       | 3M        | 标准产品     |
| discount_intensity |       8       | 180       | 折扣力度     |
| promotion_channel  |       4       | 80        | 促销渠道     |
| publish_user       |       8       | 2.2K      | 发布者       |
| site               |       8       | 410       | 站点         |
| dianpupingfen      |       4       | 70        | 店铺评分     |
| pinpaidengji       |       4       | 4 (定长)  | 品牌等级     |
| dianpufensi        |       4       | 90        | 店铺粉丝     |
| item_type          |       4       | 90        | 物品类型     |
| username           |       8       | 1.3M      | 用户名       |
| ts                 |       8       | 200K      | 时间戳       |

**维度跨度 4~32，无法直接做元素级交叉**，必须先投影对齐。

### 3.2 当前 main_group 数据流

```
click_50_seq (216维) → DIN → [216] → concat 其他特征 → DCNv2 → CDOT → Bias → PEPNet → PLE → Tower
```

SIEC 插入点：DIN 输出后，concat 到 main_group 之前。

```
click_50_seq (216维) → DIN → [216]
                    ↘ SIEC → [96]
                          ↓ concat
                    [312] → DCNv2 → ...
```

### 3.3 与 seq_transformer 实验的关系

| 维度     | seq_transformer (已证否)               | SIEC (本方案)                                |
| -------- | -------------------------------------- | -------------------------------------------- |
| 交叉粒度 | 整个 216 维序列 embedding              | 每个 side info 维度分别交叉                  |
| 信息流   | 目标 query 与整个序列的 soft alignment | side info 之间的硬编码组合                   |
| 参数     | Transformer 197K                       | 线性投影 ~2K + 交叉零参数                    |
| 先验     | 数据驱动 attention weight              | 手工设计交叉模式                             |
| 结论     | −0.06pp（DIN 已充分捕捉 item 交互）    | 待验证（交叉的是不同语义维度，非 item 交互） |

**关键区别**：seq_transformer 做的是"如何聚合序列"，SIEC 做的是"不同语义维度如何交互"。两者正交。

______________________________________________________________________

## 四、实验计划

### 4.1 实验矩阵

| 实验名          | 改动                     | 预期 GAUC_cvr |  预期 BCE_cvr  | 改动量        | 风险 |
| --------------- | ------------------------ | :-----------: | :------------: | ------------- | :--: |
| **sie_base**    | SIEC + ots002, 3 对交叉  |  +0.1~0.3pp   | ≈0.491（不变） | code + config |  低  |
| **sie_4pair**   | 增加到 4 对（+item×spu） | +0.15~0.35pp  |     ≈0.491     | code + config |  低  |
| **sie_no_proj** | 不加 post-proj 降维      |  +0.05~0.2pp  |     ≈0.491     | config        | 极低 |
| **sie_single**  | 只做 item×cate（2 操作） | +0.05~0.15pp  |     ≈0.491     | config        | 极低 |
| **sie_ots012**  | SIEC + ots012            |  +0.2~0.5pp   | 0.470（恶化）  | code + config |  中  |

### 4.2 快速验证路径

```
sie_single (config only, 1 天)
    │
    ├─ ≥ +0.1pp → sie_base (code + config, 2 天)
    │       │
    │       ├─ ≥ +0.2pp → sie_4pair (扩一对, 1 天)
    │       │       │
    │       │       └─ ≥ +0.3pp → 上线候选
    │       │
    │       └─ < +0.1pp → 放弃 SIEC, 转向其他方向
    │
    └─ < +0.05pp → 直接放弃
```

### 4.3 评估指标

| 指标         | 目标                  | 说明                              |
| ------------ | --------------------- | --------------------------------- |
| GAUC_cvr     | ≥ +0.1pp vs sie_base  | 主指标                            |
| BCE_cvr      | ≤ 0.495（不恶化校准） | 关键约束，ots002 的优势在于校准   |
| GAUC_ctr     | ≥ baseline（不劣化）  | 共享表征不被污染                  |
| gap_cvr      | ≤ 5.0pp               | 缩小离线-在线差距                 |
| 参数量增量   | ≤ 5K                  | 投影 + post_proj 参数             |
| 推理延迟增量 | ≤ 1ms                 | 交叉在 embedding 层之后、DIN 之前 |

______________________________________________________________________

## 五、代码改动范围

### 5.1 新增文件

| 文件                         | 功能          | 行数 |
| ---------------------------- | ------------- | ---- |
| `tzrec/modules/sie_cross.py` | SIEC 模块实现 | ~80  |

### 5.2 修改文件

| 文件                             | 改动                                | 行数       |
| -------------------------------- | ----------------------------------- | ---------- |
| `tzrec/models/pepnet_dcn_ple.py` | forward() 中插入 SIEC + config 解析 | ~20        |
| `tzrec/protos/model.proto`       | 新增 sie_cross 配置字段             | ~10        |
| `config/*.config`                | 实验配置                            | 各 5-10 行 |

### 5.3 核心代码结构

```python
# tzrec/modules/sie_cross.py

class SideInfoCross(nn.Module):
    """Side-info element-wise cross for sequence groups."""

    def __init__(self, align_dim=32, cross_pairs=None, dropout=0.1):
        super().__init__()
        # 对齐投影: 每个 side info → align_dim
        self._projs = nn.ModuleDict({
            name: nn.Linear(orig_dim, align_dim)
            for name, orig_dim in side_info_dims
        })

        # 交叉模式: (i, j) → +, −, ×
        self._cross_pairs = cross_pairs or [(0,1), (0,2), (0,4)]

        # 交叉后降维
        self._post_proj = nn.ModuleList([
            nn.Linear(align_dim * 3, align_dim)
            for _ in self._cross_pairs
        ])

    def forward(self, side_info_dict, seq_mask):
        # Step 1: 对齐维度
        aligned = {k: self._projs[k](v) for k, v in side_info_dict.items()}

        # Step 2: pairwise 交叉
        outputs = []
        for i, j in self._cross_pairs:
            a, b = aligned[i], aligned[j]
            cross = torch.cat([a+b, a-b, a*b], dim=-1)
            cross = self._post_proj[self._cross_pairs.index((i,j))](cross)
            outputs.append(cross)

        return self._dropout(torch.cat(outputs, dim=-1))


# tzrec/models/pepnet_dcn_ple.py 中 forward() 插入点

# 现有: main_features = din_output  # [N, 216]
# 新增:
if self._sie_cross is not None:
    sie_output = self._sie_cross(side_info_tensors, seq_mask)  # [N, 96]
    main_features = torch.cat([main_features, sie_output], dim=-1)  # [N, 312]
```

______________________________________________________________________

## 六、风险评估

### 6.1 技术风险

| 风险             | 概率 | 影响 | 缓解                                        |
| ---------------- | :--: | :--: | ------------------------------------------- |
| 交叉产物引入噪声 |  中  |  中  | sie_single 快速验证，无效即停               |
| 投影层过拟合     |  低  |  低  | align_dim=32 参数极少（~2K），dropout 控制  |
| 与 DIN 特征冗余  |  中  |  中  | sie_no_proj 对照验证必要性                  |
| 线上延迟增加     |  低  |  高  | 交叉在 embedding 层后，并行执行，预计 \<1ms |

### 6.2 与已知证否方向的边界

| 已证否方向                    | 为什么 SIEC 不同                            |
| ----------------------------- | ------------------------------------------- |
| seq_transformer (−0.06pp)     | 替换了整个 DIN 路径；SIEC 是 DIN 的**补充** |
| PLE capacity 4x (−0.04pp)     | 瓶颈不在 PLE；SIEC 在 PLE **之前**的输入层  |
| CVR tower 扩宽 (−0.18pp)      | 瓶颈不在 tower；SIEC 不碰 tower             |
| CDOT output_dim 4→8 (−0.11pp) | 信息压缩瓶颈；SIEC 在压缩**之前**           |

### 6.3 失败条件

如果出现以下情况，立即终止 SIEC 方向：

1. sie_single（config-only）< +0.05pp
1. sie_base 有效但 BCE_cvr 恶化 > 0.01
1. sie_base 有效但 GAUC_ctr 劣化 > 0.02pp

______________________________________________________________________

## 七、与 v14+ 路线图的关系

### 7.1 定位

SIEC 是 v14+ 路线图 **Phase 2（CVR Tower 架构升级）** 的替代/并行方向。

| 维度     | Phase 2 原方案                                       | SIEC 方案                           |
| -------- | ---------------------------------------------------- | ----------------------------------- |
| 修改位置 | CVR tower 内部（residual/expert/independent bottom） | main_group 输入层（side-info 交叉） |
| 改动量   | 大（需改 tower 结构 + loss）                         | 小（~100 行代码 + config）          |
| 风险     | 中（可能破坏已有收敛）                               | 低（DIN 路径不变，SIEC 可开关）     |
| 预期增益 | +0.5~1pp                                             | +0.1~0.3pp                          |
| 验证速度 | 2-3 周                                               | 3-5 天                              |

### 7.2 推荐策略

```
sie_single (config-only, 3天)
    │
    ├─ 有效 → 并行跑 Phase 2 原型 + sie_base
    │         （sie_base 快验证，Phase 2 慢验证）
    │
    └─ 无效 → 全力投入 Phase 2
```

### 7.3 长期规划

如果 SIEC 验证有效（≥+0.1pp），后续可扩展：

1. **增加交叉对**：从 3 对扩展到 6-8 对
1. **门控加权**：用可学习 gate 替代固定交叉模式
1. **跨 sequence_group**：click_50 × conversion_20 的跨行为交叉
1. **类 DCNv2 adaptive**：数据驱动的交叉选择，而非手工预设

______________________________________________________________________

## 八、里程碑

| 时间   | 里程碑          | 成功标准                           |
| ------ | --------------- | ---------------------------------- |
| Day 3  | sie_single 结果 | GAUC_cvr ≥ +0.05pp                 |
| Day 7  | sie_base 结果   | GAUC_cvr ≥ +0.1pp, BCE 不变        |
| Day 14 | sie_4pair 结果  | GAUC_cvr ≥ +0.2pp                  |
| Day 21 | 决策点          | 有效 → 上线候选；无效 → 转 Phase 2 |

______________________________________________________________________

## 九、与旧路线图的差异

| 维度                      | 旧路线图（v14-optimization-plan-codex.md） | 本路线图（SIEC）                            |
| ------------------------- | ------------------------------------------ | ------------------------------------------- |
| 未探索方向                | 实时特征（Phase 4）                        | **side-info 交叉（Phase 2 替代）**          |
| 对 seq_transformer 的判断 | "已证否 −0.06pp，放弃 sequence 方向"       | ✅ 同意，但 SIEC 与 sequence attention 正交 |
| 交叉粒度                  | 无                                         | **side info 维度级元素交叉**                |
| 改动量                    | Phase 2 需改 tower 结构（大）              | ~100 行代码（小）                           |
| 验证速度                  | 2-3 周                                     | 3-5 天                                      |
| 风险                      | 中（可能破坏收敛）                         | 低（可开关，不影响 DIN）                    |

**核心转变**：从"改模型内部结构"转向"改模型输入表示"。v14 的所有实验都在改模型内部（ots、PLE、tower、CDOT），但**从未改变过输入侧的 side-info 表示方式**。SIEC 是在输入层做第一个结构性创新。
