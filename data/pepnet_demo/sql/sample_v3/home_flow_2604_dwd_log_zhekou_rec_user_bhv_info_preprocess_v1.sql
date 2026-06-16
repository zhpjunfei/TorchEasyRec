set odps.sql.type.system.odps2=true;
CREATE TABLE IF NOT EXISTS home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
(
    event_unix_time bigint
    ,event string
    ,event_value double
    ,item_id string
    ,scene string
    ,mmb_id string
    ,request_id string
    ,page string
    ,day_h bigint COMMENT 'event_time在当天的第几小时'
    ,week_day bigint COMMENT 'event_time在一周得第几天'
)
PARTITIONED BY
(
    dt string
)
LIFECYCLE 90
;
INSERT OVERWRITE TABLE home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1 PARTITION(dt='${bdp.system.bizdate}')
SELECT  event_time event_unix_time
        ,event
        ,event_value
        ,item_id
        ,REPLACE(scene,':','_') scene
        ,mmb_id
        ,request_id
        ,REPLACE(page,':','_') page
        ,DATEPART(FROM_UNIXTIME(event_time),'hh') day_h
        ,WEEKDAY(FROM_UNIXTIME(event_time)) week_day
FROM    mmb_dwh.dwd_log_zhekou_rec_user_bhv_info
WHERE   dt = '${bdp.system.bizdate}'
;
