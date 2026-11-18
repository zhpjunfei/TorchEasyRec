-- ============================================================
-- v5 Label 逻辑可行性验证（汇总版）
-- 分区: dt='20261013'
-- ============================================================

-- 1. 各场景样本量及占比
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
        ELSE 'other'
    END AS scene,
    COUNT(1) AS total_pv,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (), 2) AS pct,
    SUM(is_click) AS clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr_pct,
    SUM(is_conversion) AS convs,
    ROUND(SUM(is_conversion) * 100.0 / COUNT(1), 2) AS cvr_pct
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
GROUP BY
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
        ELSE 'other'
    END
ORDER BY total_pv DESC
;

-- 2. 各场景曝光率
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
    SUM(is_conversion) AS convs
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

-- 3. CTR后CVR（转化漏斗）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    SUM(is_click) AS clicks,
    SUM(is_conversion) AS convs,
    ROUND(SUM(is_conversion) * 100.0 / NULLIF(SUM(is_click), 0), 2) AS cvr_after_click_pct
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

-- 4. 序列特征统计（click_cnt, click_num）
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
    PERCENTILE(click_num, ARRAY[0.5, 0.9, 0.95, 0.99]) AS click_num_percentiles
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

-- 5. 高频用户检测（click_num >= 100）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS high_freq_pv,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (), 2) AS high_freq_pct
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND click_num >= 100
GROUP BY
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END
;
