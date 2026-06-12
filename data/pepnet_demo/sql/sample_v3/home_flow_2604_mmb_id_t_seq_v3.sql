set odps.sql.type.system.odps2=true;
CREATE TABLE IF NOT EXISTS home_flow_2604_behavior_wide_for_t_seq_v3
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
INSERT OVERWRITE TABLE home_flow_2604_behavior_wide_for_t_seq_v3 PARTITION(dt='${bdp.system.bizdate}')
SELECT  sq0.event_unix_time
        ,sq0.event
        ,sq0.event_value
        ,sq0.item_id
        ,sq0.scene
        ,sq0.mmb_id
        ,sq0.request_id
        ,sq0.page
        ,sq0.day_h
        ,sq0.week_day
        ,sq1.item_type
        ,sq1.cate
        ,sq1.cate_id_path
        ,sq1.copyright_end
        ,sq1.create_time
        ,sq1.current_price
        ,sq1.keyword
        ,sq1.pub_time
        ,sq1.tags
        ,sq1.title
        ,sq1.related_goods_ids
        ,sq1.brand
        ,sq1.core_entity
        ,sq1.dianpufensi
        ,sq1.dianpupingfen
        ,sq1.discount_intensity
        ,sq1.discount_type
        ,sq1.first_cate_id
        ,sq1.second_cate_id
        ,sq1.third_cate_id
        ,sq1.gender_score
        ,sq1.level
        ,sq1.modifiers
        ,sq1.pinpaidengji
        ,sq1.price_tag
        ,sq1.promotion_channel
        ,sq1.publish_user
        ,sq1.shop_id
        ,sq1.site
        ,sq1.spu_id
        ,sq1.sqk_id
        ,sq1.sub_title
        ,sq1.username
        ,sq1.title_vector
FROM    (
            SELECT  *
            FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
            WHERE   dt = '${bdp.system.bizdate}'
        ) sq0
LEFT JOIN (
              SELECT  *
              FROM    home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3
              WHERE   dt = '${bdp.system.bizdate}'
          ) sq1
