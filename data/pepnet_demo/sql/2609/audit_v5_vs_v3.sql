-- ============================================================
-- v5 vs v3 差异验证 SQL
-- 目的：评估 label 逻辑变更对样本质量和多场景建模的影响
-- ============================================================

-- 1. 整体样本量对比（v5 新表 vs v3 旧表）
SELECT 'v3_home' AS version, COUNT(1) AS total_pv,
       SUM(is_click) AS clicks, SUM(is_conversion) AS convs
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '20261013' AND is_home_scene = 1
UNION ALL
SELECT 'v5_home', COUNT(1), SUM(is_click), SUM(is_conversion)
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_home_scene = 1
UNION ALL
SELECT 'v5_bijia', COUNT(1), SUM(is_bijia_click), SUM(is_bijia_conversion)
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_bijia_scene = 1
UNION ALL
SELECT 'v5_haojia', COUNT(1), SUM(is_haojia_click), SUM(is_haojia_conversion)
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_haojia_scene = 1
UNION ALL
SELECT 'v5_trend', COUNT(1), SUM(is_trend_click), SUM(is_trend_conversion)
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_trend_scene = 1
;

-- 2. is_exposure 过滤影响分析（对比有/无 exposure 的样本）
SELECT
    CASE WHEN is_exposure = 1 THEN 'with_exposure' ELSE 'no_exposure' END AS exposure_flag,
    COUNT(1) AS pv,
    SUM(is_click) AS clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr_pct,
    SUM(is_conversion) AS convs,
    ROUND(SUM(is_conversion) * 100.0 / COUNT(1), 2) AS cvr_pct
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_home_scene = 1
GROUP BY CASE WHEN is_exposure = 1 THEN 'with_exposure' ELSE 'no_exposure' END
;

-- 3. 各场景曝光率对比
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS total_pv,
    SUM(is_exposure) AS exposure_cnt,
    ROUND(SUM(is_exposure) * 100.0 / COUNT(1), 2) AS exposure_rate_pct,
    SUM(is_click) AS clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr_pct
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
GROUP BY
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END
;

-- 4. click_cnt 分布（相邻窗口点击数，用于序列特征）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS total,
    AVG(click_cnt) AS avg_click_cnt,
    PERCENTILE(click_cnt, ARRAY[0.25, 0.5, 0.75, 0.9, 0.95]) AS percentiles
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
GROUP BY
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END
;

-- 5. 各场景 click_num 分布（用户总点击数）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS total,
    AVG(click_num) AS avg_click_num,
    PERCENTILE(click_num, ARRAY[0.5, 0.9, 0.95, 0.99]) AS percentiles
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
GROUP BY
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END
;

-- 6. 各场景样本量占比
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS pv,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (), 2) AS pct
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
GROUP BY
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END
;
