-- ============================================================
-- v5 序列特征质量验证
-- 目的：验证多场景引入后，各场景序列特征是否有效
-- ============================================================

-- 1. 各场景 click_50 序列长度分布（需要看 chajia_50 等序列字段）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS total_samples,
    -- click 序列特征统计（如果有）
    AVG(LENGTH(COALESCE(click_10_seq, ''))) AS avg_click_10_len,
    AVG(LENGTH(COALESCE(click_50_seq, ''))) AS avg_click_50_len,
    -- chajia 序列特征统计
    AVG(LENGTH(COALESCE(chajia_50_seq, ''))) AS avg_chajia_50_len
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

-- 2. 各场景序列特征空值率
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    COUNT(1) AS total,
    SUM(CASE WHEN click_10_seq IS NULL OR click_10_seq = '' THEN 1 ELSE 0 END) AS click_10_empty,
    ROUND(SUM(CASE WHEN click_10_seq IS NULL OR click_10_seq = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 2) AS click_10_empty_pct,
    SUM(CASE WHEN click_50_seq IS NULL OR click_50_seq = '' THEN 1 ELSE 0 END) AS click_50_empty,
    ROUND(SUM(CASE WHEN click_50_seq IS NULL OR click_50_seq = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 2) AS click_50_empty_pct,
    SUM(CASE WHEN chajia_50_seq IS NULL OR chajia_50_seq = '' THEN 1 ELSE 0 END) AS chajia_50_empty,
    ROUND(SUM(CASE WHEN chajia_50_seq IS NULL OR chajia_50_seq = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 2) AS chajia_50_empty_pct
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

-- 3. 各场景行为序列的唯一 item_id 数量（评估序列多样性）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END AS scene,
    mmb_id,
    COUNT(DISTINCT item_id) AS unique_items,
    COUNT(1) AS total_events,
    ROUND(COUNT(DISTINCT item_id) * 100.0 / COUNT(1), 2) AS uniqueness_pct
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
GROUP BY
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 2 THEN 'bijia'
        WHEN 3 THEN 'haojia'
        WHEN 4 THEN 'trend'
    END,
    mmb_id
HAVING COUNT(1) >= 5  -- 只看有足够行为的用户
;
