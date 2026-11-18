-- ============================================================
-- trend 场景 item 分布特征
-- 目的：验证 trend 点击是否集中在特定 item（可迁移性判断）
-- dt='20261013'
-- ============================================================

-- 1. 按 item 统计曝光、点击、转化分布
SELECT
    CASE
        WHEN pv < 10 THEN '0-10'
        WHEN pv < 50 THEN '10-50'
        WHEN pv < 100 THEN '50-100'
        WHEN pv < 500 THEN '100-500'
        ELSE '500+'
    END AS pv_range,
    COUNT(1) AS item_count,
    SUM(pv) AS total_pv,
    SUM(clicks) AS total_clicks,
    SUM(convs) AS total_convs,
    ROUND(SUM(clicks) * 100.0 / SUM(pv), 2) AS ctr,
    ROUND(SUM(convs) * 100.0 / NULLIF(SUM(clicks), 0), 2) AS cvr
FROM (
    SELECT
        item_id,
        COUNT(1) AS pv,
        SUM(is_trend_click) AS clicks,
        SUM(is_trend_conversion) AS convs
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5
    WHERE dt = '20261013' AND is_trend_scene = 1
    GROUP BY item_id
) t
GROUP BY
    CASE
        WHEN pv < 10 THEN '0-10'
        WHEN pv < 50 THEN '10-50'
        WHEN pv < 100 THEN '50-100'
        WHEN pv < 500 THEN '100-500'
        ELSE '500+'
    END
;

-- 2. 高 PV item 的转化质量（只分析样本量足够的 item）
SELECT
    item_id,
    COUNT(1) AS pv,
    SUM(is_trend_click) AS clicks,
    ROUND(SUM(is_trend_click) * 100.0 / COUNT(1), 2) AS ctr,
    SUM(is_trend_conversion) AS convs,
    ROUND(SUM(is_trend_conversion) * 100.0 / NULLIF(SUM(is_trend_click), 0), 2) AS cvr
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_trend_scene = 1
GROUP BY item_id
HAVING COUNT(1) >= 100
ORDER BY clicks DESC
LIMIT 20
;
