CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3(
	logits_ctr FLOAT,
	 logits_cvr FLOAT,
	 probs_ctr FLOAT,
	 probs_cvr FLOAT,
	 is_click BIGINT,
	 is_conversion BIGINT,
	 request_id STRING,
	 item_id ARRAY<STRING>,
	 mmb_id ARRAY<STRING>,
	 item_type ARRAY<STRING>
)
PARTITIONED BY (dt STRING) STORED AS aliorc
TBLPROPERTIES ('columnar.nested.type'='true');
