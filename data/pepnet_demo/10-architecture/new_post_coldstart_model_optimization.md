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

## 2 方案状态总览

| #   | 方案                                       | 状态      | 类型                              | 风险             |
| --- | ------------------------------------------ | --------- | --------------------------------- | ---------------- |
| 3A  | combo 特征（pub_hours × cate/price/brand） | ✅ 已完成 | SQL 预计算 + config id_feature    | 低               |
| 3B  | 对比学习                                   | ✅ 已完成 | config 1 行                       | 极低             |
| 3C  | Loss 加权（5 个变体）                      | ✅ 已完成 | SQL 预计算 + config sample_weight | 中（price 混淆） |
| 3D  | Freshness Gate                             | ⏸️ 暂缓   | 代码 ~40 行                       | 中               |

______________________________________________________________________

## 3 各方案详述

### 3A 组合特征交叉 — `pub_hours × cate_id` / `price_tag` / `brand`

**思路**：在 SQL 中对 `pub_hours` 按业务含义分 5 桶（`<1h/1-6h/6-24h/24-72h/≥72h`），与 `cate_id_path`/`price_tag`/`brand` 拼接成组合 key。模型用 `id_feature` 读取，绕过 FG `combo_feature` 不能引用 expr_feature 输出的限制。

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

**注意**：`cate_id_path`、`price_tag`、`brand` 为 `ARRAY<STRING>` 类型，SQL 中使用 `CONCAT_WS(',', col)` 转为逗号分隔字符串后再拼接。

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

SQL 一次产出 5 个 `fresh_weight` 变体 + 3 个 `phour_x_*` 组合列。

#### `pub_hours` 样本分布（1.34 亿样本）

| 分位      | p1     | p5   | p25  | p30  | p35  | p40  | p45  | p50  | p95   | p99   |
| --------- | ------ | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ----- | ----- |
| pub_hours | -12.58 | 0.04 | 2.50 | 3.47 | 4.68 | 6.11 | 7.65 | 9.30 | 42.65 | 74.40 |

- p1 负值（-12.58）：数据质量问题，SQL 用 `>= 0` 保护，将负值映射为 1.0x
- 右偏分布：p50 = 9.3h，90% 样本在发布后 2 天内

#### 各变体覆盖分析

| config                | sample_weight_name          | 逻辑                  | 新帖覆盖    | 有效权重 | 归一化权比            |
| --------------------- | --------------------------- | --------------------- | ----------- | -------- | --------------------- |
| `weight`              | `fresh_weight` (默认)       | `<1h→3x, 1-5h→1.5x`   | ~18% / ~20% | avg=1.43 | 2.1x / 1.05x / 0.7x   |
| `weight_binary_2x_5h` | `fresh_weight_binary_2x_5h` | `<5h→2x`              | ~38%        | avg=1.38 | 1.45x / 0.72x         |
| `weight_binary_3x_2h` | `fresh_weight_binary_3x_2h` | `<2h→3x`              | ~25%        | avg=1.50 | 2.0x / 0.67x          |
| `weight_binary_5x_1h` | `fresh_weight_binary_5x_1h` | `<1h→5x`              | ~18%        | avg=1.72 | 2.9x / 0.58x          |
| `weight_tiered_v2`    | `fresh_weight_tiered_v2`    | `<0.5h→4x, 0.5-2h→2x` | ~10% / ~25% | avg=1.40 | 2.86x / 1.43x / 0.71x |

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
```

**状态**：暂缓。等 3A/3B/3C 实验出结果后再决定是否需要。

______________________________________________________________________

## 4 独立实验设计

### 现有 config 文件总览

```
baseline                           *v1f.config
  ├── 对比学习 (3B)                 *v1f_contrastive.config
  ├── Loss 加权 (3C, 默认 tiered)   *v1f_weight.config
  ├── Loss 加权 (binary_2x_5h)      *v1f_weight_binary_2x_5h.config
  ├── Loss 加权 (binary_3x_2h)      *v1f_weight_binary_3x_2h.config
  ├── Loss 加权 (binary_5x_1h)      *v1f_weight_binary_5x_1h.config
  ├── Loss 加权 (tiered_v2)         *v1f_weight_tiered_v2.config
  └── combo 特征 (3A)               *v1f_combo.config
