-- ============================================================================
-- 勘验 SQL：home_flow_2606_ctrcvr_sorter_label_table_v5  P1-8 修复回跑验证
-- 基线分区：dt='20261014'（修复前唯一分区，实测对照基准）
-- 修复分区：dt BETWEEN '20261015' AND '20261021'（共 7 天，全部为修复后回跑）
-- 粒度基准：label 表键 = (item_id, mmb_id, request_id)
-- 对照提示：20261014 与 20261021 同为周三，星期效应可对消，是最佳对比对
-- 用法：逐条独立执行（均按 dt 分组，一条 SQL 看全 8 天）；结果发回判读
-- ============================================================================

-- ----------------------------------------------------------------------------
-- SQL-0 基线：总量与场景分布（修复前 20261014 vs 修复后 20261015~21）
-- 期望：home/bijia/haojia 各日行数与正样本率平稳（日间波动，周三对周三最佳）；
--       trend 行数修复后各日 ≈ 20261014 的 40%~50%（2~3 行/组合合并为 1 行）
-- ----------------------------------------------------------------------------
SELECT  dt
        ,CASE WHEN is_home_scene = 1 THEN 'home'
              WHEN is_bijia_scene = 1 THEN 'bijia'
              WHEN is_haojia_scene = 1 THEN 'haojia'
              WHEN is_trend_scene = 1 THEN 'trend'
              ELSE 'UNKNOWN' END AS scene
        ,COUNT(1) AS pv
        ,SUM(is_trend_click) AS trend_clicks
        ,SUM(is_trend_conversion) AS trend_convs
        ,SUM(is_click) AS home_clicks
        ,SUM(is_conversion) AS home_convs
FROM    mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE   dt BETWEEN '20261014' AND '20261021'
GROUP BY dt
        ,CASE WHEN is_home_scene = 1 THEN 'home'
              WHEN is_bijia_scene = 1 THEN 'bijia'
              WHEN is_haojia_scene = 1 THEN 'haojia'
              WHEN is_trend_scene = 1 THEN 'trend'
              ELSE 'UNKNOWN' END
ORDER BY dt, scene
;

-- ----------------------------------------------------------------------------
-- SQL-1 【核心判据】trend 按表键的重复组合
-- 20261014（修复前）：预期大量重复（GROUP BY 含 event_unix_time 所致）
-- 20261015~21（修复后）：**每天 dup_combos 必须 = 0**
-- ----------------------------------------------------------------------------
SELECT  dt
        ,COUNT(1) AS dup_combos
        ,SUM(cnt) AS dup_rows
FROM (
        SELECT  dt, item_id, mmb_id, request_id, COUNT(1) AS cnt
        FROM    mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
        WHERE   dt BETWEEN '20261014' AND '20261021'
        AND     is_trend_scene = 1
        GROUP BY dt, item_id, mmb_id, request_id
        HAVING COUNT(1) > 1
     ) t
GROUP BY dt
ORDER BY dt
;

-- ----------------------------------------------------------------------------
-- SQL-2 【核心判据】trend 同键标签矛盾（一行曝光 y=0 / 一行点击 y=1 的拆分残余）
-- 期望：20261015~21 每天 mixed_label_combos = 0
-- ----------------------------------------------------------------------------
SELECT  dt
        ,COUNT(1) AS mixed_label_combos
FROM (
        SELECT  dt, item_id, mmb_id, request_id
        FROM    mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
        WHERE   dt BETWEEN '20261014' AND '20261021'
        AND     is_trend_scene = 1
        GROUP BY dt, item_id, mmb_id, request_id
        HAVING COUNT(1) > 1
        AND MIN(is_trend_click) = 0 AND MAX(is_trend_click) = 1
     ) t
GROUP BY dt
ORDER BY dt
;

-- ----------------------------------------------------------------------------
-- SQL-3 【核心判据】conv 行级 ⊆ click（"转化行 click=0"是 P1-8 的行级指纹）
-- 20261014（修复前）：trend_conv_wo_click/trend_convs 预期 ≈100%（60d 表实测曾为
--                   1,993,728/1,972,750）
-- 20261015~21（修复后）：**< 2%**（残余是"转化事件无对应点击事件"的真实情况，
--                   与 bijia/haojia 同量级）
-- ----------------------------------------------------------------------------
SELECT  dt
        ,SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend_rows
        ,SUM(CASE WHEN is_trend_scene = 1 AND is_trend_conversion = 1 THEN 1 ELSE 0 END) AS trend_convs
        ,SUM(CASE WHEN is_trend_scene = 1 AND is_trend_conversion = 1 AND is_trend_click = 0 THEN 1 ELSE 0 END) AS trend_conv_wo_click
        ,SUM(CASE WHEN is_bijia_scene = 1 AND is_bijia_conversion = 1 AND is_bijia_click = 0 THEN 1 ELSE 0 END) AS bijia_conv_wo_click
        ,SUM(CASE WHEN is_haojia_scene = 1 AND is_haojia_conversion = 1 AND is_haojia_click = 0 THEN 1 ELSE 0 END) AS haojia_conv_wo_click