ON      sq0.item_id = sq1.item_id
;
CREATE TABLE IF NOT EXISTS home_flow_2604_mmb_id_t_seq_v3
(
    mmb_id string
    ,event_unix_time bigint
    ,request_id string
    ,click_50_seq__item_id string
    ,click_50_seq__cate_id_path string
    ,click_50_seq__related_goods_ids string
    ,click_50_seq__brand string
    ,click_50_seq__core_entity string
    ,click_50_seq__first_cate_id string
    ,click_50_seq__second_cate_id string
    ,click_50_seq__third_cate_id string
    ,click_50_seq__price_tag string
    ,click_50_seq__promotion_channel string
    ,click_50_seq__publish_user string
    ,click_50_seq__site string
    ,click_50_seq__spu_id string
    ,click_50_seq__discount_intensity string
    ,click_50_seq__dianpupingfen string
    ,click_50_seq__pinpaidengji string
    ,click_50_seq__dianpufensi string
    ,click_50_seq__item_type string
    ,click_50_seq__username string
    ,click_50_seq__title_vector string
    ,click_50_seq__ts string
    ,conversion_20_seq__item_id string
    ,conversion_20_seq__cate_id_path string
    ,conversion_20_seq__related_goods_ids string
    ,conversion_20_seq__brand string
    ,conversion_20_seq__core_entity string
    ,conversion_20_seq__first_cate_id string
    ,conversion_20_seq__second_cate_id string
    ,conversion_20_seq__third_cate_id string
    ,conversion_20_seq__price_tag string
    ,conversion_20_seq__promotion_channel string
    ,conversion_20_seq__publish_user string
    ,conversion_20_seq__site string
    ,conversion_20_seq__spu_id string
    ,conversion_20_seq__discount_intensity string
    ,conversion_20_seq__dianpupingfen string
    ,conversion_20_seq__pinpaidengji string
    ,conversion_20_seq__dianpufensi string
    ,conversion_20_seq__item_type string
    ,conversion_20_seq__username string
    ,conversion_20_seq__title_vector string
    ,conversion_20_seq__ts string
    ,favorite_10_seq__item_id string
    ,favorite_10_seq__cate_id_path string
    ,favorite_10_seq__related_goods_ids string
    ,favorite_10_seq__brand string
    ,favorite_10_seq__core_entity string
    ,favorite_10_seq__first_cate_id string
    ,favorite_10_seq__second_cate_id string
    ,favorite_10_seq__third_cate_id string
    ,favorite_10_seq__price_tag string
    ,favorite_10_seq__promotion_channel string
    ,favorite_10_seq__publish_user string
    ,favorite_10_seq__site string
    ,favorite_10_seq__spu_id string
    ,favorite_10_seq__discount_intensity string
    ,favorite_10_seq__dianpupingfen string
    ,favorite_10_seq__pinpaidengji string
    ,favorite_10_seq__dianpufensi string
    ,favorite_10_seq__item_type string
    ,favorite_10_seq__username string
    ,favorite_10_seq__title_vector string
    ,favorite_10_seq__ts string
)
PARTITIONED BY
(
    dt string
)
LIFECYCLE 90
;
INSERT OVERWRITE TABLE home_flow_2604_mmb_id_t_seq_v3 PARTITION(dt='${bdp.system.bizdate}')
SELECT  features['pid'] mmb_id
        ,CAST(features['event_time'] AS BIGINT) event_unix_time
        ,features['request_id'] request_id
        ,features['click_50_seq__item_id'] click_50_seq__item_id
        ,features['click_50_seq__cate_id_path'] click_50_seq__cate_id_path
        ,features['click_50_seq__related_goods_ids'] click_50_seq__related_goods_ids
        ,features['click_50_seq__brand'] click_50_seq__brand
        ,features['click_50_seq__core_entity'] click_50_seq__core_entity
        ,features['click_50_seq__first_cate_id'] click_50_seq__first_cate_id
        ,features['click_50_seq__second_cate_id'] click_50_seq__second_cate_id
        ,features['click_50_seq__third_cate_id'] click_50_seq__third_cate_id
        ,features['click_50_seq__price_tag'] click_50_seq__price_tag
        ,features['click_50_seq__promotion_channel'] click_50_seq__promotion_channel
        ,features['click_50_seq__publish_user'] click_50_seq__publish_user
        ,features['click_50_seq__site'] click_50_seq__site
        ,features['click_50_seq__spu_id'] click_50_seq__spu_id
        ,features['click_50_seq__discount_intensity'] click_50_seq__discount_intensity
        ,features['click_50_seq__dianpupingfen'] click_50_seq__dianpupingfen
        ,features['click_50_seq__pinpaidengji'] click_50_seq__pinpaidengji
        ,features['click_50_seq__dianpufensi'] click_50_seq__dianpufensi
        ,features['click_50_seq__item_type'] click_50_seq__item_type
        ,features['click_50_seq__username'] click_50_seq__username
        ,features['click_50_seq__title_vector'] click_50_seq__title_vector
        ,features['click_50_seq__ts'] click_50_seq__ts
        ,features['conversion_20_seq__item_id'] conversion_20_seq__item_id
        ,features['conversion_20_seq__cate_id_path'] conversion_20_seq__cate_id_path
        ,features['conversion_20_seq__related_goods_ids'] conversion_20_seq__related_goods_ids
        ,features['conversion_20_seq__brand'] conversion_20_seq__brand
        ,features['conversion_20_seq__core_entity'] conversion_20_seq__core_entity
        ,features['conversion_20_seq__first_cate_id'] conversion_20_seq__first_cate_id
        ,features['conversion_20_seq__second_cate_id'] conversion_20_seq__second_cate_id
        ,features['conversion_20_seq__third_cate_id'] conversion_20_seq__third_cate_id
        ,features['conversion_20_seq__price_tag'] conversion_20_seq__price_tag
        ,features['conversion_20_seq__promotion_channel'] conversion_20_seq__promotion_channel
        ,features['conversion_20_seq__publish_user'] conversion_20_seq__publish_user
        ,features['conversion_20_seq__site'] conversion_20_seq__site
        ,features['conversion_20_seq__spu_id'] conversion_20_seq__spu_id
        ,features['conversion_20_seq__discount_intensity'] conversion_20_seq__discount_intensity
        ,features['conversion_20_seq__dianpupingfen'] conversion_20_seq__dianpupingfen
        ,features['conversion_20_seq__pinpaidengji'] conversion_20_seq__pinpaidengji
        ,features['conversion_20_seq__dianpufensi'] conversion_20_seq__dianpufensi
        ,features['conversion_20_seq__item_type'] conversion_20_seq__item_type
        ,features['conversion_20_seq__username'] conversion_20_seq__username
        ,features['conversion_20_seq__title_vector'] conversion_20_seq__title_vector
        ,features['conversion_20_seq__ts'] conversion_20_seq__ts
        ,features['favorite_10_seq__item_id'] favorite_10_seq__item_id
        ,features['favorite_10_seq__cate_id_path'] favorite_10_seq__cate_id_path
        ,features['favorite_10_seq__related_goods_ids'] favorite_10_seq__related_goods_ids
        ,features['favorite_10_seq__brand'] favorite_10_seq__brand
        ,features['favorite_10_seq__core_entity'] favorite_10_seq__core_entity
        ,features['favorite_10_seq__first_cate_id'] favorite_10_seq__first_cate_id
        ,features['favorite_10_seq__second_cate_id'] favorite_10_seq__second_cate_id
        ,features['favorite_10_seq__third_cate_id'] favorite_10_seq__third_cate_id
        ,features['favorite_10_seq__price_tag'] favorite_10_seq__price_tag
        ,features['favorite_10_seq__promotion_channel'] favorite_10_seq__promotion_channel
        ,features['favorite_10_seq__publish_user'] favorite_10_seq__publish_user
        ,features['favorite_10_seq__site'] favorite_10_seq__site
        ,features['favorite_10_seq__spu_id'] favorite_10_seq__spu_id
        ,features['favorite_10_seq__discount_intensity'] favorite_10_seq__discount_intensity
        ,features['favorite_10_seq__dianpupingfen'] favorite_10_seq__dianpupingfen
        ,features['favorite_10_seq__pinpaidengji'] favorite_10_seq__pinpaidengji
        ,features['favorite_10_seq__dianpufensi'] favorite_10_seq__dianpufensi
        ,features['favorite_10_seq__item_type'] favorite_10_seq__item_type
        ,features['favorite_10_seq__username'] favorite_10_seq__username
        ,features['favorite_10_seq__title_vector'] favorite_10_seq__title_vector
        ,features['favorite_10_seq__ts'] favorite_10_seq__ts
