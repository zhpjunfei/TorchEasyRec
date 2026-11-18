-- ============================================================
-- v5 可行性决策验证 SQL
-- 目的：从效果提升角度评估 v5 label 逻辑是否合理
-- ============================================================

-- 1. 各场景正负样本比（评估样本均衡性）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS total_pv,
    SUM(is_click) AS positive_clicks,
    COUNT(1) - SUM(is_click) AS negative_clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr_pct,
    ROUND(SUM(is_click) * 100.0 / (COUNT(1) - SUM(is_click)), 2) AS pos_neg_ratio
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

-- 2. 各场景转化质量（CTR后CVR，评估conversion信号强度）
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

-- 3. 各场景曝光转化率（评估真实转化能力）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    SUM(is_exposure) AS exposures,
    SUM(is_conversion) AS convs,
    ROUND(SUM(is_conversion) * 100.0 / NULLIF(SUM(is_exposure), 0), 2) AS cvr_after_exposure_pct
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

-- 4. 各场景 user 级别行为统计（评估序列特征可用性）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(DISTINCT mmb_id) AS unique_users,
    AVG(click_num) AS avg_clicks_per_user,
    PERCENTILE(avg_clicks_per_user, ARRAY[0.5, 0.9, 0.95, 0.99]) AS user_click_percentiles
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

-- 5. 异常样本检测（click_num >= 100 的高频用户）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS high_freq_users,
    COUNT(DISTINCT mmb_id) AS unique_mmb_ids
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
