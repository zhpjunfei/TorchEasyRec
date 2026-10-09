CREATE TABLE IF NOT EXISTS home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_wide_v1
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
    ,type string
    ,gender string
    ,age_group string
    ,reg_type string
    ,mmb_level string
    ,user_status string
    ,mmb_status string
    ,intergral double
    ,gold_coin double
    ,is_subscribe_discount string
    ,is_subscribe_savemoney string
    ,is_subscribe_clockin string
    ,receive_push string
    ,is_not_disturb string
    ,is_atpush string
    ,province string
    ,city string
    ,area_code string
    ,reg_time string
    ,login_province string
    ,login_city string
    ,login_time string
    ,sdk_version string
    ,app_version string
    ,os_type string
    ,os_version string
    ,dev_brand string
    ,dev_model string
    ,jpush string
    ,first_campaign_name string
    ,first_utm_campaign string
    ,first_utm_source string
    ,first_ad_name string
    ,first_site_name string
    ,install_apps string
    ,lifecycle_tags string
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
)
PARTITIONED BY
(
    dt string
)
LIFECYCLE 90
;
