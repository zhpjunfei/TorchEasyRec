# 新帖冷启动模型侧优化方案

## 1 问题定性

辛普森悖论的**根因不是模型预测不准，是服务端分配不均**：

| 指标         | 新帖   | 老帖   | 解读                                          |
| ------------ | ------ | ------ | --------------------------------------------- |
| 曝光次数占比 | 16.88% | 83.12% | 新帖曝光太少                                  |
| 曝光UV占比   | 71.46% | 99.96% | 28.5%的用户从没见过新帖——不可能产生点击或转化 |
| 购买UV占比   | 9.63%  | 22.14% | 覆盖不足直接导致转化损失                      |

**模型侧能做的**：提高新帖评分准确性 → 排名上升 → 获得更多曝光机会。间接且有限，预期贡献约 20%（其余 80% 靠服务端策略）。

______________________________________________________________________

## 2 方案优先级

```
                             对辛普森悖论的直接影响
                             低 ←——————————→ 高

       模型侧 ──────→  对比学习       ┌─────────────────┐
                        Loss 加权     │ 服务端策略 (P0)  │
                                      │ · 探索配额       │
                                      │ · UV 曝光上限    │
                                      │ · 疲劳控制       │
                                      └─────────────────┘
```

______________________________________________________________________

## 3 各方案详述

### 3A 组合特征交叉 — `pub_hours × cate_id` / `price_tag` / `brand`

**思路**：在 SQL 中对 `pub_hours` 按业务含义分 5 桶（`<1h/1-6h/6-24h/24-72h/≥72h`），与 `cate_id_path`/`price_tag`/`brand` 拼接成组合 key。模型用 `id_feature` 读取，效果等价于 `combo_feature`。

**与原始方案的区别**：

|          | 原始方案（废弃）                     | 当前方案                         |
| -------- | ------------------------------------ | -------------------------------- |
| 分桶方式 | 复用 FG expr_feature 的 20 边界      | SQL 中自定义 5 桶                |
| 边界维护 | SQL 需同步 FG config，易断裂         | 独立自主，无同步问题             |
| 特征类型 | `combo_feature`（FG 不支持链式引用） | `id_feature`（直接读取预计算列） |
| 实现位置 | config 中定义                        | SQL 预计算 + config 读取         |

**分桶设计**（基于 1.34 亿样本分布）：

```
桶 0: < 1h     冷启核心区  (~p0-p20)
桶 1: 1h ~ 6h  冷启延伸区  (~p20-p42)
桶 2: 6h ~ 24h 当天发布    (~p42-p70)
桶 3: 24h ~ 72h 近几天     (~p70-p90)
桶 4: ≥ 72h    老帖        (~p90+)
```

**SQL 实现**（`_shuffled_60d_v3.sql`）：

```sql
,CONCAT(
  CASE WHEN pub_hours >= 0 AND pub_hours < 1.0  THEN '0'
       WHEN pub_hours >= 0 AND pub_hours < 6.0  THEN '1'
       WHEN pub_hours >= 0 AND pub_hours < 24.0 THEN '2'
       WHEN pub_hours >= 0 AND pub_hours < 72.0 THEN '3'
       ELSE '4' END, '_', cate_id_path
) AS phour_x_cate
,CONCAT(..., '_', price_tag) AS phour_x_price
,CONCAT(..., '_', brand)     AS phour_x_brand
```

**Config 实现**（`id_feature` + ZCH）：

```protobuf
id_feature {
    feature_name: "phour_x_cate"
    expression: "item:phour_x_cate"
    embedding_dim: 24
    zch { zch_size: 1000000  eviction_interval: 2  lfu {}
        threshold_filtering_func: "lambda x: dynamic_threshold_filter(x, 3.0)" }
}
```

**独立 config**：`home_flow_2604_pepnet_v4_cdot32_weight_long_v1f_combo.config`

**预期收益**：低。改善模型对不同品类/价格的冷启曲线建模。

______________________________________________________________________

### 3B 开启对比学习

**配置变更**（0 行代码）：

```protobuf
pepnet_dcn_ple {
    contrastive_loss_enabled: true
}
```

**作用链**：

```
训练时:
  title_vector（当前 item 标题语义）↔ behavior_emb（DIN 输出）
  对比 loss 拉近语义与行为相近的 pair
      ↓
服务时:
  新帖标题 "Nike 跑鞋" → 与用户点过的 "Nike鞋" behavior 语义相近
   → 通过共享 DIN 参数获得合理评分
```

