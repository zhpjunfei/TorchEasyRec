# 标签泄漏问题修复 - 最终方案

**日期**: 2026-10-20
**问题类型**: 结构性标签矛盾（Task Space Leakage）
**修复状态**: ✅ 已完成

______________________________________________________________________

## 一、问题本质

### 1.1 标签语义矛盾

在v5样本表中，非home场景的行存在**双重重构**：

```sql
-- bijia场景分支（第84-95行）
CAST(0 AS BIGINT) AS is_click,           -- CTR塔看到"负样本"
...
is_bijia_click AS is_bijia_click,        -- bijia_click塔看到"正样本"
...
1 AS is_bijia_scene                      -- 场景标记
```

**矛盾**：同一行样本，CTR塔被要求预测"不点击"，而辅助塔被要求预测"点击"。

### 1.2 配置缺陷

| Tower        | 原掩码            | 问题                                   |
| ------------ | ----------------- | -------------------------------------- |
| ctr          | 无                | ❌ 所有样本参与，非home行喂错误梯度    |
| cvr          | `is_click`        | ❌ 只在正样本上计算，退化为"永远预测1" |
| bijia_click  | `is_bijia_scene`  | ✅ 正确                                |
| haojia_click | `is_haojia_scene` | ✅ 正确                                |
| trend_click  | `is_trend_scene`  | ✅ 正确                                |

______________________________________________________________________

## 二、修复内容

### 2.1 修改文件

```
原始: home_flow_2608_v19_multiscene.config
修复: home_flow_2608_v19_multiscene_v2_fix_label_leak.config
```

### 2.2 具体改动

**改动1：ctr tower添加掩码**

```protobuf
# 修复前
tower_name: "ctr"
label_name: "is_click"
weight: 4.5
# ... (无掩码配置)

# 修复后
tower_name: "ctr"
label_name: "is_click"
weight: 4.5
# ...
task_space_indicator_label: "is_home_scene"  # ✅ 新增
in_task_space_weight: 1
out_task_space_weight: 0
```

**改动2：cvr tower修正掩码**

```protobuf
# 修复前
task_space_indicator_label: "is_click"  # ❌ 错误

# 修复后
task_space_indicator_label: "is_home_scene"  # ✅ 正确
```

______________________________________________________________________

## 三、影响分析

### 3.1 修复前的问题

**CTR AUC虚高假象**：

```
AUC = 0.8266（虚高）
GAUC = 0.6933（真实）
Gap = 0.1333（主要由标签泄漏造成）
```

**原因**：

- 正样本全部来自home（真实点击）
- 负样本混入大量"天然低分"的非home行
- 模型学会"区分home和非home"而非"区分用户兴趣"

**梯度冲突**：

```
非home样本同时向两个方向拉扯共享主干：
- CTR塔：拉向"低分"（因为is_click=0）
- 辅助塔：拉向"高分"（因为有真实点击）

weight: 4.5 放大了这个冲突
```

### 3.2 修复后的预期

| 指标       | 修复前 | 预期修复后 | 变化               |
| ---------- | ------ | ---------- | ------------------ |
| CTR AUC    | 0.8322 | 0.78~0.80  | 下降（回归真实）   |
| CTR GAUC   | 0.7010 | **0.72+**  | 提升（消除冲突）   |
| CVR AUC    | 0.7358 | 0.75+      | 提升（校准更准确） |
| bijia GAUC | 0.8769 | 0.88+      | 稳定或微升         |

**核心判断标准**：CTR GAUC > 0.72

______________________________________________________________________

## 四、验证方案

### 4.1 样本分布验证SQL

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

**预期**：

- home: ~1.8M样本，CTR ~37%
- 其他场景: 不参与CTR loss（被掩码排除）

### 4.2 训练验证SQL

```sql
-- 对比修复前后关键指标
SELECT
    'before_fix' AS version,
    0.8322 AS ctr_auc,
    0.7010 AS ctr_gauc,
    0.7358 AS cvr_auc,
    0.8769 AS bijia_gauc;

-- 修复后运行训练，替换上面数值
```

______________________________________________________________________

## 五、训练命令

```bash
# 使用修复版config训练
bash data/pepnet_demo/config/v19/train_v19_multiscene.sh \
  --config data/pepnet_demo/config/v19/home_flow_2608_v19_multiscene_v2_fix_label_leak.config \
  --days 60
```

______________________________________________________________________

## 六、风险评估

| 风险             | 概率 | 影响 | 缓解措施                         |
| ---------------- | ---- | ---- | -------------------------------- |
| 修复后GAUC无提升 | 中   | 中   | 设置回退点，无提升则分析其他方向 |
| 修复后GAUC下降   | 低   | 高   | 立即回退到原始config             |
| 训练时间增加     | 低   | 低   | 样本量减少约33%，训练时间应减少  |
| CTCVR逻辑异常    | 低   | 中   | 验证CTCVR loss计算是否正确       |

______________________________________________________________________

## 七、决策标准

### 成功标准

- CTR GAUC > 0.72（当前0.7010）
- CTR AUC回归到0.78~0.80（合理区间）
- CVR AUC > 0.75

### 失败标准

- CTR GAUC < 0.69（比修复前还差）
- 训练报错或loss异常

### 行动指南

1. **如果成功**：确认修复有效，进入Phase 2（P0特征添加）
1. **如果无效**：重新分析其他优化方向（特征工程、模型结构）
1. **如果失败**：回退配置，检查掩码逻辑是否正确实现

______________________________________________________________________

## 八、参考

- `OPTIMIZATION_ANALYSIS.md`：优化必要性分析
- `TRAINING_ANALYSIS_20261017.md`：30天训练分析
- `PHASE1_FINAL_SUMMARY.md`：Phase 1执行方案
- `tzrec/models/multi_task_rank.py:127-147`：掩码实现逻辑
- `tzrec/models/multi_task_rank.py:186-196`：CTCVR掩码读取逻辑

______________________________________________________________________

**修复完成时间**: 2026-10-20 15:30
**修复文件**: `home_flow_2608_v19_multiscene_v2_fix_label_leak.config`
**下一步**: 启动60天样本训练验证效果
