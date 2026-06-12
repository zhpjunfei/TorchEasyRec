set odps.sql.type.system.odps2=true;
CREATE TABLE IF NOT EXISTS home_flow_2604_behavior_wide_for_pre_t_seq_v3
(
    event_unix_time bigint
    ,event string
    ,item_id string
    ,scene string
    ,mmb_id string
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
INSERT OVERWRITE TABLE home_flow_2604_behavior_wide_for_pre_t_seq_v3 PARTITION(dt='${bdp.system.bizdate}')
SELECT  sq0.event_unix_time
        ,sq0.event
        ,sq0.item_id
        ,sq0.scene
        ,sq0.mmb_id
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
            FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1
            WHERE   dt = TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), - 1,'dd'),'yyyymmdd')
        ) sq0
LEFT JOIN (
              SELECT  *
              FROM    home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3
              WHERE   dt = '${bdp.system.bizdate}'
          ) sq1
ON      sq0.item_id = sq1.item_id
;
CREATE TABLE IF NOT EXISTS home_flow_2604_mmb_id_pre_t_seq_v3
(
    mmb_id string
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
INSERT OVERWRITE TABLE home_flow_2604_mmb_id_pre_t_seq_v3 PARTITION(dt='${bdp.system.bizdate}')
SELECT  mmb_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_id)>0,item_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__item_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(cate_id_path)>0,cate_id_path,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__cate_id_path
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(related_goods_ids)>0,related_goods_ids,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__related_goods_ids
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(brand)>0,brand,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__brand
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(core_entity)>0,core_entity,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__core_entity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(first_cate_id)>0,first_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__first_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(second_cate_id)>0,second_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__second_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(third_cate_id)>0,third_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__third_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(price_tag)>0,price_tag,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__price_tag
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(promotion_channel)>0,promotion_channel,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__promotion_channel
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(publish_user)>0,publish_user,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__publish_user
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(site)>0,site,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__site
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(spu_id)>0,spu_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__spu_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(discount_intensity)>0,discount_intensity,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__discount_intensity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpupingfen)>0,dianpupingfen,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__dianpupingfen
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(pinpaidengji)>0,pinpaidengji,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__pinpaidengji
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpufensi)>0,dianpufensi,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__dianpufensi
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_type)>0,item_type,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__item_type
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(username)>0,username,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__username
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(title_vector)>0,title_vector,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__title_vector
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(event_unix_time)>0,event_unix_time,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,10
        ) click_10_seq__ts
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_id)>0,item_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__item_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(cate_id_path)>0,cate_id_path,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__cate_id_path
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(related_goods_ids)>0,related_goods_ids,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__related_goods_ids
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(brand)>0,brand,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__brand
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(core_entity)>0,core_entity,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__core_entity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(first_cate_id)>0,first_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__first_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(second_cate_id)>0,second_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__second_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(third_cate_id)>0,third_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__third_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(price_tag)>0,price_tag,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__price_tag
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(promotion_channel)>0,promotion_channel,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__promotion_channel
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(publish_user)>0,publish_user,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__publish_user
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(site)>0,site,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__site
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(spu_id)>0,spu_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__spu_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(discount_intensity)>0,discount_intensity,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__discount_intensity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpupingfen)>0,dianpupingfen,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__dianpupingfen
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(pinpaidengji)>0,pinpaidengji,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__pinpaidengji
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpufensi)>0,dianpufensi,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__dianpufensi
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_type)>0,item_type,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__item_type
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(username)>0,username,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__username
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(title_vector)>0,title_vector,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__title_vector
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(event_unix_time)>0,event_unix_time,'')
            ,event_unix_time
            ,event
            ,ARRAY('click')
            ,';'
            ,50
        ) click_50_seq__ts
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_id)>0,item_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__item_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(cate_id_path)>0,cate_id_path,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__cate_id_path
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(related_goods_ids)>0,related_goods_ids,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__related_goods_ids
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(brand)>0,brand,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__brand
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(core_entity)>0,core_entity,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__core_entity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(first_cate_id)>0,first_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__first_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(second_cate_id)>0,second_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__second_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(third_cate_id)>0,third_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__third_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(price_tag)>0,price_tag,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__price_tag
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(promotion_channel)>0,promotion_channel,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__promotion_channel
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(publish_user)>0,publish_user,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__publish_user
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(site)>0,site,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__site
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(spu_id)>0,spu_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__spu_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(discount_intensity)>0,discount_intensity,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__discount_intensity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpupingfen)>0,dianpupingfen,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__dianpupingfen
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(pinpaidengji)>0,pinpaidengji,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__pinpaidengji
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpufensi)>0,dianpufensi,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__dianpufensi
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_type)>0,item_type,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__item_type
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(username)>0,username,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__username
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(title_vector)>0,title_vector,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__title_vector
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(event_unix_time)>0,event_unix_time,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,5
        ) conversion_5_seq__ts
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_id)>0,item_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__item_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(cate_id_path)>0,cate_id_path,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__cate_id_path
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(related_goods_ids)>0,related_goods_ids,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__related_goods_ids
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(brand)>0,brand,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__brand
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(core_entity)>0,core_entity,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__core_entity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(first_cate_id)>0,first_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__first_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(second_cate_id)>0,second_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__second_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(third_cate_id)>0,third_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__third_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(price_tag)>0,price_tag,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__price_tag
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(promotion_channel)>0,promotion_channel,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__promotion_channel
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(publish_user)>0,publish_user,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__publish_user
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(site)>0,site,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__site
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(spu_id)>0,spu_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__spu_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(discount_intensity)>0,discount_intensity,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__discount_intensity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpupingfen)>0,dianpupingfen,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__dianpupingfen
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(pinpaidengji)>0,pinpaidengji,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__pinpaidengji
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpufensi)>0,dianpufensi,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__dianpufensi
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_type)>0,item_type,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__item_type
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(username)>0,username,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__username
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(title_vector)>0,title_vector,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__title_vector
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(event_unix_time)>0,event_unix_time,'')
            ,event_unix_time
            ,event
            ,ARRAY('conversion')
            ,';'
            ,20
        ) conversion_20_seq__ts
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_id)>0,item_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__item_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(cate_id_path)>0,cate_id_path,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__cate_id_path
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(related_goods_ids)>0,related_goods_ids,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__related_goods_ids
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(brand)>0,brand,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__brand
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(core_entity)>0,core_entity,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__core_entity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(first_cate_id)>0,first_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__first_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(second_cate_id)>0,second_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__second_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(third_cate_id)>0,third_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__third_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(price_tag)>0,price_tag,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__price_tag
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(promotion_channel)>0,promotion_channel,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__promotion_channel
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(publish_user)>0,publish_user,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__publish_user
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(site)>0,site,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__site
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(spu_id)>0,spu_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__spu_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(discount_intensity)>0,discount_intensity,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__discount_intensity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpupingfen)>0,dianpupingfen,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__dianpupingfen
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(pinpaidengji)>0,pinpaidengji,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__pinpaidengji
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpufensi)>0,dianpufensi,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__dianpufensi
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_type)>0,item_type,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__item_type
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(username)>0,username,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__username
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(title_vector)>0,title_vector,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__title_vector
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(event_unix_time)>0,event_unix_time,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,5
        ) favorite_5_seq__ts
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_id)>0,item_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__item_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(cate_id_path)>0,cate_id_path,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__cate_id_path
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(related_goods_ids)>0,related_goods_ids,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__related_goods_ids
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(brand)>0,brand,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__brand
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(core_entity)>0,core_entity,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__core_entity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(first_cate_id)>0,first_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__first_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(second_cate_id)>0,second_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__second_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(third_cate_id)>0,third_cate_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__third_cate_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(price_tag)>0,price_tag,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__price_tag
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(promotion_channel)>0,promotion_channel,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__promotion_channel
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(publish_user)>0,publish_user,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__publish_user
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(site)>0,site,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__site
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(spu_id)>0,spu_id,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__spu_id
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(discount_intensity)>0,discount_intensity,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__discount_intensity
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpupingfen)>0,dianpupingfen,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__dianpupingfen
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(pinpaidengji)>0,pinpaidengji,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__pinpaidengji
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(dianpufensi)>0,dianpufensi,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__dianpufensi
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(item_type)>0,item_type,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__item_type
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(username)>0,username,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__username
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(title_vector)>0,title_vector,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__title_vector
        ,WM_CONCAT_BY_SORT(
            IF(LENGTH(event_unix_time)>0,event_unix_time,'')
            ,event_unix_time
            ,event
            ,ARRAY('favorite')
            ,';'
            ,10
        ) favorite_10_seq__ts
FROM    home_flow_2604_behavior_wide_for_pre_t_seq_v3
WHERE   dt = '${bdp.system.bizdate}'
GROUP BY mmb_id
;
