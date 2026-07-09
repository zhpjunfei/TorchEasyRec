set odps.sql.type.system.odps2=true;


-- ==========================================
-- 1. 创建训练集表 (仅首次运行需要)
-- ==========================================
-- DROP TABLE IF EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_upsample;
-- CREATE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_upsample
-- LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3 LIFECYCLE 1;


-- ==========================================
-- 2. 每日调度执行：基于 v3 产出 upsample 训练集
--    - 老帖子：保留
--    - 新帖子：保留
--    - 新帖子正样本：翻倍
-- ==========================================
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_upsample PARTITION(dt='${bdp.system.bizdate}')
SELECT `(dt)?+.+` FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '${bdp.system.bizdate}' AND isnewitem_fg[0] = '0'
UNION ALL
SELECT `(dt)?+.+` FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '${bdp.system.bizdate}' AND isnewitem_fg[0] = '1'
UNION ALL
SELECT `(dt)?+.+` FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '${bdp.system.bizdate}' AND isnewitem_fg[0] = '1' AND (is_click = 1 OR is_conversion = 1)
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT);
