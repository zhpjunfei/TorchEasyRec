SET odps.sql.type.system.odps2 = true
;

CREATE TABLE IF NOT EXISTS home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1_agg LIKE home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1
LIFECYCLE 1
;

INSERT OVERWRITE TABLE home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1_agg PARTITION(dt='${bdp.system.bizdate}')
SELECT  sq2.event_unix_time
        ,sq2.event
        ,sq2.item_id
        ,sq2.scene
        ,sq2.mmb_id
FROM    (
            SELECT  sq1.event_unix_time
                    ,sq1.event
                    ,sq1.item_id
                    ,sq1.scene
                    ,sq1.mmb_id
                    ,ROW_NUMBER() OVER(PARTITION BY sq1.mmb_id,sq1.event ORDER BY sq1.event_unix_time DESC) rnk
            FROM    (
                        SELECT  sq0.event_unix_time
                                ,sq0.event
                                ,sq0.item_id
                                ,sq0.scene
                                ,sq0.mmb_id
                                ,ROW_NUMBER() OVER(PARTITION BY sq0.mmb_id,sq0.item_id,sq0.event ORDER BY sq0.event_unix_time DESC) rk
                        FROM    (
                                    -- 从聚合表取180天分区，每天数据已去重+截断，数据量远小于源表
                                    SELECT  event_unix_time
                                            ,event
                                            ,item_id
                                            ,scene
                                            ,mmb_id
                                            ,dt
                                    FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1
                                    WHERE   dt <= '${bdp.system.bizdate}'
                                    AND     dt > TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -180,'dd'),'yyyymmdd')
                                ) sq0
                        INNER JOIN (
                                    -- 每个用户最近一次有行为的日期
                                    SELECT  mmb_id
                                            ,MAX(dt) AS user_last_dt
                                    FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1
                                    WHERE   dt <= '${bdp.system.bizdate}'
                                    AND     dt > TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -180,'dd'),'yyyymmdd')
                                    GROUP BY mmb_id
                                ) last_dt
                        ON      sq0.mmb_id = last_dt.mmb_id
                        WHERE   sq0.dt <= last_dt.user_last_dt
                        AND     sq0.dt > TO_CHAR(DATEADD(TO_DATE(last_dt.user_last_dt,'yyyymmdd'), -15,'dd'),'yyyymmdd')
                    ) sq1
            WHERE   sq1.rk = 1
        ) sq2
WHERE   sq2.rnk <= CASE WHEN sq2.event IN ('click') THEN 50 WHEN sq2.event IN ('conversion') THEN 20 WHEN sq2.event IN ('favorite') THEN 10 ELSE 50 END
;
