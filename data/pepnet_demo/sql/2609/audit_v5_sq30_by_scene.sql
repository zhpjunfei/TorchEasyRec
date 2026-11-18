-- ============================================================
-- v5 样本质量勘验 - 查询5: sq30 缺失按场景分布
-- 目的：确认 item_rt 缺失是否集中在某个场景
-- dt='20261013'
-- ============================================================

SELECT
    CASE WHEN sq30.item_id IS NOT NULL THEN 'matched' ELSE 'unmatched' END AS join_status,
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend_pv
FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
LEFT JOIN home_flow_2604_item_id_rt_statistic_feat_v1 sq30
    ON sq0.item_id = sq30.item_id
    AND sq0.request_id = sq30.request_id
    AND sq30.dt = '20261013'
WHERE sq0.dt = '20261013'
GROUP BY join_status
;
