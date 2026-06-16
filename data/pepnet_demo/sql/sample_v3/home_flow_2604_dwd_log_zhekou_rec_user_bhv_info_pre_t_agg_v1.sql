set odps.sql.type.system.odps2=true;
CREATE TABLE IF NOT EXISTS home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1
(
    event_unix_time bigint
    ,event string
    ,item_id string
    ,scene string
    ,mmb_id string
)
PARTITIONED BY
(
    dt string
)
LIFECYCLE 90
;
INSERT OVERWRITE TABLE home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1 PARTITION(dt='${bdp.system.bizdate}')
SELECT  sq1.event_unix_time
        ,sq1.event
        ,sq1.item_id
        ,sq1.scene
        ,sq1.mmb_id
FROM    (
            SELECT  sq0.`(rk)?+.+`
                    ,ROW_NUMBER() OVER(PARTITION BY mmb_id,event ORDER BY event_unix_time DESC) rnk
            FROM    (
                        SELECT  *
                                ,ROW_NUMBER() OVER(PARTITION BY mmb_id,item_id,event ORDER BY event_unix_time DESC) rk
                        FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
                        WHERE   dt <= '${bdp.system.bizdate}'
                        and     dt > TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), - 15,'dd'),'yyyymmdd')
                        and     event IN ('click','conversion','favorite')
                    ) sq0
            WHERE   sq0.rk = 1
        ) sq1
WHERE   sq1.rnk <= CASE WHEN sq1.event IN ('click') THEN 50 WHEN sq1.event IN ('conversion') THEN 20 WHEN sq1.event IN ('favorite') THEN 10 ELSE 50 END
;
