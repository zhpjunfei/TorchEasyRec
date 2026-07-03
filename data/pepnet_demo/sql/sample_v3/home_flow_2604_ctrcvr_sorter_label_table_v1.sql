set odps.sql.type.system.odps2=true;
CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_label_table_v1
(
    event_unix_time bigint
    ,__item_id__ string
    ,item_id string
    ,scene string
    ,__mmb_id__ string
    ,mmb_id string
    ,request_id string
    ,page string
    ,day_h bigint COMMENT 'event_time在当天的第几小时'
    ,week_day bigint COMMENT 'event_time在一周得第几天'
    ,is_click BIGINT
    ,is_conversion BIGINT
)
PARTITIONED BY
(
    dt string
)
LIFECYCLE 90
;

WITH ctr_label AS
(
    SELECT  MIN(event_unix_time) AS event_unix_time
            ,item_id
            ,item_id AS __item_id__
            ,mmb_id
            ,mmb_id AS __mmb_id__
            ,MAX(page) AS page
            ,MAX(day_h) AS day_h
            ,MAX(week_day) AS week_day
            ,MAX(IF(event = 'exposure',1,0)) AS is_exposure
            ,MAX(IF(event = 'click',1,0)) AS is_click
            ,MAX(IF(event = 'conversion',1,0)) AS is_conversion
    FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE   dt = '${bdp.system.bizdate}'
    GROUP BY item_id
             ,mmb_id
)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_label_table_v1 PARTITION (dt = '${bdp.system.bizdate}')
SELECT  sq0.event_unix_time AS event_unix_time
        ,sq0.item_id AS item_id
        ,sq0.__item_id__ AS __item_id__
        ,sq1.scene AS scene
        ,sq0.mmb_id AS mmb_id
        ,sq0.__mmb_id__ AS __mmb_id__
        ,sq1.request_id AS request_id
        ,sq0.page AS page
        ,sq0.day_h AS day_h
        ,sq0.week_day AS week_day
        ,sq0.is_click AS is_click
        ,sq0.is_conversion AS is_conversion
FROM    (
            SELECT  *
                    ,SUM(is_click) OVER (PARTITION BY mmb_id ORDER BY event_unix_time ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING ) AS click_cnt
                    ,SUM(is_click) OVER (PARTITION BY mmb_id ) AS click_num
            FROM    ctr_label
            WHERE   is_exposure > 0
            AND     is_click >= is_conversion
        ) sq0
LEFT JOIN   (
                SELECT  mmb_id
                        ,item_id
                        ,request_id
                        ,scene
                        ,ROW_NUMBER() OVER (PARTITION BY mmb_id,item_id ORDER BY event_unix_time ) AS rnk
                FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
                WHERE   dt = '${bdp.system.bizdate}'
                AND     event = 'exposure'
                AND     request_id IS NOT NULL
            ) sq1
ON      sq0.mmb_id = sq1.mmb_id
AND     sq0.item_id = sq1.item_id
WHERE   sq0.click_cnt > 0
AND     sq0.click_num < 100
AND     sq1.rnk = 1 and sq1.request_id is not NULL
;