```

### 推荐实验顺序

```
Phase 1: contrastive   → 风险最低，先跑先确认
Phase 2: weight(默认)  → 验证 Loss 加权是否有效
Phase 3: combo         → 验证组合特征是否有效
Phase 4: 其余 weight   → 如果 weight 有效，调优阈值
```

### 上线决策

| 实验离线 AUC               | 决策            |
| -------------------------- | --------------- |
| 新帖子集 AUC 提升 < 0.5%   | 不上线          |
| 新帖子集 AUC 提升 ≥ 0.5%   | AB 测试         |
| AB 正向且 price 分桶无异常 | 全量上线        |
| AB 正向但 price 分桶有偏   | 调整权重/桶阈值 |

______________________________________________________________________

## 5 验证指标

| 指标                 | 当前   | 目标              | 验证对象      |
| -------------------- | ------ | ----------------- | ------------- |
| 新帖曝光UV占比       | 71.46% | >85%              | 服务端策略    |
| 新帖 UVCTR           | 28.49% | >35%              | 服务端 + 模型 |
| 新帖 PVCTR           | 4.99%  | >4.5%（合理下降） | 服务端        |
| 新帖购买UV占比       | 9.63%  | >15%              | 服务端 + 模型 |
| 新帖独立 AUC（新增） | 无     | 新增 baseline     | 所有实验      |
| 新帖 GAUC（新增）    | 无     | 新增 baseline     | 所有实验      |
| 新帖 price 分桶 AUC  | 无     | 新增 baseline     | Loss 加权实验 |

______________________________________________________________________

## 6 不采纳方案及理由

| 不采纳                                        | 理由                                      |
| --------------------------------------------- | ----------------------------------------- |
| CVR Shortcut 修正                             | 不是偏见：全零输入输出常量是合理 baseline |
| DCNv2 特征重复                                | 已有 4 层 cross + low_rank=256，足够      |
| CDOT 增强                                     | 任务不匹配                                |
| 新帖辅助 tower                                | 训练数据不足（仅 16.88%）                 |
| Exploration Head                              | 有价值但属长期，工作量高                  |
| 原生 `combo_feature` 引用 `expr_feature` 输出 | FG 框架不支持链式引用，`no input` 报错    |

______________________________________________________________________

## 7 相关文件

### Config 文件

| 文件                               | 说明                              |
| ---------------------------------- | --------------------------------- |
| `*_v1f.config`                     | baseline 生产 config              |
| `*_v1f_contrastive.config`         | 对比学习                          |
| `*_v1f_weight.config`              | Loss 加权（默认 tiered）          |
| `*_v1f_weight_binary_2x_5h.config` | Loss 加权（2x, \<5h）             |
| `*_v1f_weight_binary_3x_2h.config` | Loss 加权（3x, \<2h）             |
| `*_v1f_weight_binary_5x_1h.config` | Loss 加权（5x, \<1h）             |
| `*_v1f_weight_tiered_v2.config`    | Loss 加权（\<0.5h→4x, 0.5-2h→2x） |
| `*_v1f_combo.config`               | pub_hours × cate/price/brand      |

### SQL / Pipeline 文件

| 文件                                | 说明                                              |
| ----------------------------------- | ------------------------------------------------- |
| `sql/sample_v3/*_60d_v3.sql`        | 产出所有 fresh_weight + phour_x\_\* 列的 pipeline |
| `sql/sample_v3/*_60d_v3_tae.sql`    | train/val 切分（当前为随机 99/1）                 |
| `sql/sample_v3/*_pyfg_encoded_v3`   | FG 编码 runner（Python）                          |
| `sql/sample_v3/*_fix_sample_v3.sql` | 基础宽表建表语句                                  |
| `sql/sample_v3/*_fg_v3ff.json`      | FG 特征定义 JSON                                  |
