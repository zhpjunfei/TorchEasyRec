______________________________________________________________________

## date: 2026-07-18 tags: [calibration, physics-interpretation, temperature-scaling, ece, multi-task-ranking] status: draft related: \["\[[calibration-calicaustralrank]\]", "\[[pepnet-dcn-ple]\]", "\[[v15-experiments]\]"

# 校准模块的物理意义——每一步给精排带来了什么

> 本文从**物理意义**出发，逐层拆解校准模块中每个设计选择对精排系统产生的实际影响。不谈公式，谈直觉。

______________________________________________________________________

## 一、精排的排序公式与校准的位置

我们的精排最终打分公式是：

```
score = ctr × cvr × bid
```

其中 ctr 和 cvr 来自两个塔的输出，bid 是出价。

**校准发生在哪里？**

```
塔输出: tower_hidden → final_linear → raw_logit
                                          ↓
                                    ┌─────┴─────┐
                                    │           │
                               cvr_add_ctr   bias_sum
                               (CTR塔logit)   (全局偏置)
                                    │           │
                                    └─────┬─────┘
                                          ↓
                                    tower_output (raw_logit)
                                          ↓
                                  ┌─────┴──────┐
                                  │            │
                              Temperature   predictions
                              Scaler         (probs = sigmoid)
                                  │            │
                                  └─────┬──────┘
                                        ↓
                              calibration_loss (ECE)
                                        ↓
                              反向传播 → 更新 shift 参数
```

校准位于**塔输出之后、概率转换之前**。这意味着：

1. **排序公式不变**：score = ctr × cvr × bid 中的 ctr/cvr 来自 sigmoid(probs)，而 probs 来自 calibrated_logit
1. **温度缩放是 sigmoid 的前置操作**：logit / T 改变了 sigmoid 曲线的"陡峭度"
1. **calibration_loss 优化的是概率数值，不是排序位置**

______________________________________________________________________

## 二、TemperatureScaler 的物理意义

### 2.1 温度 T 控制 sigmoid 曲线的"硬度"

sigmoid 函数：

```
p = 1 / (1 + exp(-logit / T))
```

**T=1（标准 sigmoid）：**

```
logit = -3 → p = 0.047   (很低)
logit =  0 → p = 0.500   (居中)
logit = +3 → p = 0.953   (很高)
```

**T=1.5（软化）：**

```
logit = -3 → p = 0.133   (从 0.047 提升到 0.133)
logit =  0 → p = 0.500   (不变)
logit = +3 → p = 0.867   (从 0.953 降到 0.867)
```

**直观理解：**

想象 sigmoid 曲线是一张**弹簧床**：

- T=1 时：弹簧很硬，两边极端值（0 和 1）很"尖"，中间过渡区很窄
- T=1.5 时：弹簧变软了，极端值被"压平"，概率整体向 0.5 靠拢
- T→∞ 时：弹簧完全消失，所有概率都变成 0.5（均匀分布）

### 2.2 为什么 CVR 需要"软化"？

CVR 标签稀疏（50% 转化率），训练时有两个极端情况：

**情况 A：正样本（转化用户）**

模型看到用户点了广告又买了东西，会把这个样本的 logit 推向很大的正值（比如 +5）。sigmoid 输出 0.993——模型"非常确信"这个人会转化。

但问题是：这个用户可能只是恰好今天心情好，或者商品刚好打折。**一次转化不代表这个用户"注定"会转化**。模型把概率推到 0.993，是在**过度自信**。

**情况 B：负样本（点击但未转化）**

模型看到这个用户点了但没买，logit 推向很负（比如 -4）。sigmoid 输出 0.018——模型"非常确信"这个人不会转化。

但用户可能还没看完商品页面，或者正在比价。**一次没转化不代表"不可能"转化**。

**T=1.5 的作用：**

把情况 A 的 0.993 拉到 0.927，把情况 B 的 0.018 拉到 0.072。

概率分布变得更"温和"，不再那么极端。这就像是给模型戴上了一副**防过度自信的眼镜**——它仍然能区分谁会转化、谁不会，但不会把区分度推得太远。

### 2.3 为什么 CTR 不需要"软化"？

CTR 标签密度高（点击率通常 5-15%），样本量大，模型有足够的信号来校准自己的置信度。而且 CTR 是**排名主导任务**——CTR 塔的 logits 直接决定了广告排序，如果也对 CTR 做 T=1.5 软化，会把排序 discrimination 能力削弱。

实验数据印证了这一点：

