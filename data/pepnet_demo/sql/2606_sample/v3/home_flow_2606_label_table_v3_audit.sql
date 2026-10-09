--@exclude_output=
SET odps.sql.type.system.odps2 = true;

-- =====================================================================
-- 勘验 SQL：home_flow_2606_ctrcvr_sorter_label_table_v3
-- 覆盖场景分支：home、bijia、haojia、trend（已移除 search/chajia）
-- =====================================================================

-- =========================================================
-- 校验项 1：原始明细各 event 分布 + request_id 完整性
-- 目的：确认新事件已在源表出现，且 trend 全部带 request_id
-- =========================================================
SELECT
    '1_raw_event_dist'            AS audit_item,
    COUNT(1)                      AS total_rows,
    COUNT(IF(event = 'exposure',         1, NULL)) AS e_exposure,
    COUNT(IF(event = 'click',            1, NULL)) AS e_click,
    COUNT(IF(event = 'conversion',       1, NULL)) AS e_conversion,
    COUNT(IF(event = 'search_bijia_exposure',   1, NULL)) AS e_bijia_exp,
    COUNT(IF(event = 'search_haojia_exposure',  1, NULL)) AS e_haojia_exp,
    COUNT(IF(event = 'trend_exposure',   1, NULL)) AS e_trend_exp,
    -- trend 全量 request_id 为 NULL 的行数（应为 0）
    COUNT(IF(event IN ('trend_exposure','trend_click','trend_conversion')
           AND request_id IS NULL, 1, NULL)) AS trend_null_req
FROM home_flow_2606_dwd_log_zhekou_rec_user_bhv_info_preprocess_v2
WHERE dt = '${bdp.system.bizdate}'
;

-- =========================================================
-- 校验项 2：各分支 scene 标记分布（四场景互斥）
-- =========================================================
SELECT
    '2_scene_dist'                AS audit_item,
    COUNT(1)                      AS total_pv,
    SUM(is_home_scene)            AS home_pv,
    SUM(is_bijia_scene)           AS bijia_pv,
    SUM(is_haojia_scene)          AS haojia_pv,
    SUM(CAST(is_trend_scene AS BIGINT))       AS trend_pv
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '${bdp.system.bizdate}'
;

-- =========================================================
-- 校验项 3：场景互斥性检查（每条样本 sum=1）
-- =========================================================
SELECT
    '3_scene_mutual_excl'         AS audit_item,
    COUNT(1)                      AS violating_rows
FROM (
    SELECT mmb_id,
           is_home_scene
           + CAST(is_bijia_scene AS BIGINT)
           + CAST(is_haojia_scene AS BIGINT)
           + CAST(is_trend_scene AS BIGINT) AS scene_sum
    FROM home_flow_2606_ctrcvr_sorter_label_table_v3
    WHERE dt = '${bdp.system.bizdate}'
) t
WHERE scene_sum <> 1
;

-- =========================================================
-- 校验项 4：trend 样本的 request_id 完整性（核心验证）
-- =========================================================
SELECT
    '4_trend_request_id_check'    AS audit_item,
    COUNT(1)                      AS trend_total,
    COUNT(IF(request_id IS NOT NULL, 1, NULL)) AS trend_with_req,
    COUNT(IF(request_id IS NULL,     1, NULL)) AS trend_null_req,
    -- 验证 request_id 对应的曝光事件时间不晚于 trend 事件本身
    SUM(CASE WHEN sub.future_request = 1 THEN 1 ELSE 0 END) AS trend_leakage_rows
FROM (
    SELECT t.event_unix_time  AS trend_time
            ,t.request_id     AS request_id
            ,MAX(r.event_unix_time) AS latest_exposure_time
            ,MAX(CASE WHEN r.event_unix_time > t.event_unix_time THEN 1 ELSE 0 END) AS future_request
    FROM home_flow_2606_ctrcvr_sorter_label_table_v3 t
    LEFT JOIN (
        SELECT mmb_id, event_unix_time, request_id
        FROM home_flow_2606_dwd_log_zhekou_rec_user_bhv_info_preprocess_v2
        WHERE dt = '${bdp.system.bizdate}'
          AND event IN ('exposure','search_bijia_exposure','search_haojia_exposure','trend_exposure')
          AND request_id IS NOT NULL
    ) r ON r.mmb_id = t.mmb_id AND r.request_id = t.request_id
    WHERE t.dt = '${bdp.system.bizdate}'
      AND t.is_trend_scene = 1
    GROUP BY t.event_unix_time, t.request_id
) sub
;

