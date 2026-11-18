-- ============================================================
-- v5 样本质量勘验 - 查询1: 各场景样本量与特征覆盖
-- 目的：验证不同场景的 JOIN 是否有遗漏或膨胀
-- dt='20261013'
-- ============================================================

-- 先统计 label 表的原始样本量
SELECT
    'label_table' AS source,
    COUNT(1) AS total_pv,
    SUM(is_home_scene) AS home_pv,
    SUM(is_bijia_scene) AS bijia_pv,
    SUM(is_haojia_scene) AS haojia_pv,
    SUM(is_trend_scene) AS trend_pv
FROM home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt = '20261013'
;