- 方案 A（全塔校准，T=1.5）：CTR AUC **-1.1%**，CVR AUC +1.8%
- 方案 D（只校 CVR，T=1.5）：CTR AUC **-0.29%**，CVR AUC +1.70%

只校 CVR，CTR 几乎不受影响。

### 2.4 温度缩放的单调性保证

```
f(z) = z / T, T > 0
f'(z) = 1/T > 0  (单调递增)
```

如果样本 A 的 logit > 样本 B 的 logit，那么 logit/T_A > logit/T_B。

**物理含义：** 温度缩放不改变样本间的相对顺序。

线上排序结果不变，这意味着：

- 广告位的展示顺序不变
- 用户体验不变
- 只有概率输出的数值变了

这对于**排序模型**来说是关键的安全保障——我们改的是"信心"，不是"排名"。

______________________________________________________________________

## 三、Soft ECE Loss 的物理意义

### 3.1 ECE 衡量什么？

ECE = Expected Calibration Error = **期望校准误差**

想象一个概率预测器，它对所有样本都输出概率 0.7：

- 如果这 100 个样本中有 70 个真的转化了 → 校准完美（ECE=0）
- 如果只有 30 个真的转化了 → 校准很差（ECE 高）

**ECE 的本质是"预测概率"和"真实频率"之间的偏差。**

### 3.2 为什么用 Soft ECE 而不是硬分桶？

硬分桶（histogram binning）：

```
把样本按概率分成 10 个桶：[0, 0.1), [0.1, 0.2), ..., [0.9, 1.0]
每个桶内算平均预测概率 vs 平均真实标签
```

问题：分桶边界是不可微的。一个样本的概率从 0.099 变到 0.101，就从桶 1 跳到桶 2，梯度断了。

**Soft ECE 的做法：**

用 sigmoid CDF 做"模糊分桶"。一个样本可以同时属于相邻的几个桶，每个桶有一个"隶属度"。

```
sigmoid((p - left_edge) / width) - sigmoid((p - right_edge) / width)
```

这个函数在桶中心附近接近 1，在桶边界处平滑过渡到 0。

**物理含义：** 每个样本对相邻桶都有贡献，梯度可以流畅地通过 sigmoid 的导数传播到温度参数 T。

### 3.3 ECE loss 如何影响训练？

```
total_loss = ctr_bce + ctcvr_bce + calibration_loss
                                    ↓
                            calib_weight × ECE
                                    ↓
                            反向传播 → shift 参数更新
                                    ↓
                            T = initial_temp × exp(shift)
                                    ↓
                            logit / T 变化
                                    ↓
                    sigmoid(logit/T) 变化
                                    ↓
                    ECE 减小（校准改善）
```

calibration_loss 的梯度告诉模型："你的概率太自信了，往 0.5 方向挪一点"或者"你的概率太保守了，往极端方向挪一点"。

**注意：** calibration_loss 优化的是概率数值的合理性，不是排序好坏。它不关心哪个样本排前面，只关心概率值是否反映了真实频率。

______________________________________________________________________

## 四、Progressive Schedule 的物理意义

### 4.1 为什么要渐进式引入校准？

训练初期（step 0-2000）：

- 模型 logits 还在剧烈震荡
- loss 从高位快速下降
- 此时的概率预测没有意义——模型还没学会基本的模式
- 如果此时引入 ECE loss，梯度会和 BCE 梯度冲突

**比喻：** 就像一个刚学走路的孩子，你先让他站稳（学基本模式），再教他走直（校准概率）。如果一开始就要求他每一步都踩准地标线，他只会摔倒。

### 4.2 Progressive Schedule 的时间线

```
step 0-2000 (0-26%):    weight = 0.00  → 校准完全不干预
step 2000-4000 (26-52%): weight 0.00→0.02 → 慢慢引入
step 4000-6000 (52-78%): weight 0.02→0.03 → 加速介入
step >6000 (78-100%):    weight = 0.03  → 稳定运行
```

**物理含义：**

- 前 26% 的训练让模型学会"大概怎么分"
- 中间 52% 的训练让模型学会"分得多准"
- 后 22% 的训练让模型学会"概率数值对不对"

### 4.3 为什么 weight 这么小（0.02-0.05）？

因为 BCE loss 的量级大约是 2.6-3.0，而 ECE loss 的量级大约是 0.08-0.10。

如果 weight=1.0，calibration_loss 会占 total_loss 的 2-3%，这已经是一个不可忽视的优化目标了。但我们希望校准是**辅助性的**——它不应该和 BCE 竞争优化资源。

