-- ============================================================
-- 跨场景 item 对比分析
-- 目的：验证 trend 场景的点击 signal 是否与其他场景一致
-- dt='20261013'
-- ============================================================

SELECT
    item_id,
    -- home 场景
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN is_home_scene = 1 THEN is_click ELSE 0 END) AS home_clicks,
    SUM(CASE WHEN is_home_scene = 1 THEN is_conversion ELSE 0 END) AS home_convs,
    -- trend 场景
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend_pv,
    SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_click ELSE 0 END) AS trend_clicks,
    SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_conversion ELSE 0 END) AS trend_convs
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
GROUP BY item_id
HAVING SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) >= 50
   AND SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) >= 50
ORDER BY
    ABS(
        (SUM(CASE WHEN is_home_scene = 1 THEN is_click ELSE 0 END) * 100.0 /
         NULLIF(SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END), 0)) -
        (SUM(CASE WHEN is_trend_scene = 1 THEN is_trend_click ELSE 0 END) * 100.0 /
         NULLIF(SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END), 0))
    ) ASC
LIMIT 30
;
