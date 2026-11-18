# 标签泄漏问题修复方案

**日期**: 2026-10-20
**问题**: 多场景建模中的结构性标签矛盾
**状态**: ✅ 已修复

______________________________________________________________________

## 一、问题发现

### 1.1 核心矛盾

在v5样本表中，非home场景的行存在**标签语义矛盾**：

| 场景   | is_click (主塔) | is_xxx_click (辅助塔) | 矛盾    |
| ------ | --------------- | --------------------- | ------- |
| home   | 真实点击标签    | -                     | ✅ 一致 |
| bijia  | **硬编码为0**   | 真实点击标签          | ❌ 相反 |
| haojia | **硬编码为0**   | 真实点击标签          | ❌ 相反 |
| trend  | **硬编码为0**   | 真实点击标签          | ❌ 相反 |

**后果**：同一行样本，主塔被要求预测"不点击"，辅助塔被要求预测"点击"。

### 1.2 配置缺陷

原始配置中：

- **ctr tower**：无`task_space_indicator_label` → 所有样本参与CTR loss
- **cvr tower**：`task_space_indicator_label: "is_click"` → 只在正样本上计算loss（退化风险）

______________________________________________________________________

## 二、影响分析

### 2.1 CTR AUC虚高

```
AUC = 0.8266（虚高）
GAUC = 0.6933（真实）
Gap = 0.1333
```

**原因**：

- 正样本全部来自home（真实点击）
- 负样本混入大量"天然低分"的非home行
- 模型学会"区分home和非home"而非"区分用户兴趣"

### 2.2 梯度冲突

每个非home样本同时向两个方向拉扯共享主干：

- CTR塔：拉向"低分"（因为is_click=0）
- 辅助塔：拉向"高分"（因为有真实点击）

**weight: 4.5** 进一步放大了这个冲突。

### 2.3 CTCVR污染

CTCVR loss从ctr配置读取掩码，ctr无掩码 → CTCVR对全量样本计算 → CV塔学到错误模式。

______________________________________________________________________

## 三、修复方案

### 3.1 修改内容

**文件**：`home_flow_2608_v19_multiscene_v2_fix_label_leak.config`

**改动**：

1. **ctr tower**：添加`task_space_indicator_label: "is_home_scene"`
1. **cvr tower**：修改`task_space_indicator_label`从`is_click`改为`is_home_scene`

### 3.2 修复后配置

```protobuf
# CTR Tower（修复后）
tower_name: "ctr"
label_name: "is_click"
weight: 4.5
task_space_indicator_label: "is_home_scene"  # ✅ 只在家场景计算loss
in_task_space_weight: 1
out_task_space_weight: 0

# CVR Tower（修复后）
tower_name: "cvr"
label_name: "is_conversion"
weight: 1.0
task_space_indicator_label: "is_home_scene"  # ✅ 只在家场景计算loss
in_task_space_weight: 1
out_task_space_weight: 0

# 辅助任务（保持不变）
tower_name: "bijia_click"
task_space_indicator_label: "is_bijia_scene"  # ✅
tower_name: "haojia_click"
task_space_indicator_label: "is_haojia_scene"  # ✅
tower_name: "trend_click"
task_space_indicator_label: "is_trend_scene"  # ✅
```

### 3.3 关键设计决策

**为什么用`is_home_scene`而不是`is_home_scene AND is_click`？**

| 掩码选择                     | 正样本数 | 负样本数 | 风险评估             |
| ---------------------------- | -------- | -------- | -------------------- |
| `is_home_scene`              | ~1.2M    | ~0.6M    | ✅ 正常二元分类      |
| `is_home_scene AND is_click` | ~0.4M    | ~0       | ❌ 退化成"永远预测1" |

**结论**：必须保留负样本，掩码应是"场景归属"而非"场景且点击"。

______________________________________________________________________

## 四、预期效果

### 4.1 离线指标变化

| 指标       | 修复前 | 预期修复后 | 原因                          |
| ---------- | ------ | ---------- | ----------------------------- |
| CTR AUC    | 0.8266 | 0.78~0.80  | 去掉"easy负样本"，AUC回归真实 |
| CTR GAUC   | 0.6933 | **0.72+**  | 消除梯度冲突，个性化能力提升  |
| CVR AUC    | 0.7358 | 0.75+      | 只在home场景训练，校准更准确  |
| bijia GAUC | 0.8769 | 0.88+      | 辅助塔不受影响，可能略有提升  |

### 4.2 核心判断标准

**成功标准**：CTR GAUC > 0.72（当前0.7010）

**失败标准**：CTR GAUC < 0.69（回退到修复前水平）

______________________________________________________________________

## 五、验证SQL

修复后需要重新验样本分布：

```sql
-- 验证修复后CTR loss的实际样本分布
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS pv,
    SUM(is_click) AS clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
GROUP BY scene;
```

**预期结果**：只有home场景的样本参与CTR loss，其他场景的样本被掩码排除。

______________________________________________________________________

## 六、后续行动

1. **立即**：使用修复版config启动60天样本训练
1. **对比**：修复前vs修复后的CTR GAUC
1. **决策**：
   - 如果GAUC提升 > 0.01 → 确认修复有效，进入Phase 2
   - 如果GAUC无变化 → 重新分析其他优化方向
   - 如果GAUC下降 → 回退配置，检查掩码逻辑

______________________________________________________________________

## 七、参考文档

- `OPTIMIZATION_ANALYSIS.md`：优化必要性分析
- `PHASE1_FINAL_SUMMARY.md`：Phase 1执行方案
- `TRAINING_ANALYSIS_20261017.md`：30天训练分析

______________________________________________________________________

**修复完成时间**: 2026-10-20
**修复文件**: `home_flow_2608_v19_multiscene_v2_fix_label_leak.config`
