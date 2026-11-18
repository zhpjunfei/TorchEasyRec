-- ============================================================
-- v5 样本质量勘验 - 查询3: 关键特征表的覆盖情况
-- 目的：验证 JOIN 后特征是否有值（非NULL）
-- dt='20261013'
-- ============================================================

SELECT
    'total' AS metric, COUNT(1) AS val FROM home_flow_2606_ctrcvr_sorter_label_table_v5 WHERE dt = '20261013'
UNION ALL
-- sq33 用户基础信息覆盖
SELECT 'sq33_match' AS metric, COUNT(DISTINCT sq0.mmb_id) AS val
FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
INNER JOIN home_flow_2604_ads_usr_user_basic_info_preprocess_v1 sq33
    ON sq0.mmb_id = sq33.mmb_id AND sq33.dt = '20261013'
WHERE sq0.dt = '20261013'
UNION ALL
-- sq56 序列特征覆盖
SELECT 'sq56_match' AS metric, COUNT(DISTINCT sq0.mmb_id) AS val
FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
INNER JOIN home_flow_2606_mmb_id_all_seq_feat_v1 sq56
    ON sq0.mmb_id = sq56.mmb_id AND sq0.request_id = sq56.request_id AND sq56.dt = '20261013'
WHERE sq0.dt = '20261013'
UNION ALL
-- sq30 item实时统计覆盖（按item_id+request_id）
SELECT 'sq30_match' AS metric, COUNT(DISTINCT sq0.item_id || '|' || sq0.request_id) AS val
FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
INNER JOIN home_flow_2604_item_id_rt_statistic_feat_v1 sq30
    ON sq0.item_id = sq30.item_id AND sq0.request_id = sq30.request_id AND sq30.dt = '20261013'
WHERE sq0.dt = '20261013'
;
