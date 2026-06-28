______________________________________________________________________

## date: 2026-06-28 tags: [experiment, v14, v15, roadmap] status: updated related: \["\[[v14-experiments]\]"\]

# v15 优化路线图（ots 扫完后的新方向）

> ots 全扫（21 点 0.005→0.50）GAUC_cvr 从 0.6957 → 0.7413，所有超参 lever 已穷尽。转向架构升级。

______________________________________________________________________

## 一、已完成（v14，2026-06-28 完结）

### ots 全扫描

| 实验数 |    范围    |      GAUC_cvr 提升      |  状态   |
| :----: | :--------: | :---------------------: | :-----: |
|   21   | 0.005→0.50 | **+4.56pp**（严格单调） | ✅ 完结 |

### 已证否的方向

| 方向                     | 证据                                           | 结论                         |
| :----------------------- | :--------------------------------------------- | :--------------------------- |
| dropout 调参             | ots≥0.12 时 dropout 0.1→0.3 仅 +0.08pp（噪声） | ❌ ots 替代品，高 ots 下冗余 |
| CVR tower 扩宽           | wide −0.18pp, wide+dropout −0.10pp             | ❌ 瓶颈不在 tower MLP        |
| dense weight decay       | adamw 等同基线                                 | ❌ 零效果                    |
| cvr tower wd             | Config D 等同 A                                | ❌ 零效果                    |
| ctcvr/ESMM               | +0.29pp GAUC_cvr, −0.07pp CTR                  | ❌ 中性偏负                  |
| 梯度隔离/手术/自适应加权 | 全部负或中性                                   | ❌                           |

### 基线状态

| 指标     |   ots=0.50（极致）   |   ots=0.12（推荐）   | ots=0.01（v12 baseline） |
| :------- | :------------------: | :------------------: | :----------------------: |
| GAUC_cvr | **0.7413 (+4.56pp)** | **0.7245 (+2.88pp)** |          0.6957          |
| GAUC_ctr |   0.7040 (−0.04pp)   |   0.7043 (−0.01pp)   |          0.7044          |
| BCE_cvr  |   0.384（过置信）    |    0.470（健康）     |          0.494           |
| gap_cvr  |        4.51pp        |        4.75pp        |          5.25pp          |

______________________________________________________________________

## 二、核心认知（28+ 实验的教训）

### 2.1 什么有效、什么无效

| 状态      | 方向                                         |   证据强度   | 机制                                          |
| :-------- | :------------------------------------------- | :----------: | :-------------------------------------------- |
| ✅✅ 最强 | out_task_space_weight 单调增益 0.005→0.50    |  ⭐⭐⭐⭐⭐  | 非点击梯度从 0%→90.5%，CVR 塔获得全量数据训练 |
| ✅ 有效   | PLE extraction network 容量                  | ❓（实验中） | 共享表征质量决定两 tower 上限                 |
| ❌ 已证伪 | CVR tower MLP 宽度                           |    ⭐⭐⭐    | [512,256,128] 已够，1024→无效                 |
| ❌ 已证伪 | dropout 调参（ots≥0.12）                     |     ⭐⭐     | ots 自身提供正则，dropout 冗余                |
| ❌ 已证伪 | weight decay / ctcvr / 梯度干预 / 自适应加权 |    ⭐⭐⭐    | 多重独立证伪                                  |

### 2.2 未探索的杠杆（按确定性排序）

| 杠杆                      | 预期增益  |          成本          |      风险      |
| :------------------------ | :-------: | :--------------------: | :------------: |
| PLE expert 容量（进行中） |   1~2pp   |    低（改 config）     |       低       |
| Contrastive Phase 2       | 0.1~0.3pp |   极低（改 config）    |      极低      |
| 实时特征（短窗口/ratio）  | 0.5~1.5pp | 高（Flink SQL + 数据） |       中       |
| Sequence encoder 升级     | 0.3~0.8pp |  中（改 proto+model）  | 中（OOM 风险） |
| Embedding 维度/容量       |   未知    |    低（改 config）     |       中       |
| PLE expert count vs width |   未知    |    低（改 config）     |       低       |