**这不是直接改善新帖 item_id embedding**，而是改善 DIN 空间结构，让新帖通过内容相似性间接受益。

**前提**：数据 pipeline 产出 `title_vector`，覆盖新帖样本。

**独立 config**：`home_flow_2604_pepnet_v4_cdot32_weight_long_v1f_contrastive.config`

**预期收益**：模型侧最高性价比方案，风险极低。

______________________________________________________________________

### 3C Loss 加权

#### 数据 pipeline

SQL 已更新，一次产出 5 个 `fresh_weight` 变体：

```sql
CASE WHEN pub_hours >= 0 AND pub_hours < 1.0 THEN 3.0
     WHEN pub_hours >= 0 AND pub_hours < 5.0 THEN 1.5
     ELSE 1.0
END AS fresh_weight                           -- 分档推荐（默认）
,CASE WHEN pub_hours >= 0 AND pub_hours < 5.0 THEN 2.0
      ELSE 1.0
END AS fresh_weight_binary_2x_5h              -- 简单二值
,CASE WHEN pub_hours >= 0 AND pub_hours < 2.0 THEN 3.0
      ELSE 1.0
END AS fresh_weight_binary_3x_2h              -- 窄窗口高提权
,CASE WHEN pub_hours >= 0 AND pub_hours < 1.0 THEN 5.0
      ELSE 1.0
END AS fresh_weight_binary_5x_1h              -- 极窄极端提权
,CASE WHEN pub_hours >= 0 AND pub_hours < 0.5 THEN 4.0
     WHEN pub_hours >= 0 AND pub_hours < 2.0 THEN 2.0
     ELSE 1.0
END AS fresh_weight_tiered_v2                 -- 替代分档
```

#### `pub_hours` 样本分布（1.34 亿样本）

| 分位      | p1     | p5   | p25  | p30  | p35  | p40  | p45  | p50  | p95   | p99   |
| --------- | ------ | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ----- | ----- |
| pub_hours | -12.58 | 0.04 | 2.50 | 3.47 | 4.68 | 6.11 | 7.65 | 9.30 | 42.65 | 74.40 |

- p1 负值（-12.58）：数据质量问题，SQL 用 `>= 0` 保护，将负值映射为 1.0x
- 右偏分布：p50 = 9.3h，90% 样本在发布后 2 天内

#### 各变体覆盖分析

| 变体                  | 逻辑                  | 新帖覆盖    | 有效权重 | 归一化后权比          |
| --------------------- | --------------------- | ----------- | -------- | --------------------- |
| `fresh_weight` (默认) | `<1h→3x, 1-5h→1.5x`   | ~18% / ~20% | avg=1.43 | 2.1x / 1.05x / 0.7x   |
| `binary_2x_5h`        | `<5h→2x`              | ~38%        | avg=1.38 | 1.45x / 0.72x         |
| `binary_3x_2h`        | `<2h→3x`              | ~25%        | avg=1.50 | 2.0x / 0.67x          |
| `binary_5x_1h`        | `<1h→5x`              | ~18%        | avg=1.72 | 2.9x / 0.58x          |
| `tiered_v2`           | `<0.5h→4x, 0.5-2h→2x` | ~10% / ~25% | avg=1.40 | 2.86x / 1.43x / 0.71x |

#### Config 配置

```protobuf
data_config {
    sample_weight_fields: "search_weight"
    sample_weight_fields: "fresh_weight"       # 切换实验只需改此行
}
task_towers {
    tower_name: "ctr"
    sample_weight_name: "fresh_weight"         # 与上面对应
}
```

**独立 config**：`home_flow_2604_pepnet_v4_cdot32_weight_long_v1f_weight.config`

**风险**：新帖平均价格 861 > 老帖 665，权重可能混淆 freshness 与 price。训练后需验证新帖子集独立 AUC。

______________________________________________________________________

### 3D Freshness Gate（暂缓）

**思路**：在 EPNet 的 element-wise scale 之外，并行一个轻量 freshness 门控。

