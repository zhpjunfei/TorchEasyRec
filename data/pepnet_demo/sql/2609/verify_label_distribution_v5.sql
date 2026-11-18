-- ============================================================
-- 验证SQL: v5样本分布与标签质量检查
-- 分区: dt='20261013'
-- ============================================================

-- SQL1: 各场景点击分布
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
        ELSE 'UNKNOWN'
    END AS scene,
    COUNT(1) AS pv,
    SUM(CASE WHEN is_home_scene = 1 THEN is_click ELSE 0 END) AS home_clicks,
    SUM(CASE WHEN is_bijia_scene = 1 THEN is_bijia_click ELSE 0 END) AS bijia_clicks,
    SUM(CASE WHEN is_haojia_scene = 1 THEN is_haojia_click ELSE 0 END) AS haojia_clicks,
    SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_click ELSE 0 END) AS trend_clicks,
    ROUND(SUM(CASE WHEN is_home_scene = 1 THEN is_click ELSE 0 END) * 100.0 /
          NULLIF(SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END), 0), 2) AS home_ctr,
    ROUND(SUM(CASE WHEN is_bijia_scene = 1 THEN is_bijia_click ELSE 0 END) * 100.0 /
          NULLIF(SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END), 0), 2) AS bijia_ctr,
    ROUND(SUM(CASE WHEN is_haojia_scene = 1 THEN is_haojia_click ELSE 0 END) * 100.0 /
          NULLIF(SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END), 0), 2) AS haojia_ctr,
    ROUND(SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_click ELSE 0 END) * 100.0 /
          NULLIF(SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END), 0), 2) AS trend_ctr
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013'
GROUP BY scene
ORDER BY pv DESC;

-- SQL2: 各场景正样本率核实
SELECT
    'home' AS scene,
    COUNT(1) AS pv,
    SUM(is_click) AS clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013' AND is_home_scene = 1
UNION ALL
SELECT
    'bijia' AS scene,
    COUNT(1) AS pv,
    SUM(is_bijia_click) AS clicks,
    ROUND(SUM(is_bijia_click) * 100.0 / COUNT(1), 2) AS ctr
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013' AND is_bijia_scene = 1
UNION ALL
SELECT
    'haojia' AS scene,
    COUNT(1) AS pv,
    SUM(is_haojia_click) AS clicks,
    ROUND(SUM(is_haojia_click) * 100.0 / COUNT(1), 2) AS ctr
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013' AND is_haojia_scene = 1
UNION ALL
SELECT
    'trend' AS scene,
    COUNT(1) AS pv,
    SUM(is_trend_click) AS clicks,
    ROUND(SUM(is_trend_click) * 100.0 / COUNT(1), 2) AS ctr
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013' AND is_trend_scene = 1;

-- SQL3: 点击标签语义验证
SELECT
    'click_label_check' AS check_item,
    SUM(CASE WHEN is_home_scene = 1 AND (is_bijia_click = 1 OR is_haojia_click = 1 OR is_trend_click = 1) THEN 1 ELSE 0 END) AS home_with_other_clicks,
    SUM(CASE WHEN is_bijia_scene = 1 AND is_click = 1 THEN 1 ELSE 0 END) AS bijia_with_home_click,
    SUM(CASE WHEN is_haojia_scene = 1 AND is_click = 1 THEN 1 ELSE 0 END) AS haojia_with_home_click,
    SUM(CASE WHEN is_trend_scene = 1 AND is_click = 1 THEN 1 ELSE 0 END) AS trend_with_home_click
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013';

-- SQL4: 验证is_home_scene_click字段是否存在
SELECT
    COUNT_IF(is_home_scene_click IS NOT NULL) AS non_null_count,
    COUNT_IF(is_home_scene_click = 1) AS positive_count,
    COUNT(1) AS total_count
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013'
LIMIT 1;

-- SQL5: 各场景转化分布
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
        ELSE 'UNKNOWN'
    END AS scene,
    COUNT(1) AS pv,
    SUM(is_conversion) AS cvr_label_convs,
    SUM(CASE WHEN is_home_scene = 1 THEN is_conversion ELSE 0 END) AS home_convs,
    SUM(CASE WHEN is_bijia_scene = 1 THEN is_bijia_conversion ELSE 0 END) AS bijia_convs,
    SUM(CASE WHEN is_haojia_scene = 1 THEN is_haojia_conversion ELSE 0 END) AS haojia_convs,
    SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_conversion ELSE 0 END) AS trend_convs,
    ROUND(SUM(is_conversion) * 100.0 / COUNT(1), 2) AS cvr_rate,
    ROUND(SUM(CASE WHEN is_home_scene = 1 THEN is_conversion ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END), 0), 2) AS home_cvr,
    ROUND(SUM(CASE WHEN is_bijia_scene = 1 THEN is_bijia_conversion ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END), 0), 2) AS bijia_cvr,
    ROUND(SUM(CASE WHEN is_haojia_scene = 1 THEN is_haojia_conversion ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END), 0), 2) AS haojia_cvr,
    ROUND(SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_conversion ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END), 0), 2) AS trend_cvr
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013'
GROUP BY scene;

-- SQL6: 转化标签语义验证
SELECT
    'conversion_label_check' AS check_item,
    SUM(CASE WHEN is_home_scene = 1 AND (is_bijia_conversion = 1 OR is_haojia_conversion = 1 OR is_trend_conversion = 1) THEN 1 ELSE 0 END) AS home_with_other_convs,
    SUM(CASE WHEN is_bijia_scene = 1 AND is_conversion = 1 THEN 1 ELSE 0 END) AS bijia_with_home_conv,
    SUM(CASE WHEN is_haojia_scene = 1 AND is_conversion = 1 THEN 1 ELSE 0 END) AS haojia_with_home_conv,
    SUM(CASE WHEN is_trend_scene = 1 AND is_conversion = 1 THEN 1 ELSE 0 END) AS trend_with_home_conv
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261013';
