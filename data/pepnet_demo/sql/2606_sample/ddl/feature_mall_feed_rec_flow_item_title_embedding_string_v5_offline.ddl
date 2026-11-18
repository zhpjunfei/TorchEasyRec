CREATE TABLE IF NOT EXISTS feature_mall_feed_rec_flow_item_title_embedding_string_v5_offline(
	item_id STRING,
	 title_vector STRING,
	 event_time BIGINT,
	 fs_write_time BIGINT
)
PARTITIONED BY (dt STRING,
	 hh STRING) STORED AS aliorc
TBLPROPERTIES ('columnar.nested.type'='true')
LIFECYCLE 90;
