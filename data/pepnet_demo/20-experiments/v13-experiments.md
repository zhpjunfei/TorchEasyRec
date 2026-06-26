______________________________________________________________________

## date: 2026-06-24 tags: [experiment, v13, review] status: completed related: ["[[v12-experiments]]", "[[v14-experiments]]"]

# 优化方向深度审核

## 一、我们所知的全部事实

### 18 个实验建立的知识

```
loss 加权 → 全部失败（ctr45 除外）
梯度手术 → 无效
辅助 loss → 无效
梯度隔离 → 严重负向（证明 CVR 信号有价值）
Deep CVR tower → 严重过拟合
Embedding dropout → 贡献 0.32% CVR（最意外的强信号）
```

### 审核中发现的关键漏洞

CVR tower 的 `dropout_ratio` 被 `LHUC_PPNet` 静默忽略。`use_ln` 同样被忽略。

**当前 CVR tower 实际结构：**

- `LHUC_PPNet(512→512→256→128)` — 3 层 Linear，中间无任何 dropout / BN / LN
- 接 `Linear(128→1)`
- 是**一个完全没有正则化的 3 层 MLP，运行在 5% 的训练数据上**

这意味着我们过去 18 个实验全部基于一个有**隐含设计缺陷**的 CVR tower。

### 正确设置 CVR tower 的要素

| 要素         | 当前状态                                      | 应该有的状态                |
| :----------- | :-------------------------------------------- | --------------------------- |
| 容量         | [512,256,128]（512→512 是同维映射，浪费参数） | [256,128]（匹配 5% 数据）   |
| Dropout      | **无**（`dropout_ratio` 被忽略）              | 有（0.3~0.5）               |
| Weight Decay | 0.01（与共享层相同）                          | 0.03~0.05（CVR 专属更高值） |
| Layer Norm   | **无**（`use_ln` 被忽略）                     | 可加（若修改 LHUC_PPNet）   |

______________________________________________________________________

## 二、各方向批判性评估

### 方向 A：缩小 CVR tower 为 [256,128]

**原理**：移除 512→512 的同维映射层，减少参数 ~80%（163K→33K）。

**优点**：唯一不修代码的容量缩减手段。

**局限**：

- 没有 dropout，缩小容量只能减少"过拟合空间"，不能主动正则化
- 效果上限有限

**概率估计**：~20% 产生 >0.05% CVR 提升

### 方向 B：CVR tower dropout（已取消）

**原因**：改一个无法生效的配置无意义。已确认 `dropout_ratio` 被 `LHUC_PPNet` 丢弃。

### 方向 C：out_task_space_weight=0.01

**原理**：非点击样本 `is_conversion=0`，以 1% 权重加入 CVR 训练 → 100% 样本覆盖。

**风险（样本选择偏差）**：

- 非点击群体与点击群体的特征分布系统性不同
- CVR 塔可能学到"像非点击→低 CVR"的代理模式，而非真正的转化信号
- `cvr_add_ctr_logits=true` 部分缓解（CTR logits 已编码点击信息），但未消除

**概率估计**：\<10% 产生正向效果。零成本可试，但不值得期待。

### 方向 D：给 LHUC_PPNet 加真正 dropout（修复模块）

**原理**：修改 `LHUC_PPNet.__init__` 接受 `dropout_ratio`，在每层 Linear 后加 `nn.Dropout`。

**为什么可能是这 18 个实验后最大收益源**：

- CVR tower **从未**有过 dropout
- 唯一一次与 dropout 相关的实验是 embedding dropout（optimized config，−0.32% CVR）— 那是 embedding 层，不是 tower 层
- dropout 是防止小数据过拟合最成熟的手段

**工作量**：低。修改 1 个文件（`lhuc_net.py`）+ rebuild wheel。

**风险**：接近零。dropout 是标准操作，test 时自动关闭。

**概率估计**：~30% 产生 >0.05% CVR 提升。这是所有方向中最高的。

### 方向 E：part_optimizer 给 CVR tower 更高 weight decay

**原理**：regex 匹配 CVR tower 权重，用 AdamW wd=0.03（3× 默认），不修代码。

**与方向 D 的关系**：互补。dropout 和 weight decay 解决不同问题：

- Dropout：防止神经元 co-adaptation
- Weight decay：防止单一权重过大

**合理 wd 值**：0.03（建议起点）→ 0.05（激进）。理由：

- CVR tower 无 dropout → wd 是替代正则化
- 默认 0.01 是针对 100% 数据设计的，CVR 仅 5% → 5× 不算过分
- bias 不加 wd（已有做法）

**概率估计**：~15% 产生 >0.05% CVR 提升（单独使用）。与 dropout 叠加时更高。

______________________________________________________________________

## 三、各方向效果的真实预期

```
效果大小（Δauc_cvr）
    │
0.3% │ optimized 实验（缺 embedding dropout）
    │   ← 这是唯一真实数据点：缺失正则化 = −0.32%
    │
0.1% │ 方向 D（修复 dropout）— 最好预期
    │  ← 可能接近 but < 0.32%（embed dropout 覆盖 168 层，tower dropout 只覆盖 1 层）
    │
0.05%│ 方向 A（缩小容量）+ 方向 E（weight decay）
    │  方向 C（out_task_space）— 最不确定
    │
  0  └────────────────→ ctr45 baseline
```

**关键认识**：即使方向 D 成功，CVR 提升幅度也不太可能超过 embedding dropout 的 0.32%——因为 tower dropout 只影响 1 个 MLP（CVR tower），而 embedding dropout 影响 168 个 embedding 层。

______________________________________________________________________

## 四、行动建议

### 立即执行（无代码变更）

| 步骤               | 具体                                  | 预期                   |
| :----------------- | :------------------------------------ | :--------------------- |
| 1. Config A        | CVR tower [256,128]                   | 缩小容量，低配版正则化 |
| 2. Config E        | part_optimizer wd=0.03 on CVR weights | 替代正则化             |
| 3. Config A+E 叠加 | 缩小 + wd                             | 两步互补               |
| 4. Config C        | out_task_space_weight=0.01            | 零成本博彩             |

### 代码变更

| 步骤                   | 具体                              | 工作量             |
| :--------------------- | :-------------------------------- | :----------------- |
| 5. 修复 LHUC_PPNet     | 加 `dropout_ratio` + `nn.Dropout` | 1 文件，~5 行      |
| 6. rebuild wheel       | `python3 -m build --wheel`        | 1 分钟             |
| 7. 跑 A + dropout 叠加 | [256,128] + dropout 0.3 + wd 0.03 | 最完整的正则化实验 |

### 最终判断

方向 C 已不值得单独跑。把精力集中在：

**A[256,128] + E[wd=0.03] + D[dropout=0.3]** 的组合。

这是我们在这 18 个穷举实验之后，唯一有认真理论基础（CVR tower 从未被正确正则化过）的优化方向。
