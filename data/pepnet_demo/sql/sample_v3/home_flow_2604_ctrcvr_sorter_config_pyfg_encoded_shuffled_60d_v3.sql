set odps.sql.type.system.odps2=true;


-- ==========================================
-- 1. 创建训练集表和验证集表 (仅首次运行需要)
-- ==========================================
DROP TABLE IF EXISTS home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3;
CREATE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
LIKE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3 LIFECYCLE 1;
ALTER TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
ADD COLUMNS (
  search_weight DOUBLE,
  fresh_weight DOUBLE,
  fresh_weight_binary_2x_5h DOUBLE,
  fresh_weight_binary_3x_2h DOUBLE,
  fresh_weight_binary_5x_1h DOUBLE,
  fresh_weight_tiered_v2 DOUBLE,
  phour_x_cate STRING,
  phour_x_price STRING,
  phour_x_brand STRING,
  isNewItem_fg ARRAY<STRING>
);





-- ==========================================
-- 2. 每日调度执行：T-1 滑动窗口 + OOT 验证
-- ==========================================
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3


-- 【产出训练集】 (前 60 天)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3 PARTITION(dt='${bdp.system.bizdate}')
SELECT
`(dt)?+.+`
,CASE
  WHEN ARRAY_CONTAINS(f_req_page, 'search_price')
   AND NOT ARRAY_CONTAINS(f_req_page, '1w_tab_f_index_content')
   AND NOT ARRAY_CONTAINS(f_req_page, '1zhekoutuijian')
  THEN 0.3
  ELSE 1.0
END AS search_weight
,CASE
  WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 1.0 THEN 3.0
  WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 5.0 THEN 1.5
  ELSE 1.0
END AS fresh_weight
,CASE
  WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 5.0 THEN 2.0
  ELSE 1.0
END AS fresh_weight_binary_2x_5h
,CASE
  WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 2.0 THEN 3.0
  ELSE 1.0
END AS fresh_weight_binary_3x_2h
,CASE
  WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 1.0 THEN 5.0
  ELSE 1.0
END AS fresh_weight_binary_5x_1h
,CASE
  WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 0.5 THEN 4.0
  WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 2.0 THEN 2.0
  ELSE 1.0
END AS fresh_weight_tiered_v2
,CONCAT(
  CASE
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 1.0 THEN '0'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 6.0 THEN '1'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 24.0 THEN '2'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 72.0 THEN '3'
    ELSE '4'
  END, '_', CONCAT_WS(',', cate_id_path)
) AS phour_x_cate
,CONCAT(
  CASE
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 1.0 THEN '0'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 6.0 THEN '1'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 24.0 THEN '2'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 72.0 THEN '3'
    ELSE '4'
  END, '_', CONCAT_WS(',', price_tag)
) AS phour_x_price
,CONCAT(
  CASE
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 1.0 THEN '0'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 6.0 THEN '1'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 24.0 THEN '2'
    WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 72.0 THEN '3'
    ELSE '4'
  END, '_', CONCAT_WS(',', brand)
) AS phour_x_brand
,ARRAY(CASE
  WHEN pub_hours IS NOT NULL AND pub_hours >= 0 AND pub_hours < 5.0 THEN '1'
  ELSE '0'
END) AS isNewItem_fg
WHERE   dt > TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -60, 'dd'), 'yyyymmdd')
AND     dt <= '${bdp.system.bizdate}'
-- AND     (ARRAY_CONTAINS(f_req_page, '1w_tab_f_index_content') OR ARRAY_CONTAINS(f_req_page, '1zhekoutuijian'))
DISTRIBUTE BY CAST(RAND() * 10000 AS BIGINT)
