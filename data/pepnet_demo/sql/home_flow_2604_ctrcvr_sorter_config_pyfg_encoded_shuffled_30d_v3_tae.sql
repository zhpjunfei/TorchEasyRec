set odps.sql.type.system.odps2=true;


-- ==========================================
-- 1. 创建训练集表和验证集表 (仅首次运行需要)
-- ==========================================
-- CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_train
-- LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3 LIFECYCLE 30;

-- CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_val
-- LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3 LIFECYCLE 30;

-- 修改整表的生命周期为 30 天（影响所有现存和未来产出的分区）
-- ALTER TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_train SET LIFECYCLE 30;
-- ALTER TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_val SET LIFECYCLE 30;


-- ==========================================
-- 2. 每日调度执行：T-1 滑动窗口 + 最后一天验证
-- ==========================================
-- 时间线示例 (假设今日调度 bizdate = 20260527):
-- 总数据窗口: 过去 8 天 (20260520 ~ 20260527)
-- 训练集窗口: 前 7 天 (20260520 ~ 20260526)
-- 验证集窗口: 最后 1 天 (20260527) 采样 1%
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3


-- 【产出训练集】 (前 7 天)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_train PARTITION(dt='${bdp.system.bizdate}')
SELECT  `(dt)?+.+`
WHERE   dt > TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -8, 'dd'), 'yyyymmdd')
AND     dt <= '${bdp.system.bizdate}'
AND     (ARRAY_CONTAINS(f_req_page, '1w_tab_f_index_content') OR ARRAY_CONTAINS(f_req_page, '1zhekoutuijian'))
AND     dt <= TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -1, 'dd'), 'yyyymmdd')
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)


-- 【产出验证集】 (最后 1 天，采样 1%)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_val PARTITION(dt='${bdp.system.bizdate}')
SELECT  `(dt)?+.+`
WHERE   dt = '${bdp.system.bizdate}'
AND     (ARRAY_CONTAINS(f_req_page, '1w_tab_f_index_content') OR ARRAY_CONTAINS(f_req_page, '1zhekoutuijian'))
AND     RAND() < 0.01
;
