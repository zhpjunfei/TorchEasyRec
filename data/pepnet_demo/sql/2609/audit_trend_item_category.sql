-- ============================================================
-- trend 场景 item 品类分布分析
-- 目的：验证 trend 点击是否集中在特定品类（可迁移性判断）
-- dt='20261013'
-- ============================================================

SELECT
    cate_id,
    COUNT(1) AS item_count,
    COUNT(DISTINCT mmb_id) AS user_count,
    SUM(is_trend_click) AS clicks,
    ROUND(SUM(is_trend_click) * 100.0 / COUNT(1), 2) AS ctr,
    SUM(is_trend_conversion) AS convs,
    ROUND(SUM(is_trend_conversion) * 100.0 / NULLIF(SUM(is_trend_click), 0), 2) AS cvr
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013' AND is_trend_scene = 1
GROUP BY cate_id
HAVING COUNT(1) >= 50
ORDER BY item_count DESC
LIMIT 20
;
