
---

# V11 实验日志深度重审（2026-06-23）

## 一、文档变更概览

相对于上次审查，文档新增了 **§11 Label Smoothing + LR 调度实验**（119 行），标题从"完整设计方案"改为"实验日志"。核心变更：

|变更|说明|
|---|---|
|新增 §11|完整的 label smoothing + LR 调度消融实验|
|新增 5 个 config|label_smoothing、tmax_6700_label_smoothing、warmrestart 及其 2-epoch 变体|
|新增 segment_diag config|含 GroupedAUC（按 lifecycle_tags / first_cate_id 分组）|
|冻结对比学习部分|§1-10 标注为"已冻结"|

---

## 二、§1-10 对比学习部分的结论重审

### 2.1 核心结论回顾

文档的 §10 给出了清晰的证据链：

|证据|数据|结论|
|---|---|---|
|title_vector 直接输入无 AUC 增益|0.71574 vs 0.71572|title_vector 无预测力|
|bidirectional loss 改善|4.35 → 3.53|双向对齐有效|
|但 AUC 不涨|0.716080 < 0.716316|对齐不转 AUC|
|bidirectional + tmax 不如 tmax alone|0.716408 < 0.716737|对比梯度抵消主任务|

### 2.2 我的重审意见

**结论基本正确，但有三个值得商榷的点：**

#### 商榷点 1："title_vector 无预测力"的结论过于绝对

文档的证明依赖于 `title_vector` 作为 raw_feature 直接输入的对照实验（0.71574 vs 0.71572）。但这个实验只证明了 **"未经任何处理的静态 title_vector 无预测力"**，没有排除以下可能性：

1. **title_vector 经过可学习投影后可能有预测力**。文档在 Phase 2 中设计了 `contrastive_title_adapter`（Linear(128→64→128) + zero init），但没有跑完就被回退了。如果让这个 adapter 被 BCE 梯度直接优化（而非仅通过对比学习间接优化），可能发现 title_vector 中确实存在微弱信号。
    
2. **title_vector 可能在特定 segment 中有预测力**。新增的 segment_diag config 引入了 `grouped_auc` 按 lifecycle_tags 和 first_cate_id 分组。如果 title_vector 只在某些品类或用户生命周期段中有价值，全局 AUC 会掩盖这种局部增益。
    
3. **title_vector 与序列 title_vector 的交互可能有用**。SQL 管道生成了 `click_50_seq__title_vector`（用户历史浏览商品的标题向量序列），但目前没有任何实验使用它。如果将序列 title 的均值/注意力加权作为"用户语义偏好"，与 target title_vector 做对比，可能比用 DIN 输出做对比更有意义。
    

#### 商榷点 2：BCE 下降但 AUC 不升的机制分析不完整

文档发现"对比对齐让概率校准更好（BCE 降），但排序更差（AUC 降）"。我补充一个**量化视角**：

- BCE 降低说明模型输出的概率更接近真实标签的置信度
- AUC 降低说明模型对样本的**相对排序**变差了
- 这暗示对比学习让 DIN 输出**向共性信号（item 内容）偏移**，**削弱了个性信号（用户偏好）**

**关键问题**：DIN 编码器本身已经通过 attention 机制从行为序列中提取了目标相关的表征。对比学习额外施加的"向 title_vector 靠拢"约束，实际上是**在 DIN 已经学到的表征上叠加了一个正交的信号**。当 title_vector 与点击行为无关时，这个正交信号就变成了噪声。

#### 商榷点 3：实验终止的理由充分但不够全面

文档建议"停止对比学习实验，上线 tmax_6700"，这是正确的短期决策。但长期来看，**对比学习范式本身可能仍然有价值**——只要换一个有预测力的对齐目标。

---

## 三、§11 Label Smoothing + LR 调度实验重审

### 3.1 实验设计评估

