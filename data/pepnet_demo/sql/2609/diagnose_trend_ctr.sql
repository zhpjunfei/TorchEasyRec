-- ============================================================
-- trend CTR 异常诊断 - 排除小样本干扰
-- dt='20261013'
-- ============================================================

-- 1. 只看样本量 >= 100 的 item（排除噪声）
SELECT
    item_id,
    COUNT(1) AS pv,
    SUM(is_click) AS clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr,
    SUM(is_conversion) AS convs
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
  AND is_trend_scene = 1
GROUP BY item_id
HAVING COUNT(1) >= 100
ORDER BY ctr DESC
LIMIT 50
;

-- 2. trend 与 home 相同 item 的 CTR 对比
WITH trend_stats AS (
    SELECT item_id, COUNT(1) AS pv, SUM(is_click) AS clicks
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5
    WHERE dt = '20261013' AND is_trend_scene = 1
    GROUP BY item_id HAVING COUNT(1) >= 50
),
home_stats AS (
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
    ROUND(h.clicks * 100.0 / h.pv, 2) AS home_ctr
FROM trend_stats t
INNER JOIN home_stats h ON t.item_id = h.item_id
ORDER BY (t.clicks * 100.0 / t.pv) - (h.clicks * 100.0 / h.pv) DESC
LIMIT 30
;

-- 3. trend 场景的 click 事件分布（检查是否有异常）
SELECT
    item_id,
    COUNT(1) AS total_events,
    SUM(CASE WHEN event = 'exposure' THEN 1 ELSE 0 END) AS exposure_cnt,
    SUM(CASE WHEN event = 'click' THEN 1 ELSE 0 END) AS click_cnt,
    SUM(CASE WHEN event = 'conversion' THEN 1 ELSE 0 END) AS conversion_cnt
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_trend_scene = 1
GROUP BY item_id
HAVING COUNT(1) >= 50
ORDER BY click_cnt DESC
LIMIT 30
;