______________________________________________________________________

## 三、v15 实验路线图

### Phase 2（当前 — 架构容量）

| 序号 | 实验                       | 内容                                     | 目的                            | 优先级 |
| :--: | :------------------------- | :--------------------------------------- | :------------------------------ | :----: |
|  1   | **ots012_plebig** 🏃       | PLE expert 3×3×[1024,512]/[512,256]      | 共享表征容量翻 4x               | **P0** |
|  2   | *ots012_plebig_wide_tower* | 如 plebig 有效，恢复 tower 宽度          | PLE 容量 + tower 宽度叠加       |   P1   |
|  3   | *ots012_plec*              | 只加 expert count（2→3），不加 width     | 分离 expert count vs width 效果 |   P2   |
|  4   | *ots012_plew*              | 只加 expert width，不加 count            | 同上                            |   P2   |
|  5   | **contrastive_phase2**     | alignment_mode: "column"→"bidirectional" | 对比学习第二阶段                |   P1   |

如果 Phase 2 有效（GAUC_cvr > +1pp），主攻架构方向；否则转特征方向。

### Phase 3（特征工程）

| 序号 | 实验                     | 内容                                     | 目的                           | 优先级 |
| :--: | :----------------------- | :--------------------------------------- | :----------------------------- | :----: |
|  6   | **实时短窗口特征**       | item\_\_cnt_click_rt5m/15m/30m           | 捕捉更精细的实时热度           |   P0   |
|  7   | **实时 ratio 特征**      | click_rate_rt, conversion_rate_rt        | 真实热度度量（而非 raw count） |   P0   |
|  8   | **用户侧实时统计**       | user\_\_cnt_click_rt1h 等                | 用户当下活跃度/兴趣            |   P1   |
|  9   | **实时 × 属性 cross**    | rt_hot × login_city / gender / dev_brand | 实时热门 × 用户画像            |   P2   |
|  10  | **Sequence Transformer** | click_50_seq: DIN→TransformerEncoder     | 捕捉 item 间交互               |   P1   |
|  11  | **KV 实时特征增强**      | 新增更多 attribute 的 rt KV 特征         | 用户实时兴趣分布               |   P2   |

### Phase 4（部署与最终调优）

| 序号 | 实验                 | 内容                                     | 目的                      | 优先级 |
| :--: | :------------------- | :--------------------------------------- | :------------------------ | :----: |
|  12  | 最优 config 重复验证 | ots=0.12/0.15 + Phase 2/3 增益           | 确认可复现                |   P0   |
|  13  | 在线融合 β 调优      | fusion_score = CTR × CVR^β               | 线上 CTR vs CVR trade-off |   P0   |
|  14  | gap_cvr 监控         | 离线 GAUC vs 在线 UV GAUC 差距           | 验证离线评估有效性        |   P0   |
|  15  | BCE_cvr 校准         | 如 \<0.420 需校准（temperature scaling） | 防止过置信                |   P1   |

______________________________________________________________________

## 四、决策树

```
ots sweep completed (+4.56pp max)
│
├── PLE capacity (ots012_plebig)
│   │
│   ├── ✅ >+1pp → 主攻架构
│   │   │
│   │   ├── decompose: expert count vs width
│   │   ├── then: tower width re-test
│   │   └── then: contrastive Phase 2
│   │
│   └── ❌ <+0.5pp → 放弃架构，转特征
│       │
│       ├── real-time features (short window / ratio)
│       ├── sequence encoder upgrade
│       └── contrastive Phase 2 (low-cost Hail Mary)
│
└── deploy ots=0.12 or 0.15
    └── online fusion β tuning
```

______________________________________________________________________

## 五、实验提交顺序（当前）

```
Round 1 (当前): ots012_plebig 🏃
Round 2:        contrastive_phase2 (低投入高周转)
Round 3:        根据 plebig 结果决定架构或特征方向
```