FROM    (
            SELECT  RT_SEQ_FEATURE(
                        mmb_id
                        ,event_unix_time
                        ,ARRAY(
                            item_id
                            ,cate_id_path
                            ,related_goods_ids
                            ,brand
                            ,core_entity
                            ,first_cate_id
                            ,second_cate_id
                            ,third_cate_id
                            ,price_tag
                            ,promotion_channel
                            ,publish_user
                            ,site
                            ,spu_id
                            ,discount_intensity
                            ,dianpupingfen
                            ,pinpaidengji
                            ,dianpufensi
                            ,item_type
                            ,username
                            ,title_vector
                        )
                        ,ARRAY(
                            'item_id'
                            ,'cate_id_path'
                            ,'related_goods_ids'
                            ,'brand'
                            ,'core_entity'
                            ,'first_cate_id'
                            ,'second_cate_id'
                            ,'third_cate_id'
                            ,'price_tag'
                            ,'promotion_channel'
                            ,'publish_user'
                            ,'site'
                            ,'spu_id'
                            ,'discount_intensity'
                            ,'dianpupingfen'
                            ,'pinpaidengji'
                            ,'dianpufensi'
                            ,'item_type'
                            ,'username'
                            ,'title_vector'
                        )
                        ,event
                        ,ARRAY('click','conversion','favorite')
                        ,ARRAY(50,20,10)
                        ,1
                        ,'split'
                        ,3
                        ,';'
                        ,request_id
                    ) features
            FROM    (
                        SELECT  event_unix_time
                                ,event
                                ,item_id
                                ,scene
                                ,mmb_id
                                ,request_id
                                ,cate_id_path
                                ,related_goods_ids
                                ,brand
                                ,core_entity
                                ,first_cate_id
                                ,second_cate_id
                                ,third_cate_id
                                ,price_tag
                                ,promotion_channel
                                ,publish_user
                                ,site
                                ,spu_id
                                ,discount_intensity
                                ,dianpupingfen
                                ,pinpaidengji
                                ,dianpufensi
                                ,item_type
                                ,username
                                ,title_vector
                        FROM    home_flow_2604_behavior_wide_for_t_seq_v3
                        WHERE   dt = '${bdp.system.bizdate}'
                        DISTRIBUTE BY mmb_id
                        SORT BY mmb_id
                                ,event_unix_time
                    ) sq0
        ) sq1
;
