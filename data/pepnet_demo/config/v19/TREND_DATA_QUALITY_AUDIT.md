# Trend数据质量问题审核

**日期**: 2026-10-21
**审核对象**: P1-8 数据脏问题分析
**状态**: ⚠️ 部分验证通过，需补充数据证据

______________________________________________________________________

## 一、已验证的结论

### 1.1 SQL结构问题 ✅ 确认

**代码级证据**（`home_flow_2606_ctrcvr_sorter_label_table_v5.sql`）：

```sql
-- home/bijia/haojia（正确）
GROUP BY item_id, mmb_id, request_id

-- trend（有问题）
GROUP BY event_unix_time, item_id, mmb_id, request_id  -- 第157行
```

**结论**：分析正确，trend的GROUP BY确实包含了event_unix_time。

### 1.2 问题机制 ✅ 理论成立

**假设场景**：

```
用户Y在请求Z中查看商品X：
- t1时刻：trend_exposure事件 → 行1: (item_X, user_Y, req_Z, t1, is_trend_click=0)
- t2时刻：trend_click事件   → 行2: (item_X, user_Y, req_Z, t2, is_trend_click=1)
```

由于GROUP BY包含event_unix_time，这两行不会被合并，导致：

- 特征相同（同一item、user、request）
- 标签相反（click=0 vs click=1）

**理论危害**：

1. 排序信息抹掉：等价于软标签0.5
1. 梯度方差增加：双倍样本量，单倍信息量
1. CVR打击更大：转化更稀疏，矛盾比例更高

______________________________________________________________________

## 二、待验证的结论（需要数据）

### 2.1 实际重复率 ⏳ 待确认

**需要验证**：

- trend场景中有多少比例的(item, user, request)组合出现多次？
- 重复行中有多少是"标签矛盾"的？

**验证SQL**（已创建）：

```sql
-- 检查重复组合
SELECT item_id, mmb_id, request_id, COUNT(1) AS row_count, SUM(is_trend_click) AS click_count
FROM ... WHERE is_trend_scene = 1
GROUP BY ... HAVING COUNT(1) > 1;

-- 检查标签矛盾
SELECT
  COUNT(CASE WHEN click_count > 1 AND positive_count = click_count THEN 1 END) AS all_positive,
  COUNT(CASE WHEN click_count > 1 AND positive_count = 0 THEN 1 END) AS all_negative,
  COUNT(CASE WHEN click_count > 1 AND positive_count > 0 AND positive_count < click_count THEN 1 END) AS mixed_labels
FROM (...);
```

**预期结果判断标准**：

| 指标     | 无害阈值 | 有害阈值 | 严重阈值 |
| -------- | -------- | -------- | -------- |
| 重复率   | \<5%     | 5-20%    | >20%     |
| 矛盾比例 | \<10%    | 10-30%   | >30%     |

### 2.2 trend_click GAUC最低的原因 ⏳ 需排除其他因素

**当前证据**：

- trend GAUC = 0.639（bijia 0.877, haojia 0.772）

**可能的其他原因**：

1. 样本量少：trend 11.5M vs bijia 19.6M
1. 行为模式差异：查价点击 vs 推荐点击
1. 特征缺失：trend没有chajia_seq等序列特征
1. 正样本率差异：trend 50.68% vs bijia 34.97%

**验证方法**：

- 如果重复率\<5%且矛盾比例\<10%，则数据质量问题不是主因
- 需要A/B测试：修复前后对比trend GAUC

______________________________________________________________________

## 三、方案审核

### 3.1 修复方案 ✅ 合理

**根因级修复**：

```sql
-- 修改trend_sample的GROUP BY
GROUP BY item_id, mmb_id, request_id  -- 去掉event_unix_time
```

**兜底修复**：

```sql
-- 在60d汇总脚本中添加去重
ROW_NUMBER() OVER (PARTITION BY mmb_id, item_id, request_id ORDER BY event_unix_time)
```

