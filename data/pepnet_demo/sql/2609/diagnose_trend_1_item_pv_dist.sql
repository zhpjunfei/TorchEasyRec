-- ============================================================
-- trend 场景 item PV 分布诊断
-- 目的：验证 CTR=49.29% 是否由少数高频 item 拉动
-- dt='20261013'
-- ============================================================

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
