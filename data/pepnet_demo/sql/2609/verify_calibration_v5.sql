-- ============================================================
-- 验证SQL: 模型校准分析
-- 目标: 对比预测概率分布与实际label分布
-- ============================================================

-- SQL 1: 各场景预测分布（仅home场景有预测意义）
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
        ELSE 'UNKNOWN'
    END AS scene,
    COUNT(1) AS samples,
    -- CTR预测
    ROUND(AVG(pred_ctr), 4) AS avg_pred_ctr,
    ROUND(STDDEV(pred_ctr), 4) AS std_pred_ctr,
    ROUND(MIN(pred_ctr), 4) AS min_pred_ctr,
    ROUND(MAX(pred_ctr), 4) AS max_pred_ctr,
    -- CTR实际
    ROUND(AVG(is_click), 4) AS actual_ctr,
    -- CVR预测（仅home）
    ROUND(AVG(CASE WHEN is_home_scene = 1 THEN pred_cvr ELSE NULL END), 4) AS avg_pred_cvr_home,
    ROUND(AVG(CASE WHEN is_home_scene = 1 THEN is_conversion ELSE NULL END), 4) AS actual_cvr_home
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261019'
GROUP BY scene;

-- SQL 2: home场景分桶校准分析（关键）
SELECT
    CASE
        WHEN pred_ctr < 0.2 THEN '0-0.2'
        WHEN pred_ctr < 0.3 THEN '0.2-0.3'
        WHEN pred_ctr < 0.4 THEN '0.3-0.4'
        WHEN pred_ctr < 0.5 THEN '0.4-0.5'
        WHEN pred_ctr < 0.6 THEN '0.5-0.6'
        WHEN pred_ctr < 0.7 THEN '0.6-0.7'
        ELSE '0.7-1.0'
    END AS pred_bucket,
    COUNT(1) AS samples,
    ROUND(AVG(pred_ctr), 4) AS avg_pred,
    ROUND(AVG(is_click), 4) AS actual_ctr,
    ROUND(AVG(is_conversion), 4) AS actual_cvr,
    -- 校准偏差
    ROUND(AVG(pred_ctr) - AVG(is_click), 4) AS calibration_error
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261019' AND is_home_scene = 1
GROUP BY pred_bucket
ORDER BY pred_bucket;

-- SQL 3: 预测分布分位数
SELECT
    'ctr_prediction_quantiles' AS metric,
    ROUND(PERCENTILE(pred_ctr, 0.1), 4) AS p10,
    ROUND(PERCENTILE(pred_ctr, 0.25), 4) AS p25,
    ROUND(PERCENTILE(pred_ctr, 0.5), 4) AS p50,
    ROUND(PERCENTILE(pred_ctr, 0.75), 4) AS p75,
    ROUND(PERCENTILE(pred_ctr, 0.9), 4) AS p90
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261019' AND is_home_scene = 1
UNION ALL
SELECT
    'ctr_actual_labels' AS metric,
    ROUND(PERCENTILE(CASE WHEN is_click = 1 THEN pred_ctr END, 0.1), 4) AS p10,
    ROUND(PERCENTILE(CASE WHEN is_click = 1 THEN pred_ctr END, 0.25), 4) AS p25,
    ROUND(PERCENTILE(CASE WHEN is_click = 1 THEN pred_ctr END, 0.5), 4) AS p50,
    ROUND(PERCENTILE(CASE WHEN is_click = 1 THEN pred_ctr END, 0.75), 4) AS p75,
    ROUND(PERCENTILE(CASE WHEN is_click = 1 THEN pred_ctr END, 0.9), 4) AS p90
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261019' AND is_home_scene = 1;
