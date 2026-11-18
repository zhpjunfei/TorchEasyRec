# trend_click → trend_cvr 塔替换方案

**日期**: 2026-10-22
**状态**: ✅ 已执行（2026-10-22）——按用户指示以**新增配置**方式落地：`home_flow_2608_v19_multiscene_v3_trend_cvr.config`（基于 v2_fix_label_leak，diff 仅方案内 3 处变更 + 2 行头注释）。v2 系配置保持原样未动（保 A/B 记录可比性）；4 个 phase 配置的同步替换仍待决策。
**动机**: trend 场景为查价弹窗，点击率 ~100%（真实业务形态），`is_trend_click` 作监督信号信息量≈0（常数任务、梯度消失）；trend 数据中唯一有信息量的标签是**转化（28.8% 正，每步 ~65 正/160 负）**。本方案将 trend 任务槽位的监督信号换为转化，使 trend 5.5% 的数据行从"零梯度"变为有效监督，并通过共享主干把"查价→转化"表征迁移到 home CTCVR。
**设计原则**: **唯一变量 = 监督 label**。权重、掩码、塔结构、样本全部不动。

______________________________________________________________________

## 一、变更清单（共 3 处）

### 变更 1：trend 塔块（核心，v2 配置第 13084 行起）

```diff
     task_towers {
-      tower_name: "trend_click"
-      label_name: "is_trend_click"
+      tower_name: "trend_cvr"
+      label_name: "is_trend_conversion"
       weight: 0.5
       train_metrics {
         auc {}
       }
       train_metrics {
         grouped_auc { grouping_key: "is_trend_scene" }
       }
       losses {
         binary_cross_entropy {}
       }
       mlp {
         hidden_units: [512, 256, 128]
         use_ln: true
         dropout_ratio: 0.1
       }
       task_space_indicator_label: "is_trend_scene"
       in_task_space_weight: 1
       out_task_space_weight: 0
     }
```

只动两行：`tower_name` 与 `label_name`。改名是必要的——否则指标会叫 `auc_trend_click` 实际学转化，误导读日志的人。

### 变更 2：`data_config.label_fields`（必须，否则取数/loss 阶段 KeyError）

```diff
   label_fields: "is_bijia_click"
   label_fields: "is_haojia_click"
   label_fields: "is_trend_click"
+  label_fields: "is_trend_conversion"
```

注意两点：

- **`is_trend_conversion` 必须加**——`dataset.py` 按 `label_fields` 决定读哪些列，tower 的 `label_name` 找不到列会直接失败（同 P0-5 机制）；v5 表已有该列（SQL-5 实测可用），无需改数据管道；
- **`is_trend_click` 建议保留**——已无塔消费它，但保留可让 `LABEL_DIST` 继续输出它，用作分布自检（应 ≈ `is_trend_scene`，即 ~5.5%）。

### 变更 3：无需改动项（明确列出防误动）

| 项                           | 值                                | 说明                                            |
| ---------------------------- | --------------------------------- | ----------------------------------------------- |
| `weight`                     | 0.5                               | 与 trend_click 同槽位同强度，避免混入第二个变量 |
| `task_space_indicator_label` | `"is_trend_scene"`                | 掩码不变                                        |
| `in/out_task_space_weight`   | 1 / 0                             | 不变                                            |
| `mlp`                        | [512,256,128]                     | 不变（A-1 已统一）                              |
| `train_metrics`              | auc + grouped_auc(is_trend_scene) | 结构不变，仅随塔名换前缀                        |
| 样本/数据管道                | —                                 | 不变（is_trend_conversion 列已存在于 v5 表）    |

## 二、影响面

1. **参数量/显存/速度**：不变（塔结构逐字节一致，仅 label 源不同）；
1. **日志字段名**：`binary_cross_entropy_trend_click` → `binary_cross_entropy_trend_cvr`，`auc_trend_click`/`grouped_auc_trend_click` → `*_trend_cvr`——**监控看板/告警里引用旧名的配置需同步**；
1. `grad_cos_sim_*` 键名随 tower_name 变化（含 `trend_cvr` 的对）；
1. `LABEL_DIST` 新增 `is_trend_conversion` 输出；
1. serving：若未来需要 trend 转化预估（弹窗后成交概率），该塔可直接作为服务头；trend 点击分不再产出（点击率恒 ~1，无预估价值）。

## 三、预期读数与验收

| 读数                                       | 预期                               | 依据                                                        |
| ------------------------------------------ | ---------------------------------- | ----------------------------------------------------------- |
| `binary_cross_entropy_trend_cvr` 初始      | ≈ **0.60**                         | 28.8% 先验的熵 H(0.288)=0.601，常数预测即此值；随后应低于它 |
| `grouped_auc_trend_cvr`                    | **> 0.6** 且显著可分               | 65 正/160 负每步，任务健康                                  |
| `LABEL_DIST` 中 `is_trend_conversion`      | ≈ 65/4096 ≈ **1.6%**               | 5.5% × 28.8%                                                |
| `LABEL_DIST` 中 `is_trend_click`           | ≈ `is_trend_scene` ≈ 5.5%          | 分布自检                                                    |
| home `grouped_auc_ctr` / `grouped_auc_cvr` | 观察迁移收益（趋势性，不承诺幅度） | trend 行仅占 5.5%，收益以特征通道为主                       |

**判失败**：`grouped_auc_trend_cvr` ≈ 0.5（没学到东西）→ 检查 label 列是否读到；loss 初始值远偏离 0.60 → 检查 label 分布是否与验收 SQL 一致。

## 四、执行范围

| 配置                                                        | 动作             | 理由                                                                       |
| ----------------------------------------------------------- | ---------------- | -------------------------------------------------------------------------- |
| `home_flow_2608_v19_multiscene_v2_fix_label_leak.config`    | **必改**         | 活跃训练配置                                                               |
| `home_flow_2608_v19_multiscene_v2_no_mask_control.config`   | **必改（同批）** | 保持与主配置只差 ctr 掩码一个变量，未来 A/B 重跑不失效                     |
| `home_flow_2608_v19_phase1_{chajia,p0,p0_v2,search}.config` | 建议同步         | 4 个 phase 均含 trend_click，不同步则 Phase 对比混入"label 不同"的混淆变量 |
| `phase1_bijia_only` / `phase2_bijia_haojia`                 | 免改             | 无 trend 塔                                                                |

## 五、执行顺序与回滚

1. **等数据链路完成**（fix_sample → 60d 汇总，用修复后 label 表）；
1. 落配置变更（3 处）；
1. **T_max 同批重算**：新数据实测 `Training Epoch 0: Nit` 后 `T_max = N − 1000`（预计 ≈ 6,150~6,200，见 `config_vs_distribution_review.md` §三）；
1. 起训练，按 §三 验收。

**回滚**：反向应用 diff 即可（2 行塔改名 + 删 1 行 label_fields），无数据依赖。

______________________________________________________________________

**决策点（可选）**：trend_cvr 权重是否从 0.5 提到 1.0（增强意图表征迁移强度）。建议首轮保持 0.5（一次一个变量），若 home 迁移收益不明显再单独调权重做 A/B。