```python
if self.embedding_group.has_group("freshness"):
    freshness_dim = self.embedding_group.group_total_dim("freshness")
    self.freshness_gate = nn.Sequential(
        nn.Linear(freshness_dim, 64),
        nn.ReLU(),
        nn.Linear(64, deep_concat_dim),
        nn.Sigmoid(),
    )

if hasattr(self, 'freshness_gate'):
    fg_scale = self.freshness_gate(grouped_features["freshness"])
    deep_input = deep_input * (1.0 + self._boost_ratio * fg_scale)
```

**状态**：暂缓。等 Loss 加权和对比学习的 A/B 结果出来后再决定是否需要。

______________________________________________________________________

## 4 独立实验设计

2 个已实现 + 1 个规划中：

```
baseline                          # 原生产 config
  ├── 对比学习 (3B) → contrastive.config
  ├── Loss加权 (3C) → weight.config
  └── combo特征 (3A) → combo.config    ← SQL 预计算 + id_feature
```

推荐实验顺序：先跑风险最低的 contrastive，再跑 weight。

| 实验       | config      | 代码量         | 风险             | 预估收益           |
| ---------- | ----------- | -------------- | ---------------- | ------------------ |
| 对比学习   | contrastive | 0 行           | 极低             | 中（DIN 空间改善） |
| Loss 加权  | weight      | 0 行           | 中（price 混淆） | 中-高              |
| combo 特征 | combo       | SQL + 0 行代码 | 低               | 低                 |

______________________________________________________________________

## 5 执行路线

```
sprint 1                    sprint 2                  sprint 3
┌──────────────────┐       ┌──────────────────┐      ┌──────────────────┐
│ 服务端策略        │  →   │ 模型侧 A/B       │  →   │ 择优上线         │
│ · 探索配额       │       │                  │      │                  │
│ · UV 曝光上限    │       │ 实验1: contrastive│      │ 如果两个都有效   │
│ · 疲劳控制       │       │ 实验2: weight    │      │ 合并上线         │
│                  │       │                  │      │                  │
│ pipeline         │       │ 可选: 时间切分   │      │ Freshness Gate   │
│ fresh_weight 产出│       │ TAE (方案A)     │      │ (如果仍需要)     │
└──────────────────┘       └──────────────────┘      └──────────────────┘
```

______________________________________________________________________

## 6 验证指标

| 指标                 | 当前   | 目标              | 验证对象                    |
| -------------------- | ------ | ----------------- | --------------------------- |
| 新帖曝光UV占比       | 71.46% | >85%              | 服务端策略                  |
| 新帖 UVCTR           | 28.49% | >35%              | 服务端 + 模型               |
| 新帖 PVCTR           | 4.99%  | >4.5%（合理下降） | 服务端                      |
| 新帖购买UV占比       | 9.63%  | >15%              | 服务端 + 模型               |
| 新帖独立 AUC（新增） | 无     | 新增 baseline     | 模型侧（所有实验）          |
| 新帖 GAUC（新增）    | 无     | 新增 baseline     | 模型侧（所有实验）          |
| 新帖 price 分桶 AUC  | 无     | 新增 baseline     | Loss 加权（price 混淆监控） |

______________________________________________________________________

## 7 不采纳方案及理由

| 不采纳                                                        | 理由                                      |
| ------------------------------------------------------------- | ----------------------------------------- |
| CVR Shortcut 修正                                             | 不是偏见：全零输入输出常量是合理 baseline |
| DCNv2 特征重复                                                | 已有 4 层 cross + low_rank=256，足够      |
| CDOT 增强                                                     | 任务不匹配                                |
| 新帖辅助 tower                                                | 训练数据不足（仅 16.88%）                 |
| Exploration Head                                              | 有价值但属长期，工作量高                  |
| combo 特征（FG原生 `combo_feature` 引用 `expr_feature` 输出） | FG 框架不支持链式引用，`no input` 报错    |

______________________________________________________________________

## 8 相关文件

| 文件                              | 说明                                          |
| --------------------------------- | --------------------------------------------- |
| `config/*_v1f.config`             | baseline 生产 config                          |
| `config/*_v1f_combo.config`       | SQL 预计算 + id_feature 方案                  |
| `config/*_v1f_weight.config`      | Loss 加权（fresh_weight）                     |
| `config/*_v1f_contrastive.config` | 对比学习                                      |
| `sql/sample_v3/*_60d_v3.sql`      | 产出 fresh_weight + phour_x\_\* 列的 pipeline |
| `sql/sample_v3/*_60d_v3_tae.sql`  | train/val 切分（当前为随机 99/1）             |
