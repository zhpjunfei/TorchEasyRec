-- ============================================================
-- 全面特征覆盖检查 - 按场景统计各特征表覆盖率
-- dt='20261013'
-- ============================================================

-- 测试各关键特征表在不同场景的覆盖率
WITH base AS (
    SELECT
        mmb_id, request_id, item_id,
        is_home_scene, is_bijia_scene, is_haojia_scene, is_trend_scene
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5
    WHERE dt = '20261013'
)
SELECT
    'total' AS feature_table,
    COUNT(DISTINCT mmb_id || '|' || request_id) AS total_records,
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend_pv
FROM base

UNION ALL

-- sq56: 序列特征（已知100%）
SELECT
    'sq56_seq_feat' AS feature_table,
    COUNT(DISTINCT b.mmb_id || '|' || b.request_id) AS total_records,
    SUM(CASE WHEN b.is_home_scene = 1 AND s56.mmb_id IS NOT NULL THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN b.is_bijia_scene = 1 AND s56.mmb_id IS NOT NULL THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN b.is_haojia_scene = 1 AND s56.mmb_id IS NOT NULL THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN b.is_trend_scene = 1 AND s56.mmb_id IS NOT NULL THEN 1 ELSE 0 END) AS trend_pv
FROM base b
LEFT JOIN home_flow_2606_mmb_id_all_seq_feat_v1 s56
    ON b.mmb_id = s56.mmb_id AND b.request_id = s56.request_id AND s56.dt = '20261013'

UNION ALL

-- sq33: 用户基础信息
SELECT
    'sq33_user_basic' AS feature_table,
    COUNT(DISTINCT b.mmb_id || '|' || b.request_id) AS total_records,
    SUM(CASE WHEN b.is_home_scene = 1 AND s33.mmb_id IS NOT NULL THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN b.is_bijia_scene = 1 AND s33.mmb_id IS NOT NULL THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN b.is_haojia_scene = 1 AND s33.mmb_id IS NOT NULL THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN b.is_trend_scene = 1 AND s33.mmb_id IS NOT NULL THEN 1 ELSE 0 END) AS trend_pv
FROM base b
LEFT JOIN home_flow_2604_ads_usr_user_basic_info_preprocess_v1 s33
    ON b.mmb_id = s33.mmb_id AND s33.dt = '20261013'

UNION ALL

-- sq30: item实时统计（已知问题表）
SELECT
    'sq30_item_rt' AS feature_table,
    COUNT(DISTINCT b.mmb_id || '|' || b.request_id) AS total_records,
    SUM(CASE WHEN b.is_home_scene = 1 AND s30.item_id IS NOT NULL THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN b.is_bijia_scene = 1 AND s30.item_id IS NOT NULL THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN b.is_haojia_scene = 1 AND s30.item_id IS NOT NULL THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN b.is_trend_scene = 1 AND s30.item_id IS NOT NULL THEN 1 ELSE 0 END) AS trend_pv
FROM base b
LEFT JOIN home_flow_2604_item_id_rt_statistic_feat_v1 s30
    ON b.item_id = s30.item_id AND b.request_id = s30.request_id AND s30.dt = '20261013'

UNION ALL

-- brand特征
SELECT
    'brand_feat' AS feature_table,
    COUNT(DISTINCT b.mmb_id || '|' || b.request_id) AS total_records,
    SUM(CASE WHEN b.is_home_scene = 1 AND sb.brand IS NOT NULL THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN b.is_bijia_scene = 1 AND sb.brand IS NOT NULL THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN b.is_haojia_scene = 1 AND sb.brand IS NOT NULL THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN b.is_trend_scene = 1 AND sb.brand IS NOT NULL THEN 1 ELSE 0 END) AS trend_pv
FROM base b
LEFT JOIN home_flow_2604_brand_static_feat_15d_v1 sb
    ON b.item_id = sb.brand AND sb.dt = '20261013'

UNION ALL

-- cate_id_path特征
SELECT
    'cate_path_feat' AS feature_table,
    COUNT(DISTINCT b.mmb_id || '|' || b.request_id) AS total_records,
    SUM(CASE WHEN b.is_home_scene = 1 AND sc.cate_id_path IS NOT NULL THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN b.is_bijia_scene = 1 AND sc.cate_id_path IS NOT NULL THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN b.is_haojia_scene = 1 AND sc.cate_id_path IS NOT NULL THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN b.is_trend_scene = 1 AND sc.cate_id_path IS NOT NULL THEN 1 ELSE 0 END) AS trend_pv
FROM base b
LEFT JOIN home_flow_2604_cate_id_path_static_feat_15d_v1 sc
    ON b.item_id = sc.cate_id_path AND sc.dt = '20261013'
;
