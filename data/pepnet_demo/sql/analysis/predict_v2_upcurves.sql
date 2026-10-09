-- ============================================================
-- 关键验证：乘法融合U型PCTR曲线
-- 对应第二张对比图右下角"固定score区间PCTR"
-- 目标：确认中间score区间是否存在PCTR断崖
-- ============================================================

-- 1. 加法融合：score区间 vs PCTR（应单调上升）
SELECT
    add_score_range,
    cnt,
    ROUND(AVG(probs_ctr), 4) AS avg_probs_ctr,
    ROUND(AVG(probs_cvr), 4) AS avg_probs_cvr,
    ROUND(SUM(is_click) / NULLIF(cnt, 0), 4) AS pctr,
    ROUND(SUM(is_conversion) / NULLIF(SUM(is_click), 0), 4) AS pcvr,
    ROUND(SUM(is_click) / NULLIF(cnt, 0) - AVG(probs_ctr), 4) AS ctr_bias
FROM (
    SELECT
        probs_ctr,
        probs_cvr,
        is_click,
        is_conversion,
        CASE
            WHEN additive_score < 0.10 THEN '0~0.10'
            WHEN additive_score < 0.20 THEN '0.10~0.20'
            WHEN additive_score < 0.30 THEN '0.20~0.30'
            WHEN additive_score < 0.40 THEN '0.30~0.40'
            WHEN additive_score < 0.50 THEN '0.40~0.50'
            WHEN additive_score < 0.60 THEN '0.50~0.60'
            WHEN additive_score < 0.70 THEN '0.60~0.70'
            WHEN additive_score < 0.80 THEN '0.70~0.80'
            ELSE '0.80+'
        END AS add_score_range,
        (0.8 * probs_ctr + 0.2 * probs_cvr) AS additive_score
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY add_score_range
ORDER BY MIN(CASE add_score_range
    WHEN '0~0.10' THEN 1 WHEN '0.10~0.20' THEN 2 WHEN '0.20~0.30' THEN 3
    WHEN '0.30~0.40' THEN 4 WHEN '0.40~0.50' THEN 5 WHEN '0.50~0.60' THEN 6
    WHEN '0.60~0.70' THEN 7 WHEN '0.70~0.80' THEN 8 ELSE 9 END);

-- 2. 乘法融合：score区间 vs PCTR（应呈现U型）
SELECT
    mul_score_range,
    cnt,
    ROUND(AVG(probs_ctr), 4) AS avg_probs_ctr,
    ROUND(AVG(probs_cvr), 4) AS avg_probs_cvr,
    ROUND(SUM(is_click) / NULLIF(cnt, 0), 4) AS pctr,
    ROUND(SUM(is_conversion) / NULLIF(SUM(is_click), 0), 4) AS pcvr,
    ROUND(SUM(is_click) / NULLIF(cnt, 0) - AVG(probs_ctr), 4) AS ctr_bias
FROM (
    SELECT
        probs_ctr,
        probs_cvr,
        is_click,
        is_conversion,
        CASE
            WHEN multiplicative_score < 0.02 THEN '0~0.02'
            WHEN multiplicative_score < 0.04 THEN '0.02~0.04'
            WHEN multiplicative_score < 0.06 THEN '0.04~0.06'
            WHEN multiplicative_score < 0.08 THEN '0.06~0.08'
            WHEN multiplicative_score < 0.10 THEN '0.08~0.10'
            WHEN multiplicative_score < 0.12 THEN '0.10~0.12'
            WHEN multiplicative_score < 0.15 THEN '0.12~0.15'
            WHEN multiplicative_score < 0.18 THEN '0.15~0.18'
            WHEN multiplicative_score < 0.20 THEN '0.18~0.20'
            ELSE '0.20+'
        END AS mul_score_range,
        (0.12 * probs_ctr * (1 + probs_cvr)) AS multiplicative_score
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY mul_score_range
ORDER BY MIN(CASE mul_score_range
    WHEN '0~0.02' THEN 1 WHEN '0.02~0.04' THEN 2 WHEN '0.04~0.06' THEN 3
    WHEN '0.06~0.08' THEN 4 WHEN '0.08~0.10' THEN 5 WHEN '0.10~0.12' THEN 6
    WHEN '0.12~0.15' THEN 7 WHEN '0.15~0.18' THEN 8 WHEN '0.18~0.20' THEN 9 ELSE 10 END);

-- 3. 验证：乘法公式中，同一score区间内CTR和CVR的组合差异
-- 如果U型是因为"CVR补偿型"商品集中在中段，这里应该能看到
SELECT
    mul_score_range,
    cnt,
    ROUND(AVG(CASE WHEN probs_ctr > 0.10 THEN probs_ctr END), 4) AS high_ctr_avg,
    ROUND(AVG(CASE WHEN probs_ctr <= 0.10 THEN probs_ctr END), 4) AS low_ctr_avg,
    ROUND(SUM(CASE WHEN probs_ctr > 0.10 THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 1) AS high_ctr_pct,
    ROUND(AVG(CASE WHEN probs_ctr > 0.10 THEN probs_cvr END), 4) AS high_ctr_cvr,
    ROUND(AVG(CASE WHEN probs_ctr <= 0.10 THEN probs_cvr END), 4) AS low_ctr_cvr,
    ROUND(SUM(CASE WHEN is_click = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(1), 2) AS click_rate_pct
FROM (
    SELECT
        probs_ctr,
        probs_cvr,
        is_click,
        CASE
            WHEN multiplicative_score < 0.04 THEN '0~0.04'
            WHEN multiplicative_score < 0.08 THEN '0.04~0.08'
            WHEN multiplicative_score < 0.12 THEN '0.08~0.12'
            WHEN multiplicative_score < 0.16 THEN '0.12~0.16'
            ELSE '0.16+'
        END AS mul_score_range,
        (0.12 * probs_ctr * (1 + probs_cvr)) AS multiplicative_score
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY mul_score_range
ORDER BY MIN(CASE mul_score_range
    WHEN '0~0.04' THEN 1 WHEN '0.04~0.08' THEN 2 WHEN '0.08~0.12' THEN 3
    WHEN '0.12~0.16' THEN 4 ELSE 5 END);

-- 4. 两个公式的score重合度：有多少商品的bucket在两种公式下相同/相邻？
SELECT
    CASE
        WHEN ABS(add_bucket - mul_bucket) = 0 THEN '完全相同'
        WHEN ABS(add_bucket - mul_bucket) <= 5 THEN '相差≤5桶'
        WHEN ABS(add_bucket - mul_bucket) <= 10 THEN '相差6~10桶'
        ELSE '相差>10桶'
    END AS overlap_level,
    COUNT(1) AS cnt,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (), 2) AS pct,
    ROUND(AVG(CASE WHEN is_click = 1 THEN 1 ELSE 0 END), 4) AS pctr
FROM (
    SELECT
        is_click,
        GREATEST(0, LEAST(99, CAST((0.8 * probs_ctr + 0.2 * probs_cvr) * 100 AS BIGINT))) AS add_bucket,
        GREATEST(0, LEAST(99, CAST((0.12 * probs_ctr * (1 + probs_cvr)) * 100 AS BIGINT))) AS mul_bucket
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY overlap_level
ORDER BY MIN(CASE overlap_level
    WHEN '完全相同' THEN 0 WHEN '相差≤5桶' THEN 1 WHEN '相差6~10桶' THEN 2 ELSE 3 END);
