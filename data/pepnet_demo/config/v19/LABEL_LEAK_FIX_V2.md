# 标签泄漏问题修复 - 验证报告

**日期**: 2026-10-20
**验证分区**: dt='20261013'
**验证状态**: ✅ 全部通过

______________________________________________________________________

## 一、验证结果汇总

| SQL  | 验证内容                | 结果                                                                              | 状态 |
| ---- | ----------------------- | --------------------------------------------------------------------------------- | ---- |
| SQL1 | 各场景点击分布          | home 80.2M(36.53%), bijia 19.6M(34.97%), trend 11.5M(50.68%), haojia 8.9M(13.23%) | ✅   |
| SQL2 | 各场景正样本率          | 同上，独立验证                                                                    | ✅   |
| SQL3 | 点击标签语义            | 无跨场景污染（所有列=0）                                                          | ✅   |
| SQL4 | is_home_scene_click字段 | 字段不存在（报错）                                                                | ✅   |
| SQL5 | 各场景CVR分布           | home 11.93%, bijia 13.58%, trend 17.23%, haojia 5.24%                             | ✅   |
| SQL6 | CVR标签语义             | 无跨场景污染（所有列=0）                                                          | ✅   |

______________________________________________________________________

## 二、详细验证结果

### 2.1 SQL1: 各场景点击分布

```sql
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
        ELSE 'UNKNOWN'
    END AS scene,
    COUNT(1) AS pv,
    SUM(CASE WHEN is_home_scene = 1 THEN is_click ELSE 0 END) AS home_clicks,
    SUM(CASE WHEN is_bijia_scene = 1 THEN is_bijia_click ELSE 0 END) AS bijia_clicks,
    SUM(CASE WHEN is_haojia_scene = 1 THEN is_haojia_click ELSE 0 END) AS haojia_clicks,
    SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_click ELSE 0 END) AS trend_clicks,
    ...
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013'
GROUP BY scene;
```

**结果**:

| scene  | pv         | home_clicks | bijia_clicks | haojia_clicks | trend_clicks | home_ctr | bijia_ctr | haojia_ctr | trend_ctr |
| ------ | ---------- | ----------- | ------------ | ------------- | ------------ | -------- | --------- | ---------- | --------- |
| home   | 80,215,798 | 29,306,395  | 0            | 0             | 0            | 36.53    | N/A       | N/A        | N/A       |
| bijia  | 19,558,474 | 0           | 6,840,322    | 0             | 0            | N/A      | 34.97     | N/A        | N/A       |
| trend  | 11,450,974 | 0           | 0            | 0             | 5,802,893    | N/A      | N/A       | N/A        | 50.68     |
| haojia | 8,886,338  | 0           | 0            | 1,175,448     | 0            | N/A      | N/A       | 13.23      | N/A       |

**关键发现**:

1. home CTR = 36.53%，证实之前文档中"37%"是正确的，"67%"是错误的估计
1. trend CTR最高(50.68%)，符合"查价高意向"特征
1. 各场景点击标签正确分离，无交叉污染

______________________________________________________________________

### 2.2 SQL3: 点击标签语义验证

```sql
SELECT
    'click_label_check' AS check_item,
    SUM(CASE WHEN is_home_scene = 1 AND (is_bijia_click = 1 OR is_haojia_click = 1 OR is_trend_click = 1) THEN 1 ELSE 0 END) AS home_with_other_clicks,
    SUM(CASE WHEN is_bijia_scene = 1 AND is_click = 1 THEN 1 ELSE 0 END) AS bijia_with_home_click,
    SUM(CASE WHEN is_haojia_scene = 1 AND is_click = 1 THEN 1 ELSE 0 END) AS haojia_with_home_click,
    SUM(CASE WHEN is_trend_scene = 1 AND is_click = 1 THEN 1 ELSE 0 END) AS trend_with_home_click
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013';
```

**结果**:

| check_item        | home_with_other_clicks | bijia_with_home_click | haojia_with_home_click | trend_with_home_click |
| ----------------- | ---------------------- | --------------------- | ---------------------- | --------------------- |
| click_label_check | 0                      | 0                     | 0                      | 0                     |

**结论**: ✅ 标签语义正确，无跨场景污染

______________________________________________________________________

