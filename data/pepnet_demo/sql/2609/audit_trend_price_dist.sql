-- ============================================================
-- trend 场景价格带分布分析
-- 目的：验证 trend 点击用户的价格偏好是否可迁移到 home
-- dt='20261013'
-- ============================================================

SELECT
    CASE
        WHEN price < 50 THEN '0-50'
        WHEN price < 100 THEN '50-100'
        WHEN price < 200 THEN '100-200'
        WHEN price < 500 THEN '200-500'
        WHEN price < 1000 THEN '500-1000'
        ELSE '1000+'
    END AS price_range,
    COUNT(1) AS item_count,
    SUM(is_trend_click) AS clicks,
    ROUND(SUM(is_trend_click) * 100.0 / COUNT(1), 2) AS ctr,
    SUM(is_trend_conversion) AS convs,
    ROUND(SUM(is_trend_conversion) * 100.0 / NULLIF(SUM(is_trend_click), 0), 2) AS cvr
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_trend_scene = 1
GROUP BY
    CASE
        WHEN price < 50 THEN '0-50'
        WHEN price < 100 THEN '50-100'
        WHEN price < 200 THEN '100-200'
        WHEN price < 500 THEN '200-500'
        WHEN price < 1000 THEN '500-1000'
        ELSE '1000+'
    END
;