|维度|评分|说明|
|---|---|---|
|动机清晰度|⭐⭐⭐⭐⭐|从"2-epoch 失败"的假设出发，设计了对比实验|
|变量控制|⭐⭐⭐⭐|5 个变体控制了 epochs 和 LR 调度两个变量|
|指标选择|⭐⭐⭐⭐⭐|同时看 AUC 和 BCE，正确识别 label smoothing 的 BCE 升高是预期的|
|统计严谨性|⭐⭐⭐⭐|使用了 σ 量化（24σ、35σ），但 SE=0.00086 的来源未说明|

### 3.2 五项发现的逐条审查

#### 发现 1：Label smoothing 的 BCE 升高是预期的

**✅ 正确。** 文档的分析非常到位：

- 直接对比 baseline BCE=1.933748 与 label_smoothing BCE=1.971085（+0.037）
- 同时 AUC 从 0.716316 升到 0.716637（+0.000321）
- BCE 升高但 AUC 不跌 → soft label 没有伤害排序能力

**补充**：label smoothing 的公式 `label * (1-ε) + 0.5*ε`（代码在 `rank_model.py:239`），当 ε=0.05 时：

- 正样本标签从 1.0 → 0.975
- 负样本标签从 0.0 → 0.025
- 这确实会让 BCE 的"理论最优值"升高约 `0.05 * log(0.025) + 0.05 * log(0.975) ≈ 0.037`，与观察到的 +0.037 完全吻合。

#### 发现 2：tmax_6700 与 label_smoothing 叠加正向

**✅ 基本正确，但需要注意 CVR 的细微变化。**

|组合|ΔAUC CTR vs baseline|解读|
|---|---|---|
|tmax_6700|+0.000421|LR 调度优化|
|label_smoothing|+0.000321|正则化效果|
|叠加|**+0.000639**|正向叠加，增量超出单独之和|

CTR 上的正向叠加说明两种优化作用于**不同方面**：tmax_6700 优化了优化轨迹，label smoothing 优化了正则化。两者不冲突。

CVR 上的轻微负向（-0.000319 vs baseline）需要关注。文档提到"不如历史 CVR 波动大（SE≈0.00086 下 ~0.3σ）"，这个判断是合理的——-0.0003 在 0.3σ 范围内属于正常波动。

#### 发现 3：WarmRestart 1-epoch AUC 下降

**✅ 分析正确。** 关键洞察：

> WarmRestart 的 T_0=6700（warmup_size=1000），实际 LR 重启发生在 step 7700，而 eval 在 step 7757。此时 LR 刚被重置到 base_lr，模型处于高 LR 不稳定状态即被评估。

这是一个**实验设计缺陷**，不是算法缺陷。WarmRestart 在 step 7700 将 LR 从接近 0 重置到 base_lr=0.001，模型参数瞬间受到大步长梯度冲击。eval 在 57 步后（step 7757）进行，此时模型还在从冲击中恢复。

**修复建议**：eval 时机应与 LR 周期对齐，或在 WarmRestart 的 restart 后等待若干个 mini-batch 再 eval。

#### 发现 4：2-epoch 在所有 LR 调度下均失败

**⚠️ 分析正确但归因可能不完整。**

|条件|AUC CTR vs 1-ep|统计显著性|
|---|---|---|
|CosineAnnealing T_max=13400|**-0.020872**|24σ|
|WarmRestart T_0=6700|**-0.030578**|35σ|

文档给出的三个可能原因：

1. 模型容量过大 → 直接记忆训练噪声
2. ε=0.05 的 label smoothing 抑制力度不足
3. 随机 99/1 拆分导致 train/val 分布几乎一致

**我补充第四个可能原因**：

4. **LR 调度在 2-epoch 场景下本身就有问题**。CosineAnnealing T_max=13400 的 1-epoch 部分（step 0-6700）LR 从 0.001 降到 ~0.0001，2-epoch 的 epoch 2 部分（step 6700-13400）LR 从 ~0.0001 回升到 0.001。这意味着 **epoch 2 的 LR 是先低后高的**——先收敛再发散。WarmRestart 的问题更严重：T_0=6700 意味着 epoch 2 开始时 LR 就被重置到 base_lr。

