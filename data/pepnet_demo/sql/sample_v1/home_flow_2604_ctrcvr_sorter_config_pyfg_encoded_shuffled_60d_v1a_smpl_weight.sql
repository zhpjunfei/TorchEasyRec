set odps.sql.type.system.odps2=true;


-- ==========================================
-- 1. 创建训练集表和验证集表 (仅首次运行需要)
-- ==========================================
-- DROP TABLE IF EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1a_smpl_weight;
-- CREATE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1a_smpl_weight
-- LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v1c LIFECYCLE 2;
-- ALTER TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1a_smpl_weight
-- ADD COLUMNS (search_weight DOUBLE);


FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v1c


-- 【产出训练集】 (前 60 天)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1a_smpl_weight PARTITION(dt='${bdp.system.bizdate}')
SELECT
`(dt)?+.+`
,CASE
  WHEN ARRAY_CONTAINS(f_req_page, 'search_price')
   AND NOT ARRAY_CONTAINS(f_req_page, '1w_tab_f_index_content')
   AND NOT ARRAY_CONTAINS(f_req_page, '1zhekoutuijian')
  THEN 0.3
  ELSE 1.0
END AS search_weight
WHERE   dt > TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -60, 'dd'), 'yyyymmdd')
AND     dt <= '${bdp.system.bizdate}'
-- AND     (ARRAY_CONTAINS(f_req_page, '1w_tab_f_index_content') OR ARRAY_CONTAINS(f_req_page, '1zhekoutuijian'))
DISTRIBUTE BY RAND()
SORT BY RAND()
