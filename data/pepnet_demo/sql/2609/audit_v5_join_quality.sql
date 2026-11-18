-- ============================================================
-- v5 样本质量勘验 - 查询2: 序列特征表 sq56 的 JOIN 覆盖
-- 目的：验证核心序列特征表的匹配率
-- dt='20261013'
-- ============================================================

SELECT
    CASE WHEN sq56_cnt > 0 THEN 'matched' ELSE 'unmatched' END AS join_status,
    COUNT(1) AS total_pv,
    SUM(CASE WHEN is_home_scene = 1 THEN 1 ELSE 0 END) AS home_pv,
    SUM(CASE WHEN is_bijia_scene = 1 THEN 1 ELSE 0 END) AS bijia_pv,
    SUM(CASE WHEN is_haojia_scene = 1 THEN 1 ELSE 0 END) AS haojia_pv,
    SUM(CASE WHEN is_trend_scene = 1 THEN 1 ELSE 0 END) AS trend_pv
FROM (
    SELECT sq0.mmb_id, sq0.request_id, sq0.is_home_scene, sq0.is_bijia_scene, sq0.is_haojia_scene, sq0.is_trend_scene
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
    WHERE sq0.dt = '20261013'
) t
LEFT JOIN (
    SELECT mmb_id, request_id, COUNT(1) AS sq56_cnt
    FROM home_flow_2606_mmb_id_all_seq_feat_v1
    WHERE dt = '20261013'
    GROUP BY mmb_id, request_id
) sq56
ON t.mmb_id = sq56.mmb_id AND t.request_id = sq56.request_id
GROUP BY join_status
;
