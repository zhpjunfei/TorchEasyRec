SET odps.sql.type.system.odps2 = true;

-- ==========================================
-- 1. 创建训练集和验证集表 (仅首次运行需要，后续可注释掉)
-- -- ==========================================
DROP TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_train;
DROP TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val;

CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_train LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3 LIFECYCLE 30;
CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3 LIFECYCLE 30;


FROM (
    SELECT  *, RAND() AS _rnd
    FROM    home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
    WHERE   dt = '${bdp.system.bizdate}'
)


-- 【训练集 95%】
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_train PARTITION(dt='${bdp.system.bizdate}')
SELECT  `(_rnd|dt)?+.+`
WHERE   _rnd < 0.95
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)


-- 【验证集 5%】
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val PARTITION(dt='${bdp.system.bizdate}')
SELECT  `(_rnd|dt)?+.+`
WHERE   _rnd >= 0.95
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)
