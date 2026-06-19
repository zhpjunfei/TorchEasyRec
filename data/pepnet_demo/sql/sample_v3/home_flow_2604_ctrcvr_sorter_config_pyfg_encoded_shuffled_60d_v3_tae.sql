set odps.sql.type.system.odps2=true;


-- ==========================================
-- 1. 建 train/val 表 (仅首次运行需要)
-- ==========================================
CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_train LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3 LIFECYCLE 30;
CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3 LIFECYCLE 30;


-- ==========================================
-- 2. 从 shuffled 表按日期切分 train/val
--    子查询中 RAND() 一次求值，保证互斥
--    上游产出 ..._shuffled_60d_v3 的任务不动
-- ==========================================
FROM (
    SELECT  *, RAND() AS _rnd
    FROM    home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
    WHERE   dt = '${bdp.system.bizdate}'
)


-- 【训练集 99%】
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_train PARTITION(dt='${bdp.system.bizdate}')
SELECT  `(_rnd|dt)?+.+`
WHERE   _rnd < 0.99
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)


-- 【验证集 1%】 (~200W)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val PARTITION(dt='${bdp.system.bizdate}')
SELECT  `(_rnd|dt)?+.+`
WHERE   _rnd >= 0.99
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)