### 2.3 SQL4: is_home_scene_click字段验证

```sql
SELECT
    COUNT_IF(is_home_scene_click IS NOT NULL) AS non_null_count,
    COUNT_IF(is_home_scene_click = 1) AS positive_count,
    COUNT(1) AS total_count
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013'
LIMIT 1;
```

**结果**:

```
FAILED: ODPS-0130071:[2,14] Semantic analysis exception - column is_home_scene_click cannot be resolved
```

**结论**: ✅ 字段不存在，已从config删除（验证通过）

______________________________________________________________________

### 2.4 SQL5: 各场景CVR分布

```sql
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
        ELSE 'UNKNOWN'
    END AS scene,
    COUNT(1) AS pv,
    SUM(is_conversion) AS cvr_label_convs,
    SUM(CASE WHEN is_home_scene = 1 THEN is_conversion ELSE 0 END) AS home_convs,
    SUM(CASE WHEN is_bijia_scene = 1 THEN is_bijia_conversion ELSE 0 END) AS bijia_convs,
    SUM(CASE WHEN is_haojia_scene = 1 THEN is_haojia_conversion ELSE 0 END) AS haojia_convs,
    SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_conversion ELSE 0 END) AS trend_convs,
    ...
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013'
GROUP BY scene;
```

**结果**:

| scene  | pv         | cvr_label_convs | home_convs | bijia_convs | haojia_convs | trend_convs | cvr_rate | home_cvr | bijia_cvr | haojia_cvr | trend_cvr |
| ------ | ---------- | --------------- | ---------- | ----------- | ------------ | ----------- | -------- | -------- | --------- | ---------- | --------- |
| haojia | 8,886,338  | 0               | 0          | 0           | 465,802      | 0           | 0.0      | N/A      | N/A       | 5.24       | N/A       |
| trend  | 11,450,974 | 0               | 0          | 0           | 0            | 1,972,750   | 0.0      | N/A      | N/A       | N/A        | 17.23     |
| home   | 80,215,798 | 9,569,003       | 9,569,003  | 0           | 0            | 0           | 11.93    | 11.93    | N/A       | N/A        | N/A       |
| bijia  | 19,558,474 | 0               | 0          | 2,656,728   | 0            | 0           | 0.0      | N/A      | 13.58     | N/A        | N/A       |

**关键发现**:

1. **is_conversion只在home场景有值**（9.57M），非home场景均为0
1. 各场景有自己的conversion标签：
   - bijia_conversion: 2.66M (13.58%)
   - trend_conversion: 1.97M (17.23%)
   - haojia_conversion: 0.47M (5.24%)
1. **CVR标签也存在同样的矛盾**：非home场景的is_conversion被硬编码为0

______________________________________________________________________

### 2.5 SQL6: CVR标签语义验证

```sql
SELECT
    'conversion_label_check' AS check_item,
    SUM(CASE WHEN is_home_scene = 1 AND (is_bijia_conversion = 1 OR is_haojia_conversion = 1 OR is_trend_conversion = 1) THEN 1 ELSE 0 END) AS home_with_other_convs,
    SUM(CASE WHEN is_bijia_scene = 1 AND is_conversion = 1 THEN 1 ELSE 0 END) AS bijia_with_home_conv,
    SUM(CASE WHEN is_haojia_scene = 1 AND is_conversion = 1 THEN 1 ELSE 0 END) AS haojia_with_home_conv,
    SUM(CASE WHEN is_trend_scene = 1 AND is_conversion = 1 THEN 1 ELSE 0 END) AS trend_with_home_conv
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013';
```

**结果**:

| check_item             | home_with_other_convs | bijia_with_home_conv | haojia_with_home_conv | trend_with_home_conv |
| ---------------------- | --------------------- | -------------------- | --------------------- | -------------------- |
| conversion_label_check | 0                     | 0                    | 0                     | 0                    |

**结论**: ✅ CVR标签语义正确，无跨场景污染

______________________________________________________________________

## 三、问题分析

### 3.1 已验证的问题

