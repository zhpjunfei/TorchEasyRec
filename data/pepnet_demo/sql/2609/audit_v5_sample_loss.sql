-- ============================================================
-- v5 样本质量勘验 - 查询3: 关键 JOIN 表的覆盖情况
-- 目的：验证主要 JOIN 表是否有匹配
-- dt='20261013'
-- ============================================================

-- 3.1: 用户基础信息 sq33 覆盖
SELECT 'sq33_user_basic' AS join_table, COUNT(DISTINCT mmb_id) AS matched_users
FROM home_flow_2604_ads_usr_user_basic_info_preprocess_v1
WHERE dt = '20261013'
INTERSECT
SELECT 'sq33_user_basic' AS join_table, COUNT(DISTINCT mmb_id) AS matched_users
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
;

-- 3.2: 序列特征 sq56 覆盖
SELECT 'sq56_seq_feat' AS join_table, COUNT(DISTINCT mmb_id) AS matched_users
FROM home_flow_2606_mmb_id_all_seq_feat_v1
WHERE dt = '20261013'
INTERSECT
SELECT 'sq56_seq_feat' AS join_table, COUNT(DISTINCT mmb_id) AS matched_users
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
;

-- 3.3: item 实时统计 sq30 覆盖（按 item_id + request_id）
SELECT 'sq30_item_rt' AS join_table, COUNT(1) AS matched_records
FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
INNER JOIN home_flow_2604_item_id_rt_statistic_feat_v1 sq30
    ON sq0.item_id = sq30.item_id AND sq0.request_id = sq30.request_id
WHERE sq0.dt = '20261013' AND sq30.dt = '20261013'
;
able_v5 sq0
    LEFT JOIN home_flow_2604_ads_usr_user_basic_info_preprocess_v1 sq33
        ON sq0.mmb_id = sq33.mmb_id AND sq33.dt = '20261013'
    WHERE sq0.dt = '20261013'

    UNION ALL

    -- after sq56 (sequence features)
    SELECT sq0.*, sq33.mmb_id AS sq33_mmb_id, sq30.item_id AS sq30_item_id, sq54.mmb_id AS sq54_mmb_id, sq56.mmb_id AS sq56_mmb_id
    FROM home_flow_2606_ctrcvr_sorter_label_table_v5 sq0
    LEFT JOIN home_flow_2604_ads_usr_user_basic_info_preprocess_v1 sq33
        ON sq0.mmb_id = sq33.mmb_id AND sq33.dt = '20261013'
    LEFT JOIN home_flow_2604_item_id_rt_statistic_feat_v1 sq30
        ON sq0.item_id = sq30.item_id AND sq0.request_id = sq30.request_id AND sq30.dt = '20261013'
    LEFT JOIN home_flow_2604_mmb_id_rt_statistic_feat_v1 sq54
        ON sq0.mmb_id = sq54.mmb_id AND sq0.request_id = sq54.request_id AND sq54.dt = '20261013'
    LEFT JOIN home_flow_2606_mmb_id_all_seq_feat_v1 sq56
        ON sq0.mmb_id = sq56.mmb_id AND sq0.request_id = sq56.request_id AND sq56.dt = '20261013'
    WHERE sq0.dt = '20261013'
) t
GROUP BY CASE join_stage
    WHEN 'base' THEN 'base_label'
    WHEN 'after_sq33' THEN 'after_user_basic'
    WHEN 'after_sq30' THEN 'after_item_rt'
    WHEN 'after_sq54' THEN 'after_mmb_rt'
    WHEN 'after_sq56' THEN 'after_seq_feat'
    WHEN 'after_all' THEN 'after_all_joins'
END
;
