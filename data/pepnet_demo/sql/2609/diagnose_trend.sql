-- ============================================================
-- trend 场景 CTR 异常诊断
-- dt='20261013'
-- ============================================================

-- 1. 按 item_id 统计（排除样本量过少的 item）
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
HAVING COUNT(1) >= 100  -- 只看样本量足够的 item
ORDER BY ctr DESC
LIMIT 30
;

-- 2. trend vs home 对比（相同 item_id）
SELECT
    CASE is_home_scene
        WHEN 1 THEN 'home'
        WHEN 4 THEN 'trend'
    END AS scene,
    item_id,
    COUNT(1) AS pv,
    SUM(is_click) AS clicks,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
  AND is_home_scene IN (1, 4)
  AND item_id IN (
    SELECT item_id FROM home_flow_2606_ctrcvr_sorter_label_table_v5
    WHERE dt = '20261013' AND is_trend_scene = 1
    GROUP BY item_id HAVING COUNT(1) >= 50
  )
GROUP BY is_home_scene, item_id
HAVING COUNT(1) >= 50
ORDER BY item_id, scene
LIMIT 50
;

-- 3. trend 场景的 request_id 分布（检查是否有重复）
SELECT
    request_id,
    COUNT(1) AS event_count,
    SUM(is_click) AS clicks,
    COUNT(DISTINCT item_id) AS unique_items
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_trend_scene = 1
GROUP BY request_id
HAVING COUNT(1) > 10  -- 只看有多条记录的 request
ORDER BY event_count DESC
LIMIT 20
;

-- 4. trend 场景的 mmb_id 行为分布
SELECT
    mmb_id,
    COUNT(1) AS total_events,
    SUM(is_click) AS clicks,
    COUNT(DISTINCT item_id) AS unique_items,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS ctr
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_trend_scene = 1
GROUP BY mmb_id
HAVING COUNT(1) >= 10
ORDER BY ctr DESC
LIMIT 20
;
