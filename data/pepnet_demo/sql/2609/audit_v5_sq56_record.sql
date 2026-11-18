-- ============================================================
-- v5 样本质量勘验 - 查询4: sq56 序列特征记录级覆盖
-- 目的：验证有多少样本记录真正匹配到序列特征
-- dt='20261013'
-- ============================================================

SELECT
    CASE WHEN sq56.mmb_id IS NOT NULL THEN 'matched' ELSE 'unmatched' END AS join_status,
    COUNT(1) AS total_pv,
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend_pv
FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
LEFT JOIN home_flow_2606_mmb_id_all_seq_feat_v1 sq56
    ON sq0.mmb_id = sq56.mmb_id
    AND sq0.request_id = sq56.request_id
    AND sq56.dt = '20261013'
WHERE sq0.dt = '20261013'
GROUP BY join_status
;
