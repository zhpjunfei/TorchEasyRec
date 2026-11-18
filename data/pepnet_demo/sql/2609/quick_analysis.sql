-- ============================================================
-- v5 快速分析 SQL（dt='20261013'）
-- ============================================================

-- 1. 详细指标
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS total_pv,
    SUM(is_click) AS clicks,
    SUM(is_conversion) AS convs,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr_pct,
    ROUND(SUM(is_conversion) * 100.0 / COUNT(1), 2) AS cvr_exposure_pct,
    ROUND(SUM(is_conversion) * 100.0 / NULLIF(SUM(is_click), 0), 2) AS cvr_click_pct,
    SUM(is_exposure) AS exposure_cnt,
    ROUND(SUM(is_exposure) * 100.0 / COUNT(1), 2) AS exposure_rate_pct
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

-- 2. 与 v3 对比（home 场景）
SELECT
    'v3' AS version, COUNT(1) AS pv, SUM(is_click) AS clicks, SUM(is_conversion) AS convs
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '20261013' AND is_home_scene = 1
UNION ALL
SELECT
    'v5', COUNT(1), SUM(is_click), SUM(is_conversion)
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_home_scene = 1
;

-- 3. 序列特征统计
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS total,
    ROUND(AVG(click_cnt), 2) AS avg_click_cnt,
    ROUND(AVG(click_num), 2) AS avg_click_num,
    PERCENTILE(click_num, ARRAY[0.5, 0.9, 0.95, 0.99]) AS percentiles,
    SUM(CASE WHEN click_num >= 100 THEN 1 ELSE 0 END) AS high_freq_count,
    ROUND(SUM(CASE WHEN click_num >= 100 THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 2) AS high_freq_pct
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