**评估**：

- ✅ 解决根因（GROUP BY错误）
- ✅ 防御性编程（恢复v4的去重逻辑）
- ✅ 不影响其他场景（只改trend）

### 3.2 优先级评估 ⚠️ 需权衡

**原文主张**：

> "修完之后 trend_cvr 可以升回第一优先级"

**我的审核**：

1. **支持先修数据质量**：无论是否添加trend_cvr，修复GROUP BY都是必要的
1. **暂缓trend_cvr优先级提升**：
   - 当前CVR校准已通过乘积验证（error -0.75%）
   - trend_conversion正样本率17.23%，基数足够
   - 但应先验证数据修复效果，再决定是否需要trend_cvr辅助任务

### 3.3 风险评估 ⚠️ 需注意

| 风险                      | 概率 | 影响 | 缓解措施                   |
| ------------------------- | ---- | ---- | -------------------------- |
| 修复后trend样本量大幅减少 | 中   | 中   | 监控样本量变化，确保>1M    |
| 修复后trend GAUC无提升    | 中   | 低   | 设置对照实验，观察其他指标 |
| 影响其他trend相关特征     | 低   | 高   | 全量回归测试               |

______________________________________________________________________

## 四、行动建议

### 4.1 立即执行（P0）

**运行验证SQL**：

```bash
# 验证重复率和矛盾比例
odpssql -f sql/2609/verify_trend_duplicate.sql
```

**判断标准**：

- 如果重复率>10%或矛盾比例>20% → 立即修复
- 如果重复率\<5%且矛盾比例\<10% → 降低优先级

### 4.2 短期执行（P1）

**修复SQL**（如果验证通过）：

```sql
-- 修改label_table_v5.sql的trend_sample部分
, trend_sample AS
(
    SELECT  MIN(event_unix_time) AS event_unix_time  -- 改为MIN聚合
            ,item_id
            ,mmb_id
            ,request_id
            ...
    GROUP BY item_id, mmb_id, request_id  -- 去掉event_unix_time
)
```

**恢复60d汇总去重**：

```sql
-- 在shuffled_60d_v5.sql中添加
ROW_NUMBER() OVER (
  PARTITION BY mmb_id, item_id, request_id
  ORDER BY event_unix_time
) AS rn
WHERE rn = 1
```

### 4.3 中期验证（P2）

**对比实验**：

- 修复前：当前config（baseline）
- 修复后：新config + 修复后的样本

**观察指标**：

- trend GAUC是否提升
- home CTR GAUC是否受影响（应无变化）
- 训练loss是否稳定

______________________________________________________________________

## 五、结论

### 5.1 已确认

| 结论                              | 状态    | 证据           |
| --------------------------------- | ------- | -------------- |
| trend GROUP BY包含event_unix_time | ✅ 确认 | SQL代码第157行 |
| 理论危害成立                      | ✅ 确认 | 梯度分析正确   |
| 修复方案合理                      | ✅ 确认 | 解决根因       |

### 5.2 待验证

| 结论                       | 状态          | 需要                       |
| -------------------------- | ------------- | -------------------------- |
| 实际重复率                 | ⏳ 待运行SQL  | verify_trend_duplicate.sql |
| 实际矛盾比例               | ⏳ 待运行SQL  | 同上                       |
| trend GAUC最低是否由此导致 | ⏳ 需对照实验 | 修复后对比                 |

### 5.3 建议

1. **立即运行验证SQL**，获取实际重复率数据
1. **根据数据决定优先级**：
   - 高重复率(>10%) → 立即修复
   - 低重复率(\<5%) → 可降低优先级
1. **修复后必须验证**：对比trend GAUC变化
1. **trend_cvr优先级提升需暂缓**：先验证数据修复效果

______________________________________________________________________

**审核完成时间**: 2026-10-21 11:00
**下一步**: 运行验证SQL获取实际数据