| 问题                    | 状态      | 说明                                                       |
| ----------------------- | --------- | ---------------------------------------------------------- |
| CTR标签矛盾             | ✅ 已修复 | ctr tower添加`task_space_indicator_label: "is_home_scene"` |
| is_home_scene_click字段 | ✅ 已清理 | 字段不存在，已从config删除                                 |
| CVR标签矛盾             | ✅ 已验证 | is_conversion只在home场景有值，非home场景被硬编码为0       |
| CVR标签语义             | ✅ 正确   | 无跨场景污染                                               |

### 3.2 CVR标签矛盾的影响

**现状**:

- `cvr tower`: `label_name="is_conversion"`, `task_space_indicator_label="is_home_scene"`
- is_conversion只在home场景有值（9.57M），非home场景均为0
- 各场景有自己的conversion标签（is_bijia_conversion等）

**影响分析**:

1. **当前修复有效**：cvr掩码已限制只在家场景计算loss，非home行的is_conversion=0不会影响训练
1. **信息丢失**：bijia/trend/haojia的conversion信号未被利用（各2.66M/1.97M/0.47M）
1. **CTCVR路径**：`use_ctcvr_loss=true`时，cvr自身loss被跳过，CTCVR从ctr配置读取掩码

### 3.3 是否需要添加CVR辅助任务？

**选项A：保持现状**

- 优点：简单，当前修复已解决问题
- 缺点：丢失多场景CVR信号（约5.1M正样本）

**选项B：添加CVR辅助任务**

```protobuf
tower_name: "bijia_cvr"
label_name: "is_bijia_conversion"
task_space_indicator_label: "is_bijia_scene"

tower_name: "haojia_cvr"
label_name: "is_haojia_conversion"
task_space_indicator_label: "is_haojia_scene"

tower_name: "trend_cvr"
label_name: "is_trend_conversion"
task_space_indicator_label: "is_trend_scene"
```

- 优点：利用多场景CVR信号，可能提升CTCVR效果
- 缺点：增加模型复杂度，需要验证收益

**建议**: 先跑当前修复版训练，观察CTR GAUC提升效果，再决定是否添加CVR辅助任务。

______________________________________________________________________

## 四、修复确认

### 4.1 配置文件

```
原始: home_flow_2608_v19_multiscene.config
修复: home_flow_2608_v19_multiscene_v2_fix_label_leak.config
```

### 4.2 关键改动

```diff
@@ -13011 +13011,3 @@
       }
+      task_space_indicator_label: "is_home_scene"
+      in_task_space_weight: 1
+      out_task_space_weight: 0
     }
@@ -13032 +13035 @@
-      task_space_indicator_label: "is_click"
+      task_space_indicator_label: "is_home_scene"
@@ -77 -77 @@
-  label_fields: "is_home_scene_click"  # 已删除
```

### 4.3 脚本更新

```bash
# train_v19_multiscene.sh
TRAIN_CONFIG="${1:-${CONFIG_DIR}/home_flow_2608_v19_multiscene.config}"
```

支持参数传入config路径。

______________________________________________________________________

## 五、下一步行动

### 5.1 启动训练

```bash
bash data/pepnet_demo/config/v19/train_v19_multiscene.sh \
  home_flow_2608_v19_multiscene_v2_fix_label_leak.config \
  20261013
```

### 5.2 关键观测指标

| 指标       | 修复前 | 预期修复后   | 判断标准             |
| ---------- | ------ | ------------ | -------------------- |
| CTR loss   | 1.747  | **上升**     | 去掉easy负样本       |
| CTCVR loss | 0.206  | **大幅上升** | 去掉~35.8%白送负样本 |
| CTR GAUC   | 0.7010 | **提升≥1%**  | 核心成功标准         |
| CTR AUC    | 0.8322 | 不确定       | 不可靠，仅作参考     |

### 5.3 决策标准

- **成功**：CTR GAUC > 0.708（相对提升≥1%）
- **失败**：CTR GAUC < 0.7010或loss无变化
- **回退**：立即停止，检查掩码逻辑

### 5.4 P0-1 无掩码对照 run 与 T_max 修正（2026-10-21 更新）

**实测**：当前配置 `num_epochs: 1`、**7541 步/epoch**（`Training Epoch 0: 7541it` 为全量 batch 数）。

**T_max 已修正**（两配置各 4 处）：

```
触底步数 = warmup(1000) + T_max = 7300  ← 日志 7300it 全组 lr=1e-4，与调度器公式吻合
T_max: 6300 → 6541 = steps_per_epoch × num_epochs − warmup_size = 7541 − 1000
```

