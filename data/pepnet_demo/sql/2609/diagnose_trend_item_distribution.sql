-- ============================================================
-- trend 场景 item 分布诊断
-- dt='20261013'
-- ============================================================

-- 1. item PV 分布（看有多少 item 有大样本）
SELECT
    CASE
        WHEN pv < 10 THEN '0-10'
        WHEN pv < 50 THEN '10-50'
        WHEN pv < 100 THEN '50-100'
        WHEN pv < 500 THEN '100-500'
        WHEN pv < 1000 THEN '500-1000'
        ELSE '1000+'
    END AS pv_range,
    COUNT(1) AS item_count,
    SUM(pv) AS total_pv,
    ROUND(SUM(pv) * 100.0 / SUM(SUM(pv)) OVER (), 2) AS pv_pct
FROM (
    SELECT item_id, COUNT(1) AS pv
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
        WHEN pv < 1000 THEN '500-1000'
        ELSE '1000+'
    END
ORDER BY MIN(pv)
;

-- 2. 高 PV item 的 CTR（只看样本量足够的 item）
SELECT
    item_id,
    COUNT(1) AS pv,
    SUM(is_click) AS clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr,
    SUM(is_conversion) AS convs
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_trend_scene = 1
GROUP BY item_id
HAVING COUNT(1) >= 100
ORDER BY clicks DESC
LIMIT 30
;

-- 3. trend 场景所有 item 的 CTR 分布
SELECT
    PERCENTILE(ctr, ARRAY[0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]) AS ctr_percentiles,
    AVG(ctr) AS avg_ctr,
    COUNT(1) AS total_items,
    SUM(CASE WHEN pv >= 100 THEN 1 ELSE 0 END) AS items_with_100_plus_pv
FROM (
    SELECT
        item_id,
        COUNT(1) AS pv,
        SUM(is_click) AS clicks,
        ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5
    WHERE dt = '20261013' AND is_trend_scene = 1
    GROUP BY item_id
) t
;

-- 4. trend vs home 相同 item 对比（只看双场景都有且 PV>=50 的）
WITH trend_items AS (
    SELECT item_id, COUNT(1) AS pv, SUM(is_click) AS clicks
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5
    WHERE dt = '20261013' AND is_trend_scene = 1
    GROUP BY item_id HAVING COUNT(1) >= 50
),
home_items AS (
    SELECT item_id, COUNT(1) AS pv, SUM(is_click) AS clicks
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5
    WHERE dt = '20261013' AND is_home_scene = 1
    GROUP BY item_id HAVING COUNT(1) >= 50
)
SELECT
    t.item_id,
    t.pv AS trend_pv, t.clicks AS trend_clicks,
    ROUND(t.clicks * 100.0 / t.pv, 2) AS trend_ctr,
    h.pv AS home_pv, h.clicks AS home_clicks,
    ROUND(h.clicks * 100.0 / h.pv, 2) AS home_ctr,
    ROUND((t.clicks * 100.0 / t.pv) - (h.clicks * 100.0 / h.pv), 2) AS ctr_diff
FROM trend_items t
INNER JOIN home_items h ON t.item_id = h.item_id
ORDER BY ctr_diff DESC
LIMIT 30
;
