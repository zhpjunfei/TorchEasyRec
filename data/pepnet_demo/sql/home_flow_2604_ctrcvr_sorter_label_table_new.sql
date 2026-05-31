set odps.sql.type.system.odps2=true;

-- 样本表：仅保留主键 + 标签 + 必要归因字段
CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_label_table_v2
(
    request_id      STRING COMMENT '请求ID'
    ,mmb_id         STRING COMMENT '用户ID'
    ,item_id        STRING COMMENT '商品ID'
    ,scene          STRING COMMENT '场景标识'
    ,exposure_time  BIGINT COMMENT '曝光时间戳'
    ,is_click       BIGINT COMMENT '是否点击(0/1)'
    ,is_conversion  BIGINT COMMENT '是否转化(0/1)'
)
PARTITIONED BY (dt STRING)
LIFECYCLE 90;

INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_label_table_v2 PARTITION(dt='${bdp.system.bizdate}')
SELECT
    exp.request_id
    ,exp.mmb_id
    ,exp.item_id
    ,exp.scene
    ,exp.event_unix_time AS exposure_time
    -- 点击归因：曝光后 30 分钟内同用户同商品的点击
    ,IF(cli.event_unix_time IS NOT NULL, 1, 0) AS is_click
    -- 转化归因：点击后 24 小时内同用户同商品的转化 (ESMM范式)
    ,IF(cvr.event_unix_time IS NOT NULL, 1, 0) AS is_conversion
FROM (
    -- 1. 曝光明细（基准表）
    SELECT request_id, mmb_id, item_id, scene, event_unix_time
    FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE dt = '${bdp.system.bizdate}'
      AND event = 'exposure'
      AND request_id IS NOT NULL
      AND mmb_id IS NOT NULL AND item_id IS NOT NULL
) exp
LEFT JOIN (
    -- 2. 点击明细
    SELECT mmb_id, item_id, MIN(event_unix_time) AS event_unix_time
    FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE dt = '${bdp.system.bizdate}'
      AND event = 'click'
    GROUP BY mmb_id, item_id
) cli
  ON exp.mmb_id = cli.mmb_id
 AND exp.item_id = cli.item_id
 AND cli.event_unix_time BETWEEN exp.event_unix_time AND exp.event_unix_time + 1800  -- 30分钟归因窗口
LEFT JOIN (
    -- 3. 转化明细
    SELECT mmb_id, item_id, MIN(event_unix_time) AS event_unix_time
    FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE dt >= TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -1, 'dd'), 'yyyymmdd')
      AND dt <= '${bdp.system.bizdate}'
      AND event = 'conversion'
    GROUP BY mmb_id, item_id
) cvr
  ON cli.mmb_id = cvr.mmb_id
 AND cli.item_id = cvr.item_id
 AND cvr.event_unix_time BETWEEN cli.event_unix_time AND cli.event_unix_time + 86400  -- 24小时转化窗口
WHERE
    -- 防刷/异常过滤（替代原 click_num < 100）
    exp.mmb_id NOT IN (SELECT mmb_id FROM home_flow_2604_blacklist_users WHERE dt = '${bdp.system.bizdate}')
;
