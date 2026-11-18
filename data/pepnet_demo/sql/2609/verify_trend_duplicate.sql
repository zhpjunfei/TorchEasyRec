-- 验证trend场景重复问题（完全避开类型转换）
-- 直接使用原始列进行GROUP BY，不拼接字符串

-- SQL 1: 统计trend场景的基础信息
SELECT
    'trend_basic_stats' AS check_type,
    COUNT(1) AS total_rows,
    COUNT(DISTINCT item_id) AS unique_items,
    COUNT(DISTINCT request_id) AS unique_requests
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261020' AND is_trend_scene = 1;

-- SQL 2: 检查按(item_id, request_id)分组的重复情况
SELECT
    'duplicate_distribution' AS check_type,
    cnt AS rows_per_combo,
    COUNT(*) AS combo_count,
    COUNT(*) * cnt AS total_rows
FROM (
    SELECT
        item_id,
        request_id,
        COUNT(1) AS cnt
    FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
    WHERE dt = '20261020' AND is_trend_scene = 1
    GROUP BY item_id, request_id
    HAVING COUNT(1) > 1
) t
GROUP BY cnt
ORDER BY cnt;

-- SQL 3: 检查标签矛盾
SELECT
    'label_conflict' AS check_type,
    COUNT(CASE WHEN max_click = 1 AND min_click = 0 THEN 1 ELSE NULL END) AS mixed_labels,
    COUNT(CASE WHEN max_click = 1 AND min_click = 1 THEN 1 ELSE NULL END) AS all_click,
    COUNT(CASE WHEN max_click = 0 AND min_click = 0 THEN 1 ELSE NULL END) AS all_no_click
FROM (
    SELECT
        item_id,
        request_id,
        MAX(is_trend_click) AS max_click,
        MIN(is_trend_click) AS min_click
    FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
    WHERE dt = '20261020' AND is_trend_scene = 1
    GROUP BY item_id, request_id
    HAVING COUNT(1) > 1
) t;

-- SQL 4: 对比各场景的行数
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS total_rows
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261020'
GROUP BY scene;
