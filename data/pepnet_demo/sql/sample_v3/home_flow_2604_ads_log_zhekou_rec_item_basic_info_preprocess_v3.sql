set odps.sql.type.system.odps2=true;
-- DROP TABLE home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3;
CREATE TABLE IF NOT EXISTS home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3
(
    item_id string
    ,item_type string
    ,cate string
    ,cate_id_path string
    ,copyright_end bigint
    ,create_time bigint
    ,current_price double
    ,keyword string
    ,pub_time bigint
    ,tags string
    ,title string
    ,related_goods_ids string
    ,brand string
    ,core_entity string
    ,dianpufensi string
    ,dianpupingfen string
    ,discount_intensity string
    ,discount_type string
    ,first_cate_id bigint
    ,second_cate_id bigint
    ,third_cate_id bigint
    ,gender_score bigint
    ,level string
    ,modifiers string
    ,pinpaidengji string
    ,price_tag string
    ,promotion_channel string
    ,publish_user string
    ,shop_id string
    ,site string
    ,spu_id string
    ,sqk_id string
    ,sub_title string
    ,username string
    ,title_vector string
)
PARTITIONED BY
(
    dt string
)
LIFECYCLE 90
;
INSERT OVERWRITE TABLE home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3 PARTITION(dt='${bdp.system.bizdate}')
SELECT  a.item_id
        ,REGEXP_REPLACE(a.item_type,':|,|;','_') item_type
        ,REGEXP_REPLACE(a.cate,':|,|;','_') cate
        ,REGEXP_REPLACE(a.cate_id_path,':|,|;','_') cate_id_path
        ,a.copyright_end
        ,a.create_time
        ,a.current_price
        ,REGEXP_REPLACE(
            REGEXP_REPLACE(a.keyword,'#',CHR(29))
            ,':|,|;'
            ,'_'
        ) keyword
        ,a.pub_time
        ,REGEXP_REPLACE(REGEXP_REPLACE(a.tags,'#',CHR(29)),':|,|;','_') tags
        ,a.title
        ,REGEXP_REPLACE(a.related_goods_ids,':|,|;','_') related_goods_ids
        ,REGEXP_REPLACE(a.brand,':|,|;','_') brand
        ,REGEXP_REPLACE(a.core_entity,':|,|;','_') core_entity
        ,REGEXP_REPLACE(a.dianpufensi,':|,|;','_') dianpufensi
        ,REGEXP_REPLACE(a.dianpupingfen,':|,|;','_') dianpupingfen
        ,REGEXP_REPLACE(a.discount_intensity,':|,|;','_') discount_intensity
        ,REGEXP_REPLACE(
            REGEXP_REPLACE(a.discount_type,'#',CHR(29))
            ,':|,|;'
            ,'_'
        ) discount_type
        ,a.first_cate_id
        ,a.second_cate_id
        ,a.third_cate_id
        ,a.gender_score
        ,REGEXP_REPLACE(a.level,':|,|;','_') level
        ,REGEXP_REPLACE(
            REGEXP_REPLACE(a.modifiers,'#',CHR(29))
            ,':|,|;'
            ,'_'
        ) modifiers
        ,REGEXP_REPLACE(a.pinpaidengji,':|,|;','_') pinpaidengji
        ,REGEXP_REPLACE(a.price_tag,':|,|;','_') price_tag
        ,REGEXP_REPLACE(a.promotion_channel,':|,|;','_') promotion_channel
        ,REGEXP_REPLACE(a.publish_user,':|,|;','_') publish_user
        ,REGEXP_REPLACE(a.shop_id,':|,|;','_') shop_id
        ,REGEXP_REPLACE(a.site,':|,|;','_') site
        ,REGEXP_REPLACE(a.spu_id,':|,|;','_') spu_id
        ,REGEXP_REPLACE(a.sqk_id,':|,|;','_') sqk_id
        ,a.sub_title
        ,REGEXP_REPLACE(a.username,':|,|;','_') username

        -- 核心转换逻辑：将 ARRAY<DOUBLE> 转为逗号分隔的 STRING
        -- ,CONCAT_WS(',', CAST(b.title_vector AS ARRAY<STRING>)) AS title_vector
        ,CONCAT_WS(',', TRANSFORM(b.title_vector, x -> CAST(ROUND(x, 7) AS STRING))) AS title_vector

FROM    mmb_dwh.ads_log_zhekou_rec_item_basic_info a
LEFT JOIN (
    SELECT  item_id, title_vector
    FROM    (
        SELECT  item_id, title_vector
                ,ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY fs_write_time DESC) AS write_order
        FROM    feature_mall_feed_rec_flow_item_title_embedding_v5_offline
        WHERE   dt >= '20260604'
        AND     dt <= '${bdp.system.bizdate}'
        AND     title_vector IS NOT NULL
    ) t
    WHERE   write_order = 1 -- 取每个 item_id 最新的一条 embedding
) b
ON      a.item_id = b.item_id
WHERE   a.dt = '${bdp.system.bizdate}'
;

ALTER TABLE home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3 ADD IF NOT EXISTS PARTITION(dt='${bdp.system.bizdate}.done')
;
