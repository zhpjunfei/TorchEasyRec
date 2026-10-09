# Label Table v3 设计文档

> 状态：SQL 完成，待 ODPS 运行验证
> 最后更新：2026-09-01
> 关联 Issue：[Issue #1](https://github.com/zhpjunfei/TorchEasyRec/issues/1)

## 关联文件

| 文件            | 路径                                                                                                                | 说明                      |
| --------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| Label Table SQL | [v3/home_flow_2606_ctrcvr_sorter_label_table_v3](../sql/2606_sample/v3/home_flow_2606_ctrcvr_sorter_label_table_v3) | 核心产出物，22 列，4 场景 |
| Audit SQL       | [v3/home_flow_2606_label_table_v3_audit.sql](../sql/2606_sample/v3/home_flow_2606_label_table_v3_audit.sql)         | 9 项校验                  |
| 本文档          | [docs/label-table-v3-design.md](./label-table-v3-design.md)                                                         | 设计决策与修复历程        |

______________________________________________________________________

## 一、背景与目标

### 1.1 Issue #1 新增场景

用户行为表 `mmb_dwh.ads_log_zhekou_rec_user_bhv_info` 新增三组事件：

| 新事件前缀        | 场景定义                                               | request_id 情况 |
| ----------------- | ------------------------------------------------------ | --------------- |
| `search_bijia_*`  | 搜索-比价：搜索页默认着陆页，item 既有帖子又有商品映射 | 有（100%）      |
| `search_haojia_*` | 搜索-好价：搜索页第二个 tab，item 纯帖子               | 有（100%）      |
| `trend_*`         | 查价场景新版日志                                       | 有（100%）      |

### 1.2 关键审计数据（单日）

```
search_bijia: exposure=1,017,184  click=109,711   conv=46,867
search_haojia: exposure=314,129   click=20,086    conv=9,263
trend:         exposure=46,973    click=82,707    conv=37,199   ← 曝光<点击（客户端依赖）
chajia:        (已移除)
search通用:    (已移除)
```

**trend 曝光少于点击的原因**：`trend_exposure` 依赖客户端发版上报，`trend_click`/`trend_conversion` 不需要。短期 app 升级率 < 100%，所以曝光数天然少于点击数。

**所有新事件的 request_id 非空率 = 100%**，因此不需要回填逻辑。

______________________________________________________________________

## 二、最终方案

### 2.1 场景架构

| 场景   | 样本来源                                  | 聚合粒度                                 | 过滤/关联逻辑                                |
| ------ | ----------------------------------------- | ---------------------------------------- | -------------------------------------------- |
| home   | `exposure/click/conversion/favorite/like` | request 级                               | 窗口采样：邻接点击 + click_num < 100         |
| bijia  | `search_bijia_*`                          | request 级                               | INNER JOIN 有 search_bijia_click 的 request  |
| haojia | `search_haojia_*`                         | request 级                               | INNER JOIN 有 search_haojia_click 的 request |
| trend  | `trend_*`                                 | event 级（按 unix_time + item + mmb_id） | 直接透传，request_id 来自源数据              |

### 2.2 CREATE TABLE 列定义（22 列）

```sql
-- 基础字段 (8)
event_unix_time, item_id, scene, mmb_id, request_id, page, day_h, week_day

-- 推荐行为标签 (4)
is_click, is_conversion, is_favorite, is_like

-- 场景行为标签 (6)
is_bijia_click, is_bijia_conversion
is_haojia_click, is_haojia_conversion
is_trend_click, is_trend_conversion

-- 场景标记 (4)
is_home_scene, is_bijia_scene, is_haojia_scene, is_trend_scene
```

**关键决策**：

- **移除了 `is_exposure`**：`rec_sample` 已通过 `request_id IS NOT NULL` 保证曝光有效性，该列为冗余
- **移除了 `is_search_*` / `is_chajia_*` 系列**：对应场景已移除
- **移除了 `__item_id__` / `__mmb_id__` 别名列**：INSERT 层直接使用原始列名

### 2.3 UNION 结构

所有 4 个分支使用**完全相同的显式 22 列 SELECT**：

```sql
INSERT OVERWRITE TABLE home_flow_2606_ctrcvr_sorter_label_table_v3
PARTITION (dt='${bdp.system.bizdate}')
SELECT event_unix_time, item_id, scene, mmb_id, request_id, page, day_h, week_day
      ,is_click, is_conversion, is_favorite, is_like
      ,is_bijia_click, is_bijia_conversion
      ,is_haojia_click, is_haojia_conversion
      ,is_trend_click, is_trend_conversion
      ,is_home_scene, is_bijia_scene, is_haojia_scene, is_trend_scene
FROM (
    SELECT ... FROM rec_filtered WHERE click_cnt > 0 AND click_num < 100
    UNION ALL
    SELECT ... FROM bijia_filtered
    UNION ALL
    SELECT ... FROM haojia_filtered
    UNION ALL
    SELECT ... FROM trend_filtered
) t
```

______________________________________________________________________

## 三、核心修复历程

### Bug 1：trend/chajia 的 request_id 被错误置空

**根因**：旧 v2 SQL 中 `CAST(NULL AS STRING) AS request_id` 是给无 request_id 的 chajia 设计的。但审计显示所有 trend/chajia 事件都有真实 request_id（`null_req = 0`）。

**修复**：改为 `request_id AS request_id`（直接透传），同时删除了整个 `request_pool` CTE 及回填逻辑。

### Bug 2：UNION ALL 列数不匹配（24 vs 23）

**根因**：`rec_filtered` 比 sample CTE 多 `click_cnt`/`click_num` 两个窗口函数列。

**修复**：在 INSERT 层对所有 4 个分支使用相同的显式 22 列 SELECT（排除 click_cnt/click_num），不再使用 `SELECT *`。

### Bug 3：重复列名 `__item_id__` / `__mmb_id__`

**根因**：为匹配 INSERT 的 `item_id AS __item_id__` 别名，在 sample CTE 中错误添加了重复列。

**修复**：从所有 sample CTE 中移除多余的别名行，INSERT SELECT 也不再使用别名。

### Bug 4：`is_exposure` 列不一致

**根因**：sample CTE 有 `is_exposure` 但 INSERT 没有，导致列数不匹配。

**修复**：从所有 sample CTE 和 rec_filtered 中移除 `is_exposure`，同时将 rec_filtered 的 WHERE 条件从 `is_exposure > 0 AND is_click >= is_conversion` 简化为 `is_click >= is_conversion`（因为 request_id IS NOT NULL 已隐含曝光）。

______________________________________________________________________

## 四、场景标记语义

### 4.1 互斥性

每个样本只属于一个场景（`scene_sum = 1`），由 9 个 audit 校验项验证。

### 4.2 bijia/haojia 的 INNER JOIN 模式

```sql
-- 只保留有点击的 request_id
WHERE is_bijia_click > 0
-- 然后拉回同一 request 下的所有 item（含未点击的）
INNER JOIN bijia_clicked_pair ON mmb_id AND request_id
```

这保证了：

- 同 request 下点击的 item 有 `is_bijia_click=1`
- 同 request 下未点击的 item 有 `is_bijia_click=0`（作为辅助任务负样本）
- 共享 request 级别的上下文特征（day_h, week_day, scene 等）

______________________________________________________________________

## 五、与 v2 的差异

| 维度                    | v2                     | v3                      |
| ----------------------- | ---------------------- | ----------------------- |
| 场景                    | home/search/chajia     | home/bijia/haojia/trend |
| request_id 回填         | chajia 用 request_pool | trend 直接透传          |
| request_pool CTE        | 存在                   | **已删除**              |
| trend/chajia GROUP BY   | 3 列                   | 4 列（含 request_id）   |
| is_exposure             | 存在                   | **已删除**              |
| is_search\_/is_chajia\_ | 存在                   | **已删除**              |
| UNION 写法              | SELECT \*              | **显式 22 列**          |
| 目标表名                | label_table_v2         | **label_table_v3**      |

______________________________________________________________________

## 六、审计 SQL（9 项校验）

| #   | 校验项                  | 验证内容                               |
| --- | ----------------------- | -------------------------------------- |
| 1   | raw_event_dist          | 源表事件分布 + trend null_req=0        |
| 2   | scene_dist              | 四场景 PV 分布                         |
| 3   | scene_mutual_excl       | 场景互斥（sum=1）                      |
| 4   | trend_request_id_check  | trend request_id 完整性 + 未来泄漏检测 |
| 5   | source_to_label_ratio   | 各分支行数 vs 源表 distinct 数         |
| 6   | bijia/haojia click_dist | 正负样本分布（验证 INNER JOIN 效果）   |
| 7   | trend_behavior_dist     | trend 行为标签 sanity                  |
| 8   | scene_request_id_valid  | 各场景 request_id 非 NULL              |
| 9   | trend_temporal_sanity   | trend request_id 时序一致性            |

______________________________________________________________________

## 七、运行顺序

```bash
# 1. 提交 label table SQL
# 2. 运行 audit SQL 逐项验证
# 3. 根据校验结果决定是否提交
```

______________________________________________________________________

## 八、已知风险

- [ ] v3 label table 尚未在 ODPS 实际运行，列对齐仅经静态分析
- [ ] fix_sample_v3（聚合特征表）需同步更新以匹配新 schema
- [ ] config v19（task_space_indicator_label 场景 mask）需确认与新场景对齐
- [ ] trend 场景 CTR 不能用 click/exposure 计算（曝光依赖客户端），应用 AUC 评估
