CREATE TABLE IF NOT EXISTS home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5_pred_score_check(
	probs_ctr FLOAT,
	 probs_cvr FLOAT,
	 item_type ARRAY<STRING>,
	 site ARRAY<STRING>,
	 `__item_id__` STRING,
	 `__mmb_id__` STRING
)
PARTITIONED BY (dt STRING) STORED AS aliorc
TBLPROPERTIES ('columnar.nested.type'='true');