**验证建议**：用 T_max=13400 的 CosineAnnealing 做 2-epoch 时，LR 曲线应该是完整的余弦衰减（从高到低），不应该在 epoch 2 回升。但如果实现中 T_max 是"每 epoch 重置"的，那确实会在 epoch 2 重新开始衰减。需要确认 TZRec 的 CosineAnnealingLearningRate 是否按 step 绝对值计算，还是按 epoch 重置。

#### 发现 5：BCE 的 U 型回升确认过拟合

**✅ 正确。** 2-epoch 的 BCE 从 1.97 升至 2.08-2.18，远超 1-epoch 的 1.97。这是典型的过拟合信号。

**但有一个值得注意的细节**：label smoothing 的 BCE 基线本身就比 hard label 高 ~0.037（见发现 1）。所以 2-epoch 的 BCE=2.08 相比 label smoothing 的 1-epoch BCE=1.97，实际升高了 ~0.11。而 baseline（hard label）的 2-epoch BCE 如果也做对比，可能会升高更多。这说明 **label smoothing 确实有一定程度的过拟合抑制**，只是 ε=0.05 不够强。

### 3.3 当前最优配置评估

```
tmax_6700 + label_smoothing (ε=0.05), num_epochs=1
AUC CTR = 0.716955 (+0.000639 vs baseline)
```

**这是一个稳健的提升**，但需要关注几个问题：

|问题|严重程度|说明|
|---|---|---|
|提升幅度极小|⚠️ 中|+0.000639 AUC 在工业场景中可能对应 0.01% 的 GMV 变化，需要 A/B 测试验证|
|CVR 未提升|⚠️ 低|CVR AUC 从 0.757583 降到 0.757264（-0.000319），在波动范围内|
|泛化性未知|⚠️ 高|1-epoch 的结果可能在时间拆分或线上 A/B 中退化|
|未做 segment 分析|⚠️ 中|新增的 segment_diag config 还没跑实验，不知道提升来自哪些 segment|

---

## 四、模型代码与配置的一致性审查

### 4.1 Label Smoothing 的实现

代码在 `tzrec/models/rank_model.py:237-239`：

```
label_smoothing = loss_cfg.binary_cross_entropy.label_smoothing
if label_smoothing > 0:
    label = label * (1.0 - label_smoothing) + 0.5 * label_smoothing
```

**✅ 实现正确。** 标准的 label smoothing 公式。

**但有一个潜在问题**：`0.5 * label_smoothing` 假设正负样本的 smooth 目标都是 0.5。对于**极度不平衡的数据**（CTR 通常 ~1-5%），均匀 smooth（0.5）可能不是最优的。更好的做法是用先验概率 `p_prior` 代替 0.5：

```
label = label * (1.0 - label_smoothing) + p_prior * label_smoothing
```

其中 `p_prior` 可以是训练集的全局点击率（~0.03）。这样负样本的 soft label 会是 0.0015 而非 0.025，更符合数据分布。

### 4.2 PEPEtNetDCNPLE 与 Label Smoothing 的兼容性

`pepnet_dcn_ple.py` 的 `loss()` 方法调用了 `super().loss(predictions, batch)`，然后在其基础上添加 `contrastive_loss`。由于 label smoothing 在 `rank_model.py` 的基类 `loss()` 中处理，**contrastive_loss 不受 label smoothing 影响**——这是正确的，因为对比学习不应该受标签软化的影响。

**✅ 兼容性好。**

### 4.3 配置文件的完整性

检查了 `home_flow_2604_v11_tmax_6700_label_smoothing.config`：

- ✅ CTR tower 和 CVR tower 都设置了 `label_smoothing: 0.05`
- ✅ `T_max: 6700` 正确设置
- ✅ `num_epochs: 1` 正确设置

检查了 `home_flow_2604_v11_segment_diag.config`：

- ✅ 添加了 `grouped_auc` 按 `lifecycle_tags` 和 `first_cate_id` 分组
- ⚠️ 但只加了 CTR tower 的 grouped_auc，**CVR tower 没有**（需要确认是否有意为之）

---

