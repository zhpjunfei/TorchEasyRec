-- ============================================================
-- trend 场景点击用户 vs 非点击用户对比（跨场景行为）
-- dt='20261013'
-- ============================================================

SELECT
    CASE WHEN has_trend_click = 1 THEN 'clicked' ELSE 'not_clicked' END AS user_type,
    COUNT(DISTINCT mmb_id) AS unique_users,
    SUM(is_home_scene) AS home_items,
    SUM(is_bijia_scene) AS bijia_items,
    SUM(is_haojia_scene) AS haojia_items,
    SUM(is_trend_scene) AS trend_items,
    SUM(is_click) AS home_clicks,
    SUM(is_bijia_click) AS bijia_clicks,
    SUM(is_haojia_click) AS haojia_clicks,
    SUM(is_trend_click) AS trend_clicks,
    SUM(is_conversion) AS home_convs,
    SUM(is_bijia_conversion) AS bijia_convs,
    SUM(is_haojia_conversion) AS haojia_convs,
    SUM(is_trend_conversion) AS trend_convs
FROM (
    SELECT
        mmb_id,
        MAX(CASE WHEN is_trend_scene = 1 AND is_trend_click > 0 THEN 1 ELSE 0 END) AS has_trend_click,
        SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS is_home_scene,
        SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS is_bijia_scene,
        SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS is_haojia_scene,
        SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS is_trend_scene,
        SUM(CASE WHEN is_home_scene = 1 THEN is_click ELSE 0 END) AS is_click,
        SUM(CASE WHEN is_bijia_scene = 1 THEN is_bijia_click ELSE 0 END) AS is_bijia_click,
        SUM(CASE WHEN is_haojia_scene = 1 THEN is_haojia_click ELSE 0 END) AS is_haojia_click,
        SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_click ELSE 0 END) AS is_trend_click,
        SUM(CASE WHEN is_home_scene = 1 THEN is_conversion ELSE 0 END) AS is_conversion,
        SUM(CASE WHEN is_bijia_scene = 1 THEN is_bijia_conversion ELSE 0 END) AS is_bijia_conversion,
        SUM(CASE WHEN is_haojia_scene = 1 THEN is_haojia_conversion ELSE 0 END) AS is_haojia_conversion,
        SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_conversion ELSE 0 END) AS is_trend_conversion
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5
    WHERE dt = '20261013'
    GROUP BY mmb_id
) t
GROUP BY has_trend_click
;
