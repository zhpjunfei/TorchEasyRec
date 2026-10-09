-- 自研算法 home 栏位：2026年7月、8月 score 20等频分位与PCTR。
-- PCTR = 点击事件PV / 曝光事件PV；触达主键 = 日期+用户+请求+帖子。
-- 为复现原图，保留MD5 4/256固定用户样本。

WITH base_log AS (
    SELECT
        CASE
            WHEN dt BETWEEN '20260701' AND '20260731' THEN '2026年7月'
            WHEN dt BETWEEN '20260801' AND '20260831' THEN '2026年8月'
        END AS period_name,
        dt,
        bhv_type,
        user_id,
        request_id,
        CAST(doc_id AS STRING) AS post_key,
        spm,
        mmb_trans_data
    FROM mmb_dwh.ods_lh_log2_user_bhv_df
    WHERE dt BETWEEN '20260701' AND '20260831'
      AND bhv_type IN ('exposure', 'click')
      AND user_id IS NOT NULL
      AND user_id <> ''
      AND SUBSTR(MD5(user_id), 1, 2) IN ('00', '01', '02', '03')
      AND request_id IS NOT NULL
      AND request_id <> ''
      AND doc_id IS NOT NULL
      AND doc_id <> ''
),
home_exposure AS (
    SELECT
        period_name,
        dt,
        user_id,
        request_id,
        post_key,
        CASE
            WHEN spm_segment_3 LIKE '%PAI_REC%' THEN '自研算法'
            ELSE '火山算法'
        END AS algorithm_type,
        CASE
            WHEN spm_segment_3 LIKE '%PAI_REC%'
            THEN COALESCE(
                NULLIF(REGEXP_REPLACE(spm_segment_3, '^.*PAI_REC', ''), ''),
                'PAI模型值为空'
            )
            ELSE '火山算法'
        END AS model_id,
        CASE
            WHEN score_raw RLIKE '^[-+]?[0-9]+([.][0-9]+)?([eE][-+]?[0-9]+)?$'
            THEN CAST(score_raw AS DOUBLE)
            ELSE NULL
        END AS score
    FROM (
        SELECT
            period_name,
            dt,
            user_id,
            request_id,
            post_key,
            SUBSTRING_INDEX(SUBSTRING_INDEX(spm, '$##$', 3), '$##$', -1) AS spm_segment_3,
            NULLIF(GET_JSON_OBJECT(mmb_trans_data, '$.item.extra.score'), '') AS score_raw
        FROM base_log
        WHERE bhv_type = 'exposure'
          AND spm LIKE '%1w_tab_f_index_content%'
    ) parsed
    WHERE REGEXP_REPLACE(spm_segment_3, 'PAI_REC.*$', '') LIKE '1w_tab_f_index_content0%'
),
route_touch AS (
    SELECT
        period_name,
        dt,
        user_id,
        request_id,
        post_key,
        algorithm_type,
        model_id,
        COUNT(*) AS exposure_pv,
        AVG(score) AS score
    FROM home_exposure
    GROUP BY
        period_name,
        dt,
        user_id,
        request_id,
        post_key,
        algorithm_type,
        model_id
),
inhouse_touch AS (
    SELECT
        period_name,
        dt,
        user_id,
        request_id,
        post_key,
        exposure_pv,
        score
    FROM (
        SELECT
            *,
            COUNT(*) OVER (
                PARTITION BY period_name, dt, user_id, request_id, post_key
            ) AS route_cnt
        FROM route_touch
    ) ranked
    WHERE route_cnt = 1
      AND algorithm_type = '自研算法'
      AND score IS NOT NULL
),
click_touch AS (
    SELECT
        period_name,
        dt,
        user_id,
        request_id,
        post_key,
        COUNT(*) AS click_pv
    FROM base_log
    WHERE bhv_type = 'click'
    GROUP BY period_name, dt, user_id, request_id, post_key
),
percentiled AS (
    SELECT
        e.*,
        COALESCE(c.click_pv, 0) AS click_pv,
        NTILE(20) OVER (
            PARTITION BY e.period_name
            ORDER BY e.score, e.dt, e.user_id, e.request_id, e.post_key
        ) AS percentile_bin
    FROM inhouse_touch e
    LEFT JOIN click_touch c
      ON e.period_name = c.period_name
     AND e.dt = c.dt
     AND e.user_id = c.user_id
     AND e.request_id = c.request_id
     AND e.post_key = c.post_key
)
SELECT
    period_name,
    percentile_bin,
    percentile_bin * 5 AS percentile_upper_pct,
    COUNT(*) AS touch_cnt,
    SUM(exposure_pv) AS exposure_pv,
    SUM(click_pv) AS click_pv,
    MIN(score) AS score_min,
    MAX(score) AS score_max,
    AVG(score) AS score_avg,
    SUM(click_pv) / SUM(exposure_pv) AS pctr
FROM percentiled
GROUP BY period_name, percentile_bin
ORDER BY period_name, percentile_bin
LIMIT 100
;