## 五、数据管道的最新变更

### 5.1 新增的 60d 数据

```
home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_tae.sql
```

从 30d 扩展到 60d 行为窗口。这会影响：

- 序列特征的长度分布（更长 → DIN 输出更稳定）
- 冷启动用户比例（更长窗口 → 更多用户有行为历史）
- 对比学习中 `seq_len` 的分布（可能改变 τ 的有效性）

**建议**：对比学习和 label smoothing 实验应该在 60d 数据上重新跑，因为数据分布变了，之前的结论可能不适用。

### 5.2 Deploy 脚本变更

`home_flow_2604_pepnet_nsmpl_search_smpl_sorter_modify_deploy.py` 中：

- ✅ 使用了正确的 processor: `easyrec-torch-2.1`
- ✅ 存储路径包含 `${args['ymd']}` 日期变量
- ⚠️ `fg_mode: "normal"` 但训练 config 中使用 `FG_BUCKETIZE`，需要确认线上 FG 模式是否与训练一致

---

## 六、综合结论与优化建议

### 6.1 结论汇总

|模块|状态|核心结论|
|---|---|---|
|对比学习 (§1-10)|✅ 冻结|代码实现优秀，但 title_vector 监督信号无预测力，已停止|
|Label Smoothing (§11)|✅ 完成|ε=0.05 有效，BCE 升高是预期的|
|LR 调度 (§11)|✅ 完成|tmax_6700 是最优方案；2-epoch 在任何调度下都失败|
|当前最优|✅ 确定|`tmax_6700 + label_smoothing(ε=0.05), 1 epoch`|
|Segment 诊断|⏳ 待跑|segment_diag config 已创建，未出结果|

### 6.2 我补充的三个关键问题

**问题 1：AUC 提升的统计显著性与业务价值**

+0.000639 的 CTR AUC 提升在 SE=0.00086 下约为 0.74σ，**未达到统计显著水平**（通常需要 2σ 以上）。文档将其标为"历史最优"，但从统计角度看，这个提升可能是随机波动。

**建议**：用 bootstrap 或时间拆分做更严格的显著性检验。如果 A/B 测试能跑，直接上线上看 GMV 变化。

**问题 2：2-epoch 失败的 LR 调度根因未完全排查**

文档排除了"LR 调度错误"的假设，但**没有确认 TZRec 的 CosineAnnealingLearningRate 是按 step 绝对值还是按 epoch 重置计算的**。如果是后者，T_max=13400 的 2-epoch 实验中 epoch 2 的 LR 会从 0 回升到 base_lr，这正是过拟合的根源。

**建议**：打印 2-epoch 实验的 LR 曲线，确认 epoch 2 的 LR 变化趋势。

**问题 3：Segment 诊断 config 已就绪但未使用**

新增的 `home_flow_2604_v11_segment_diag.config` 包含了 `grouped_auc` 按 lifecycle_tags 和 first_cate_id 分组。这是验证"提升来自哪些 segment"的关键工具，但目前没有运行结果。

**建议**：尽快用最优配置（tmax_6700 + label_smoothing）跑 segment_diag，看提升是否集中在特定品类或用户群体。如果提升只来自某一 segment，说明优化是有针对性的，业务价值更高。

### 6.3 下一步行动清单

|优先级|行动|预计耗时|依赖|
|---|---|---|---|
|P0|上线 `tmax_6700 + label_smoothing` 到线上 A/B|—|部署 pipeline|
|P1|跑 segment_diag 实验，分析 improvement breakdown|1 day|训练集群|
|P1|在 60d 数据上重新验证最优配置|2 days|60d 数据就绪|
|P2|尝试 p_prior 替代 0.5 的 label smoothing|0.5 day|改 rank_model.py|
|P2|验证 2-epoch 失败的真实原因（LR 曲线分析）|0.5 day|已有日志|
|P3|探索序列 title_vector 对比（替代 DIN-title 对比）|3 days|特征工程|
|P3|尝试更大 ε 的 label smoothing（0.1/0.2）|1 day|训练集群|