-- =========================================================
-- 校验项 5：各分支行数与源表对应关系
-- =========================================================
SELECT
    '5_source_to_label_ratio'     AS audit_item,
    -- home
    (SELECT COUNT(DISTINCT mmb_id || '|' || request_id)
     FROM home_flow_2606_dwd_log_zhekou_rec_user_bhv_info_preprocess_v2
     WHERE dt = '${bdp.system.bizdate}'
       AND event IN ('exposure','click','conversion','favorite','like')
       AND request_id IS NOT NULL
    ) AS src_home_pairs,
    (SELECT COUNT(1)
     FROM home_flow_2606_ctrcvr_sorter_label_table_v3
     WHERE dt = '${bdp.system.bizdate}' AND is_home_scene = 1
    ) AS lbl_home_rows,
    -- bijia
    (SELECT COUNT(DISTINCT mmb_id || '|' || request_id)
     FROM home_flow_2606_dwd_log_zhekou_rec_user_bhv_info_preprocess_v2
     WHERE dt = '${bdp.system.bizdate}'
       AND event IN ('search_bijia_exposure','search_bijia_click','search_bijia_conversion')
       AND request_id IS NOT NULL
    ) AS src_bijia_pairs,
    (SELECT COUNT(1)
     FROM home_flow_2606_ctrcvr_sorter_label_table_v3
     WHERE dt = '${bdp.system.bizdate}' AND is_bijia_scene = 1
    ) AS lbl_bijia_rows,
    -- haojia
    (SELECT COUNT(DISTINCT mmb_id || '|' || request_id)
     FROM home_flow_2606_dwd_log_zhekou_rec_user_bhv_info_preprocess_v2
     WHERE dt = '${bdp.system.bizdate}'
       AND event IN ('search_haojia_exposure','search_haojia_click','search_haojia_conversion')
       AND request_id IS NOT NULL
    ) AS src_haojia_pairs,
    (SELECT COUNT(1)
     FROM home_flow_2606_ctrcvr_sorter_label_table_v3
     WHERE dt = '${bdp.system.bizdate}' AND is_haojia_scene = 1
    ) AS lbl_haojia_rows,
    -- trend（直接透传，行数 = 源表 distinct (mmb_id,item_id,request_id,unixtime) 数）
    (SELECT COUNT(DISTINCT mmb_id || '|' || item_id || '|' || request_id || '|' || event_unix_time)
     FROM home_flow_2606_dwd_log_zhekou_rec_user_bhv_info_preprocess_v2
     WHERE dt = '${bdp.system.bizdate}'
       AND event IN ('trend_exposure','trend_click','trend_conversion')
    ) AS src_trend_events,
    (SELECT COUNT(1)
     FROM home_flow_2606_ctrcvr_sorter_label_table_v3
     WHERE dt = '${bdp.system.bizdate}' AND is_trend_scene = 1
    ) AS lbl_trend_rows
FROM (SELECT 1) t
;

-- =========================================================
-- 校验项 6：bijia/haojia 行内 click 标记分布
-- 目的：验证 INNER JOIN 保留的样本中，既有正样本也有负样本
-- =========================================================
SELECT
    '6_bijia_click_dist'          AS audit_item,
    COUNT(1)                      AS total_pv,
    SUM(is_bijia_click)           AS bijia_click_pos,
    COUNT(IF(is_bijia_click = 0, 1, NULL)) AS bijia_click_neg
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '${bdp.system.bizdate}'
  AND is_bijia_scene = 1
;

SELECT
    '6_haojia_click_dist'         AS audit_item,
    COUNT(1)                      AS total_pv,
    SUM(is_haojia_click)          AS haojia_click_pos,
    COUNT(IF(is_haojia_click = 0, 1, NULL)) AS haojia_click_neg
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '${bdp.system.bizdate}'
  AND is_haojia_scene = 1
;

-- =========================================================
-- 校验项 7：trend 场景的行为标签分布（sanity check）
-- =========================================================
SELECT
    '7_trend_behavior_dist'       AS audit_item,
    COUNT(1)                      AS trend_pv,
    SUM(is_trend_click)           AS trend_click,
    SUM(is_trend_conversion)      AS trend_conv
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '${bdp.system.bizdate}'
  AND is_trend_scene = 1
;

-- =========================================================
-- 校验项 8：各场景 scene 与 request_id 联合检查
-- =========================================================
SELECT
    '8_scene_request_id_valid'    AS audit_item,
    is_home_scene,
    is_bijia_scene,
    is_haojia_scene,
    is_trend_scene,
    COUNT(1)                                          AS pv,
    COUNT(IF(request_id IS NULL, 1, NULL))            AS null_req_cnt
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '${bdp.system.bizdate}'
GROUP BY is_home_scene, is_bijia_scene, is_haojia_scene
         ,is_trend_scene
HAVING COUNT(1) > 0
ORDER BY pv DESC
;

-- =========================================================
-- 校验项 9：trend 样本的 request_id 与时序一致性
-- =========================================================
SELECT
    '9_trend_temporal_sanity'     AS audit_item,
    COUNT(1)                      AS total_rows,
    SUM(CASE WHEN req_latest_time > sub.trend_time THEN 1 ELSE 0 END) AS future_leakage,
    SUM(CASE WHEN req_latest_time = sub.trend_time THEN 1 ELSE 0 END) AS same_time,
    SUM(CASE WHEN req_latest_time < sub.trend_time THEN 1 ELSE 0 END) AS past_exposure,
    SUM(CASE WHEN req_latest_time IS NULL THEN 1 ELSE 0 END) AS no_exposure_match
FROM (
    SELECT t.event_unix_time  AS trend_time
            ,t.mmb_id         AS mmb_id
            ,t.request_id     AS request_id
            ,MAX(r.event_unix_time) AS req_latest_time
    FROM home_flow_2606_ctrcvr_sorter_label_table_v3 t
    LEFT JOIN (
        SELECT mmb_id, event_unix_time, request_id
        FROM home_flow_2606_dwd_log_zhekou_rec_user_bhv_info_preprocess_v2
        WHERE dt = '${bdp.system.bizdate}'
          AND event IN ('exposure','search_bijia_exposure','search_haojia_exposure','trend_exposure')
          AND request_id IS NOT NULL
    ) r ON r.mmb_id = t.mmb_id AND r.request_id = t.request_id
    WHERE t.dt = '${bdp.system.bizdate}'
      AND t.is_trend_scene = 1
    GROUP BY t.event_unix_time, t.mmb_id, t.request_id
) sub
;