FROM    mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE   dt BETWEEN '20261014' AND '20261021'
GROUP BY dt
ORDER BY dt
;

-- ----------------------------------------------------------------------------
-- SQL-4 回归：trend_click_pair 语义（保留的请求至少有一行点击）
-- 期望：20261015~21 每天 req_without_click = 0（20261014 也应为 0，作对照）
-- ----------------------------------------------------------------------------
SELECT  dt
        ,COUNT(1) AS req_without_click
FROM (
        SELECT  dt, mmb_id, request_id
        FROM    mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
        WHERE   dt BETWEEN '20261014' AND '20261021'
        AND     is_trend_scene = 1
        GROUP BY dt, mmb_id, request_id
        HAVING SUM(is_trend_click) = 0
     ) t
GROUP BY dt
ORDER BY dt
;

-- ----------------------------------------------------------------------------
-- SQL-5 回归：场景互斥 + 跨场景标签零污染（修复未破坏其他场景）
-- 期望：8 天三个计数均为 0
-- ----------------------------------------------------------------------------
SELECT  dt
        ,SUM(CASE WHEN is_home_scene + is_bijia_scene + is_haojia_scene + is_trend_scene <> 1 THEN 1 ELSE 0 END) AS bad_scene_flag
        ,SUM(CASE WHEN is_home_scene = 1
                   AND (is_bijia_click = 1 OR is_haojia_click = 1 OR is_trend_click = 1
                        OR is_bijia_conversion = 1 OR is_haojia_conversion = 1 OR is_trend_conversion = 1)
                  THEN 1 ELSE 0 END) AS home_with_other_labels
        ,SUM(CASE WHEN is_trend_scene = 1
                   AND (is_click = 1 OR is_conversion = 1
                        OR is_bijia_click = 1 OR is_haojia_click = 1
                        OR is_bijia_conversion = 1 OR is_haojia_conversion = 1)
                  THEN 1 ELSE 0 END) AS trend_with_foreign_labels
FROM    mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE   dt BETWEEN '20261014' AND '20261021'
GROUP BY dt
ORDER BY dt
;

-- ----------------------------------------------------------------------------
-- SQL-6 口径复核：NULL 键 + (item_id, request_id) 粒度重复（B-5，防 mmb 串扰）
-- 期望：null_key_rows 为 0；dup_item_req_combos 与 SQL-1 同为 0
--（若 (item,req) 重复多于 SQL-1，多出部分即 request_id 跨用户复用的串扰）
-- ----------------------------------------------------------------------------
SELECT  dt
        ,SUM(CASE WHEN item_id IS NULL OR mmb_id IS NULL OR request_id IS NULL THEN 1 ELSE 0 END) AS null_key_rows
FROM    mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE   dt BETWEEN '20261014' AND '20261021'
AND     is_trend_scene = 1
GROUP BY dt
ORDER BY dt
;

SELECT  dt
        ,COUNT(1) AS dup_item_req_combos
FROM (
        SELECT  dt, item_id, request_id, COUNT(1) AS cnt
        FROM    mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
        WHERE   dt BETWEEN '20261014' AND '20261021'
        AND     is_trend_scene = 1
        GROUP BY dt, item_id, request_id
        HAVING COUNT(1) > 1
     ) t
GROUP BY dt
ORDER BY dt
;

-- ============================================================================
-- 判读速查（dt=20261014 为修复前基准；20261015~21 全部须达标）
-- | 判据 | 20261014（前） | 20261015~21（后）通过线 |
-- | SQL-1 重复组合 | >0 | 每天 = 0 |
-- | SQL-2 标签矛盾 | 大量 | 每天 = 0 |
-- | SQL-3 trend conv无click 占比 | ≈100% | 每天 < 2% |
-- | SQL-4 无点击请求 | =0（对照） | 每天 = 0 |
-- | SQL-5 脏场景/污染 | =0（对照） | 每天 = 0 |
-- | SQL-6 NULL 键 / (item,req) 重复 | — | 每天 = 0 / = 0 |
-- | SQL-0 trend 行数 | 基准 | ≈ 40%~50%（周三对周三：20261014 vs 20261021） |
--
-- 全部通过后：重跑 fix_sample → 60d 汇总 → 对 60d 表跑 verify_trend_duplicate.sql
--（按 B-5 建议把其分组键补上 mmb_id，并关注 ≥5 行/组合桶是否归零——那是 join fan-out 的定性证据）
-- ============================================================================
