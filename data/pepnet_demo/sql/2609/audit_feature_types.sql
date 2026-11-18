-- ============================================================
-- 按特征类型统计覆盖率（用户侧 vs 商品侧）
-- dt='20261013'
-- ============================================================

-- 用户侧特征覆盖率
SELECT
    'user_side' AS feature_type,
    COUNT(DISTINCT mmb_id || '|' || request_id) AS total,
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home,
    SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS bijia,
    SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS haojia,
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'

UNION ALL

-- 商品静态特征覆盖率（假设item_id有效即特征有效）
SELECT
    'item_static' AS feature_type,
    COUNT(DISTINCT item_id || '|' || request_id) AS total,
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home,
    SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS bijia,
    SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS haojia,
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
  AND item_id IS NOT NULL AND item_id != ''

UNION ALL

-- 有序列特征的样本
SELECT
    'with_sequence' AS feature_type,
    COUNT(DISTINCT mmb_id || '|' || request_id) AS total,
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home,
    SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS bijia,
    SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS haojia,
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend
FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
INNER JOIN home_flow_2606_mmb_id_all_seq_feat_v1 sq56
    ON sq0.mmb_id = sq56.mmb_id AND sq0.request_id = sq56.request_id AND sq56.dt = '20261013'
WHERE sq0.dt = '20261013'

UNION ALL

-- 有item_rt特征的样本
SELECT
    'with_item_rt' AS feature_type,
    COUNT(DISTINCT mmb_id || '|' || request_id) AS total,
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home,
    SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS bijia,
    SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS haojia,
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend
FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
LEFT JOIN home_flow_2604_item_id_rt_statistic_feat_v1 sq30
    ON sq0.item_id = sq30.item_id AND sq0.request_id = sq30.request_id AND sq30.dt = '20261013'
WHERE sq0.dt = '20261013'
  AND sq30.item_id IS NOT NULL
;
