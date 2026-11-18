CREATE TABLE IF NOT EXISTS home_flow_2606_ctrcvr_sorter_label_table_v5(
	event_unix_time BIGINT,
	 item_id STRING,
	 scene STRING,
	 mmb_id STRING,
	 request_id STRING,
	 page STRING,
	 day_h BIGINT COMMENT 'event_time在当天的第几小时',
	 week_day BIGINT COMMENT 'event_time在一周得第几天',
	 is_click BIGINT,
	 is_conversion BIGINT,
	 is_favorite BIGINT,
	 is_like BIGINT,
	 is_bijia_click BIGINT,
	 is_bijia_conversion BIGINT,
	 is_haojia_click BIGINT,
	 is_haojia_conversion BIGINT,
	 is_trend_click BIGINT,
	 is_trend_conversion BIGINT,
	 is_home_scene BIGINT,
	 is_bijia_scene BIGINT,
	 is_haojia_scene BIGINT,
	 is_trend_scene BIGINT
)
PARTITIONED BY (dt STRING) STORED AS aliorc
TBLPROPERTIES ('columnar.nested.type'='true')
LIFECYCLE 90;
