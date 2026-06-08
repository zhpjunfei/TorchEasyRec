set odps.sql.type.system.odps2=true;


-- ==========================================
-- 1. 创建训练集表和验证集表 (仅首次运行需要)
-- ==========================================
-- DROP TABLE IF EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight;
-- CREATE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3 LIFECYCLE 1;
-- ALTER TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight ADD COLUMNS (search_weight DOUBLE);


FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3


-- 【产出训练集】 (前 7 天)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight PARTITION(dt='${bdp.system.bizdate}')
SELECT
`(dt)?+.+`
,CASE
  WHEN ARRAY_CONTAINS(f_req_page, 'search_price')
   AND NOT ARRAY_CONTAINS(f_req_page, '1w_tab_f_index_content')
   AND NOT ARRAY_CONTAINS(f_req_page, '1zhekoutuijian')
  THEN 0.3
  ELSE 1.0
END AS search_weight
WHERE   dt > TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -7, 'dd'), 'yyyymmdd')
AND     dt <= '${bdp.system.bizdate}'
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)
