set odps.sql.type.system.odps2=true;
CREATE TABLE IF NOT EXISTS home_flow_2604_mmb_id_all_seq_feat_v3
(
    mmb_id string
    ,event_unix_time bigint
    ,request_id string
    ,click_10_seq__item_id string
    ,click_10_seq__cate_id_path string
    ,click_10_seq__related_goods_ids string
    ,click_10_seq__brand string
    ,click_10_seq__core_entity string
    ,click_10_seq__first_cate_id string
    ,click_10_seq__second_cate_id string
    ,click_10_seq__third_cate_id string
    ,click_10_seq__price_tag string
    ,click_10_seq__promotion_channel string
    ,click_10_seq__publish_user string
    ,click_10_seq__site string
    ,click_10_seq__spu_id string
    ,click_10_seq__discount_intensity string
    ,click_10_seq__dianpupingfen string
    ,click_10_seq__pinpaidengji string
    ,click_10_seq__dianpufensi string
    ,click_10_seq__item_type string
    ,click_10_seq__username string
    ,click_10_seq__title_vector string
    ,click_10_seq__ts string
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
    ,conversion_5_seq__item_id string
    ,conversion_5_seq__cate_id_path string
    ,conversion_5_seq__related_goods_ids string
    ,conversion_5_seq__brand string
    ,conversion_5_seq__core_entity string
    ,conversion_5_seq__first_cate_id string
    ,conversion_5_seq__second_cate_id string
    ,conversion_5_seq__third_cate_id string
    ,conversion_5_seq__price_tag string
    ,conversion_5_seq__promotion_channel string
    ,conversion_5_seq__publish_user string
    ,conversion_5_seq__site string
    ,conversion_5_seq__spu_id string
    ,conversion_5_seq__discount_intensity string
    ,conversion_5_seq__dianpupingfen string
    ,conversion_5_seq__pinpaidengji string
    ,conversion_5_seq__dianpufensi string
    ,conversion_5_seq__item_type string
    ,conversion_5_seq__username string
    ,conversion_5_seq__title_vector string
    ,conversion_5_seq__ts string
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
    ,favorite_5_seq__item_id string
    ,favorite_5_seq__cate_id_path string
    ,favorite_5_seq__related_goods_ids string
    ,favorite_5_seq__brand string
    ,favorite_5_seq__core_entity string
    ,favorite_5_seq__first_cate_id string
    ,favorite_5_seq__second_cate_id string
    ,favorite_5_seq__third_cate_id string
    ,favorite_5_seq__price_tag string
    ,favorite_5_seq__promotion_channel string
    ,favorite_5_seq__publish_user string
    ,favorite_5_seq__site string
    ,favorite_5_seq__spu_id string
    ,favorite_5_seq__discount_intensity string
    ,favorite_5_seq__dianpupingfen string
    ,favorite_5_seq__pinpaidengji string
    ,favorite_5_seq__dianpufensi string
    ,favorite_5_seq__item_type string
    ,favorite_5_seq__username string
    ,favorite_5_seq__title_vector string
    ,favorite_5_seq__ts string
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
INSERT OVERWRITE TABLE home_flow_2604_mmb_id_all_seq_feat_v3 PARTITION(dt='${bdp.system.bizdate}')
SELECT  sq0.mmb_id
        ,sq0.event_unix_time
        ,sq0.request_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__item_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__cate_id_path
            ,sq1.click_10_seq__cate_id_path
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__cate_id_path
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__related_goods_ids
            ,sq1.click_10_seq__related_goods_ids
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__related_goods_ids
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__brand
            ,sq1.click_10_seq__brand
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__brand
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__core_entity
            ,sq1.click_10_seq__core_entity
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__core_entity
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__first_cate_id
            ,sq1.click_10_seq__first_cate_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__first_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__second_cate_id
            ,sq1.click_10_seq__second_cate_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__second_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__third_cate_id
            ,sq1.click_10_seq__third_cate_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__third_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__price_tag
            ,sq1.click_10_seq__price_tag
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__price_tag
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__promotion_channel
            ,sq1.click_10_seq__promotion_channel
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__promotion_channel
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__publish_user
            ,sq1.click_10_seq__publish_user
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__publish_user
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__site
            ,sq1.click_10_seq__site
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__site
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__spu_id
            ,sq1.click_10_seq__spu_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__spu_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__discount_intensity
            ,sq1.click_10_seq__discount_intensity
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__discount_intensity
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__dianpupingfen
            ,sq1.click_10_seq__dianpupingfen
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__dianpupingfen
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__pinpaidengji
            ,sq1.click_10_seq__pinpaidengji
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__pinpaidengji
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__dianpufensi
            ,sq1.click_10_seq__dianpufensi
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__dianpufensi
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__item_type
            ,sq1.click_10_seq__item_type
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__item_type
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__username
            ,sq1.click_10_seq__username
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__username
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__title_vector
            ,sq1.click_10_seq__title_vector
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) click_10_seq__title_vector
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__ts
            ,sq1.click_10_seq__ts
            ,sq0.click_50_seq__item_id
            ,sq1.click_10_seq__item_id
            ,sq0.event_unix_time
            ,';'
            ,10
            ,1
        ) click_10_seq__ts
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__item_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__cate_id_path
            ,sq1.click_50_seq__cate_id_path
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__cate_id_path
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__related_goods_ids
            ,sq1.click_50_seq__related_goods_ids
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__related_goods_ids
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__brand
            ,sq1.click_50_seq__brand
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__brand
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__core_entity
            ,sq1.click_50_seq__core_entity
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__core_entity
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__first_cate_id
            ,sq1.click_50_seq__first_cate_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__first_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__second_cate_id
            ,sq1.click_50_seq__second_cate_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__second_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__third_cate_id
            ,sq1.click_50_seq__third_cate_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__third_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__price_tag
            ,sq1.click_50_seq__price_tag
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__price_tag
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__promotion_channel
            ,sq1.click_50_seq__promotion_channel
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__promotion_channel
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__publish_user
            ,sq1.click_50_seq__publish_user
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__publish_user
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__site
            ,sq1.click_50_seq__site
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__site
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__spu_id
            ,sq1.click_50_seq__spu_id
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__spu_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__discount_intensity
            ,sq1.click_50_seq__discount_intensity
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__discount_intensity
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__dianpupingfen
            ,sq1.click_50_seq__dianpupingfen
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__dianpupingfen
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__pinpaidengji
            ,sq1.click_50_seq__pinpaidengji
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__pinpaidengji
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__dianpufensi
            ,sq1.click_50_seq__dianpufensi
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__dianpufensi
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__item_type
            ,sq1.click_50_seq__item_type
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__item_type
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__username
            ,sq1.click_50_seq__username
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__username
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__title_vector
            ,sq1.click_50_seq__title_vector
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,0
            ,';'
            ,50
            ,1
        ) click_50_seq__title_vector
        ,SINGLE_SEQ_REPLENISH(
            sq0.click_50_seq__ts
            ,sq1.click_50_seq__ts
            ,sq0.click_50_seq__item_id
            ,sq1.click_50_seq__item_id
            ,sq0.event_unix_time
            ,';'
            ,50
            ,1
        ) click_50_seq__ts
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__item_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__cate_id_path
            ,sq1.conversion_5_seq__cate_id_path
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__cate_id_path
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__related_goods_ids
            ,sq1.conversion_5_seq__related_goods_ids
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__related_goods_ids
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__brand
            ,sq1.conversion_5_seq__brand
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__brand
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__core_entity
            ,sq1.conversion_5_seq__core_entity
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__core_entity
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__first_cate_id
            ,sq1.conversion_5_seq__first_cate_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__first_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__second_cate_id
            ,sq1.conversion_5_seq__second_cate_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__second_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__third_cate_id
            ,sq1.conversion_5_seq__third_cate_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__third_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__price_tag
            ,sq1.conversion_5_seq__price_tag
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__price_tag
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__promotion_channel
            ,sq1.conversion_5_seq__promotion_channel
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__promotion_channel
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__publish_user
            ,sq1.conversion_5_seq__publish_user
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__publish_user
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__site
            ,sq1.conversion_5_seq__site
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__site
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__spu_id
            ,sq1.conversion_5_seq__spu_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__spu_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__discount_intensity
            ,sq1.conversion_5_seq__discount_intensity
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__discount_intensity
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__dianpupingfen
            ,sq1.conversion_5_seq__dianpupingfen
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__dianpupingfen
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__pinpaidengji
            ,sq1.conversion_5_seq__pinpaidengji
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__pinpaidengji
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__dianpufensi
            ,sq1.conversion_5_seq__dianpufensi
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__dianpufensi
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__item_type
            ,sq1.conversion_5_seq__item_type
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__item_type
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__username
            ,sq1.conversion_5_seq__username
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__username
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__title_vector
            ,sq1.conversion_5_seq__title_vector
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) conversion_5_seq__title_vector
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__ts
            ,sq1.conversion_5_seq__ts
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_5_seq__item_id
            ,sq0.event_unix_time
            ,';'
            ,5
            ,1
        ) conversion_5_seq__ts
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__item_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__cate_id_path
            ,sq1.conversion_20_seq__cate_id_path
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__cate_id_path
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__related_goods_ids
            ,sq1.conversion_20_seq__related_goods_ids
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__related_goods_ids
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__brand
            ,sq1.conversion_20_seq__brand
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__brand
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__core_entity
            ,sq1.conversion_20_seq__core_entity
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__core_entity
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__first_cate_id
            ,sq1.conversion_20_seq__first_cate_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__first_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__second_cate_id
            ,sq1.conversion_20_seq__second_cate_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__second_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__third_cate_id
            ,sq1.conversion_20_seq__third_cate_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__third_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__price_tag
            ,sq1.conversion_20_seq__price_tag
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__price_tag
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__promotion_channel
            ,sq1.conversion_20_seq__promotion_channel
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__promotion_channel
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__publish_user
            ,sq1.conversion_20_seq__publish_user
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__publish_user
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__site
            ,sq1.conversion_20_seq__site
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__site
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__spu_id
            ,sq1.conversion_20_seq__spu_id
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__spu_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__discount_intensity
            ,sq1.conversion_20_seq__discount_intensity
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__discount_intensity
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__dianpupingfen
            ,sq1.conversion_20_seq__dianpupingfen
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__dianpupingfen
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__pinpaidengji
            ,sq1.conversion_20_seq__pinpaidengji
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__pinpaidengji
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__dianpufensi
            ,sq1.conversion_20_seq__dianpufensi
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__dianpufensi
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__item_type
            ,sq1.conversion_20_seq__item_type
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__item_type
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__username
            ,sq1.conversion_20_seq__username
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__username
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__title_vector
            ,sq1.conversion_20_seq__title_vector
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,0
            ,';'
            ,20
            ,1
        ) conversion_20_seq__title_vector
        ,SINGLE_SEQ_REPLENISH(
            sq0.conversion_20_seq__ts
            ,sq1.conversion_20_seq__ts
            ,sq0.conversion_20_seq__item_id
            ,sq1.conversion_20_seq__item_id
            ,sq0.event_unix_time
            ,';'
            ,20
            ,1
        ) conversion_20_seq__ts
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__item_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__cate_id_path
            ,sq1.favorite_5_seq__cate_id_path
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__cate_id_path
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__related_goods_ids
            ,sq1.favorite_5_seq__related_goods_ids
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__related_goods_ids
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__brand
            ,sq1.favorite_5_seq__brand
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__brand
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__core_entity
            ,sq1.favorite_5_seq__core_entity
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__core_entity
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__first_cate_id
            ,sq1.favorite_5_seq__first_cate_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__first_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__second_cate_id
            ,sq1.favorite_5_seq__second_cate_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__second_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__third_cate_id
            ,sq1.favorite_5_seq__third_cate_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__third_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__price_tag
            ,sq1.favorite_5_seq__price_tag
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__price_tag
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__promotion_channel
            ,sq1.favorite_5_seq__promotion_channel
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__promotion_channel
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__publish_user
            ,sq1.favorite_5_seq__publish_user
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__publish_user
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__site
            ,sq1.favorite_5_seq__site
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__site
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__spu_id
            ,sq1.favorite_5_seq__spu_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__spu_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__discount_intensity
            ,sq1.favorite_5_seq__discount_intensity
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__discount_intensity
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__dianpupingfen
            ,sq1.favorite_5_seq__dianpupingfen
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__dianpupingfen
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__pinpaidengji
            ,sq1.favorite_5_seq__pinpaidengji
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__pinpaidengji
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__dianpufensi
            ,sq1.favorite_5_seq__dianpufensi
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__dianpufensi
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__item_type
            ,sq1.favorite_5_seq__item_type
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__item_type
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__username
            ,sq1.favorite_5_seq__username
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__username
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__title_vector
            ,sq1.favorite_5_seq__title_vector
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,0
            ,';'
            ,5
            ,1
        ) favorite_5_seq__title_vector
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__ts
            ,sq1.favorite_5_seq__ts
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_5_seq__item_id
            ,sq0.event_unix_time
            ,';'
            ,5
            ,1
        ) favorite_5_seq__ts
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__item_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__cate_id_path
            ,sq1.favorite_10_seq__cate_id_path
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__cate_id_path
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__related_goods_ids
            ,sq1.favorite_10_seq__related_goods_ids
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__related_goods_ids
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__brand
            ,sq1.favorite_10_seq__brand
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__brand
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__core_entity
            ,sq1.favorite_10_seq__core_entity
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__core_entity
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__first_cate_id
            ,sq1.favorite_10_seq__first_cate_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__first_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__second_cate_id
            ,sq1.favorite_10_seq__second_cate_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__second_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__third_cate_id
            ,sq1.favorite_10_seq__third_cate_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__third_cate_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__price_tag
            ,sq1.favorite_10_seq__price_tag
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__price_tag
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__promotion_channel
            ,sq1.favorite_10_seq__promotion_channel
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__promotion_channel
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__publish_user
            ,sq1.favorite_10_seq__publish_user
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__publish_user
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__site
            ,sq1.favorite_10_seq__site
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__site
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__spu_id
            ,sq1.favorite_10_seq__spu_id
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__spu_id
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__discount_intensity
            ,sq1.favorite_10_seq__discount_intensity
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__discount_intensity
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__dianpupingfen
            ,sq1.favorite_10_seq__dianpupingfen
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__dianpupingfen
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__pinpaidengji
            ,sq1.favorite_10_seq__pinpaidengji
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__pinpaidengji
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__dianpufensi
            ,sq1.favorite_10_seq__dianpufensi
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__dianpufensi
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__item_type
            ,sq1.favorite_10_seq__item_type
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__item_type
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__username
            ,sq1.favorite_10_seq__username
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__username
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__title_vector
            ,sq1.favorite_10_seq__title_vector
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,0
            ,';'
            ,10
            ,1
        ) favorite_10_seq__title_vector
        ,SINGLE_SEQ_REPLENISH(
            sq0.favorite_10_seq__ts
            ,sq1.favorite_10_seq__ts
            ,sq0.favorite_10_seq__item_id
            ,sq1.favorite_10_seq__item_id
            ,sq0.event_unix_time
            ,';'
            ,10
            ,1
        ) favorite_10_seq__ts
FROM    (
            SELECT  *
            FROM    home_flow_2604_mmb_id_t_seq_v3
            WHERE   dt = '${bdp.system.bizdate}'
        ) sq0
LEFT JOIN (
              SELECT  *
              FROM    home_flow_2604_mmb_id_pre_t_seq_v3
              WHERE   dt = '${bdp.system.bizdate}'
          ) sq1
ON      sq0.mmb_id = sq1.mmb_id
;