weight=0.02 意味着 calibration_loss 的实际贡献大约是 0.02 × 0.10 = 0.002，只占总 loss 的 0.07%。这是一个**微调信号**，告诉模型"在学好基本模式之后，顺便把概率数值调准一点"。

______________________________________________________________________

## 五、Per-task Tower 过滤的物理意义

### 5.1 为什么只校 CVR 不校 CTR？

PEPNetDCNPLE 的架构是共享底层的：

```
deep_input → EPNet → PLE ExtractionNet → [CTR tower, CVR tower]
```

CTR 和 CVR 共享 PLE 的共享 expert。校准梯度通过 temperature_scaler 传到 CVR tower，再通过 PLE 共享层传到 CTR tower。

**如果全塔校准（方案 A）：**

```
CTR calibration_loss 梯度 → PLE shared expert → CVR tower
CVR calibration_loss 梯度 → PLE shared expert → CTR tower
```

两个塔互相干扰。CTR 塔的校准梯度会"污染" CVR 塔的特征表示，反之亦然。

**如果只校 CVR（方案 D）：**

```
CVR calibration_loss 梯度 → PLE shared expert → CTR tower（轻微污染）
CTR tower 没有 calibration_loss → 不会被反向污染
```

单向干扰远小于双向干扰。

### 5.2 实验数据印证

| 方案 | tower_filter | CTR AUC 变化 | CVR AUC 变化 |
| ---- | ------------ | ------------ | ------------ |
| A    | 全部         | -1.1%        | +1.8%        |
| D    | cvr          | -0.29%       | +1.70%       |

只校 CVR 时，CTR 的负面影响从 -1.1% 降到 -0.29%，而 CVR 的正向收益几乎不变。

______________________________________________________________________

## 六、与 CTCVR Loss 的协同

当前配置启用了 `use_ctcvr_loss: true`，这是一个**联合损失**：

```
ctcvr_probs = ctr_probs × cvr_probs
ctcvr_label = ctr_label × cvr_label
bce_ctcvr = -[ctcvr_label × log(ctcvr_probs) + (1-ctcvr_label) × log(1-ctcvr_probs)]
```

**校准对 CTCVR 的影响：**

1. 温度软化 CVR logits → CVR probs 更温和 → CTCVR probs = CTR × CVR 也被带动
1. CTCVR loss 本身在优化 CTR×CVR 的联合概率
1. Calibration loss 在优化 CVR 的边际概率

这两个目标**方向一致**：都让 CVR 概率更合理。但 CTCVR loss 优化的是"联合事件的概率"，calibration loss 优化的是"CVR 塔自身的校准"。

**实验数据：**

```
Baseline:     bce_ctcvr = 0.31279
D (修复后):   bce_ctcvr = 0.35477  (+13.4%)
```

BCE_ctcvr 上升说明 CTCVR 联合概率的拟合变差了——这是因为校准在"压制" CVR 概率的极端值，而 CTCVR loss 希望 CVR 概率尽可能准确。

**但这不是问题**，因为：

1. CTCVR loss 的权重是 1.0（默认），calibration loss 权重只有 0.02
1. CTCVR loss 主导联合概率优化，calibration 只是微调
1. AUC 看的是排序能力，BCE 看的是概率准确度——两者不一定一致

______________________________________________________________________

## 七、总结：校准给精排带来了什么

| 组件                      | 物理作用                          | 对精排的影响                     |
| ------------------------- | --------------------------------- | -------------------------------- |
| TemperatureScaler (T=1.5) | 软化 CVR logits，降低模型过度自信 | CVR 概率更温和，AUC +1.7%        |
| Soft ECE Loss             | 可微分校准误差，梯度流向 T 参数   | 训练时自动学习最优软化程度       |
| Progressive Schedule      | 前期不干预，后期逐步引入          | 避免训练初期梯度冲突             |
| Per-task 过滤 (cvr only)  | 只校准 CVR 塔，保护 CTR           | CTR 负面影响从 -1.1% 降到 -0.29% |
| 单调性保证                | logit/T 不改变样本间相对顺序      | 线上排序不变，仅概率数值调整     |

**一句话总结：** 温度校准不改排名，只改信心。它让 CVR 塔在"学会区分谁会转化"之后，进一步学会"区分得有多准"。

______________________________________________________________________

## 相关

- \[[calibration-calicaustralrank]\] — 校准模块完整技术文档

- \[[calibration-calicaustralrank]\] — 校准模块完整技术文档

- \[[pepnet-dcn-ple]\] — 主模型架构

- \[[v15-experiments]\] — 实验记录