（`tzrec/optim/lr_scheduler.py:199-207`：warmup 先走满，余弦随后计 T_max，到点钳在 min_learning_rate。换数据/换卡数后需重算。）

**A/B 实验矩阵**（一次只改一个变量——两臂唯一差异 = ctr 塔掩码）：

| Run         | 配置文件                                                  | ctr 掩码      | T_max | 数据       |
| ----------- | --------------------------------------------------------- | ------------- | ----- | ---------- |
| A（修复组） | `home_flow_2608_v19_multiscene_v2_fix_label_leak.config`  | is_home_scene | 6541  | 与对照同   |
| B（对照组） | `home_flow_2608_v19_multiscene_v2_no_mask_control.config` | **无**        | 6541  | 与修复组同 |

两文件 diff 已核验：**唯一差异是 ctr 塔三行**（`task_space_indicator_label` / `in_task_space_weight` / `out_task_space_weight`）。cvr 塔掩码两臂一致保留（`use_ctcvr_loss=true` 时 cvr 自身 loss 被跳过，该掩码是空操作，不构成变量）。

**读数口径**（P0-1 量化证据）：

1. `binary_cross_entropy_ctr` / `binary_cross_entropy_ctcvr`：A 应明显高于 B（抬升公式 1/[ρ+(1−ρ)r]，ρ=home 占比≈0.68）；
1. 非 home 行的 `probs_ctr` 均值：B 中应被压向 0（伪负样本），A 中不被压；
1. 池化 AUC − grouped_auc 的差距：B 中大（场景可分性水分），A 中收窄。
1. 注意：旧 run（T_max=6300）与新 run 相比多一个 T_max 变量，跨新旧比较时以 **A vs B 同批对比**为准。

**A/B 结果（2026-10-22，两 run 第 7500/7541 步，LABEL_DIST 逐字段一致 → 同一数据流）**：

| 判据                 | A（掩码开） | B（掩码关）               | 判定                                                                       |
| -------------------- | ----------- | ------------------------- | -------------------------------------------------------------------------- |
| bce_ctr              | 2.61088     | 1.74972                   | +49.2%，达理论上限(1−ρ)/ρ=50.1% 的 98%；反推 r=μ_nonhome/μ_home=**0.0117** |
| bce_ctcvr            | 0.29805     | 0.20096                   | +48.3%（r=0.0239）——此前"CTCVR 会升更多"的预测未兑现，两塔抬升几乎相同     |
| 非 home 行 ctr 得分  | +0.279      | **≈0**（min=0.0000 饱和） | 伪负样本压分实锤                                                           |
| 池化−分组 AUC 差     | +0.019      | +0.132                    | 0.13"水分"实锤（旧 run +0.133 ≈ B）                                        |
| home grouped_auc_ctr | 0.70403     | 0.70309                   | **仅 +0.09pp**，单 run 噪声内，需 OOT/多 seed 定论                         |
| 辅助塔 GAUC ×3       | ±0.001      | —                         | 不受影响 ✓                                                                 |

**定论**：P0-1 机制 100% 实锤（公式级吻合）；修复必要（指标口径 + 非 home 分数 + 防止按假 AUC 选错模型——若按池化 auc_ctr 选，B 会"赢"11.2pp）；但单 epoch 内对 home 排序的实际收益很小（伤害以"分母稀释+指标失真"为主，被压行的梯度贡献≈0）。**保留 A 为基线；P0-3（OOT 评估）升为下一优先动作**——没有样本外指标，+0.09pp 无法定论。

______________________________________________________________________

## 六、参考文档

- `sql/2609/verify_label_distribution_v5.sql` - 验证SQL
- `config/v19/LABEL_LEAK_FIX_V2.md` - 本文档
- `OPTIMIZATION_ANALYSIS.md` - 优化必要性分析
- `TRAINING_ANALYSIS_20261017.md` - 30天训练分析
- `PHASE1_FINAL_SUMMARY.md` - Phase 1执行方案

______________________________________________________________________

**验证完成时间**: 2026-10-20 21:45
**验证文件**: `sql/2609/verify_label_distribution_v5.sql`
**下一步**: 启动60天样本训练
