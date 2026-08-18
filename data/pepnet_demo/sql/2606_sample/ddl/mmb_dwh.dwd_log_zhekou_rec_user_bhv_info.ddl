CREATE TABLE IF NOT EXISTS dwd_log_zhekou_rec_user_bhv_info(
	event_time BIGINT COMMENT '行为发生时间戳，秒级 unix timestamp，如 1622476800（需在当天时间分区内）',
	 event STRING COMMENT '行为类型（bhv_type），可自定义。内置类型如：exposure, click, stay, favorite, share, follow, comment, search, praise, auto_play, manual_play, video_over, cart, click_cart, check, order, conversion, dislike',
	 event_value DOUBLE COMMENT '行为值，如停留时长、购买件数、购买金额等',
	 item_id STRING COMMENT '内容 id（与行为相关的内容），如点击类行为必填，搜索类可为空',
	 scene STRING COMMENT '场景 ID，如 home_feed(首页推荐流)、hot_items(热卖栏目)、search(搜索场景)',
	 mmb_id STRING COMMENT '用户设备id',
	 query STRING COMMENT '搜索 query，仅在搜索行为或搜索结果页行为中传输',
	 request_id STRING COMMENT '推荐接口请求的 request_id，用于匹配行为与推荐请求',
	 page STRING COMMENT '页面 ID，如商品详情页填写主商品 ID',
	 source_page STRING COMMENT '上一页面，用于统计来源效果',
	 position STRING COMMENT '内容位置信息，表示在推荐列表中的序号（第几个位置）',
	 dislike_type STRING COMMENT '负反馈规则维度，如 author_id、cate_1、tags 等，用于不喜欢规则',
	 dislike_value STRING COMMENT '负反馈规则维度值，与 dislike_type 对应。可多值，用 $##$ 分隔',
	 trace_id STRING COMMENT 'trace_id，用于关联同一内容的曝光、点击、停留、转化等连续行为',
	 trans_data STRING COMMENT '推荐接口返回的 transData 字段，用于追踪推荐请求信息'
)
PARTITIONED BY (dt STRING COMMENT '日期分区') STORED AS aliorc
TBLPROPERTIES ('columnar.nested.type'='true',
	 'comment'='算法-折扣-物料/用户行为日志表')
LIFECYCLE 400;
