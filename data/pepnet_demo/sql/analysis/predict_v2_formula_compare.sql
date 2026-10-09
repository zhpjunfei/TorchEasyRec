-- ============================================================
-- 两种融合公式的横向对比（同一天、同一批样本）
-- 核心问题：同一样本在两种公式下得分差异有多大？排序是否一致？
-- ============================================================

-- 1. 全局对比指标
SELECT
    'total' AS dim,
    COUNT(1) AS cnt,
    -- 加法
    ROUND(AVG(additive_score), 6) AS add_avg_score,
    ROUND(STDDEV(additive_score), 6) AS add_score_std,
    ROUND(AVG(CASE WHEN is_click = 1 THEN additive_score END), 6) AS add_avg_score_click,
    ROUND(AVG(CASE WHEN is_click = 0 THEN additive_score END), 6) AS add_avg_score_no_click,
    -- 乘法
    ROUND(AVG(multiplicative_score), 6) AS mul_avg_score,
    ROUND(STDDEV(multiplicative_score), 6) AS mul_score_std,
    ROUND(AVG(CASE WHEN is_click = 1 THEN multiplicative_score END), 6) AS mul_avg_score_click,
    ROUND(AVG(CASE WHEN is_click = 0 THEN multiplicative_score END), 6) AS mul_avg_score_no_click,
    -- 相关性
    ROUND(CORR(additive_score, multiplicative_score), 4) AS score_corr,
    ROUND(CORR(additive_rank, multiplicative_rank), 4) AS rank_corr
FROM (
    SELECT
        probs_ctr,
        probs_cvr,
        is_click,
        (0.8 * probs_ctr + 0.2 * probs_cvr) AS additive_score,
        (0.12 * probs_ctr * (1 + probs_cvr)) AS multiplicative_score,
        ROW_NUMBER() OVER (ORDER BY (0.8 * probs_ctr + 0.2 * probs_cvr) DESC) AS additive_rank,
        ROW_NUMBER() OVER (ORDER BY (0.12 * probs_ctr * (1 + probs_cvr)) DESC) AS multiplicative_rank
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t;

-- 2. 各additive bucket下，乘法score的分布
-- 验证：同一个additive bucket内的商品，在乘法公式下是否仍然聚集？
SELECT
    add_bucket,
    cnt,
    ROUND(AVG(mul_score), 6) AS mul_avg_score,
    ROUND(STDDEV(mul_score), 6) AS mul_score_std,
    ROUND(MIN(mul_score), 6) AS mul_min,
    ROUND(MAX(mul_score), 6) AS mul_max,
    ROUND(AVG(probs_ctr), 4) AS avg_ctr,
    ROUND(AVG(probs_cvr), 4) AS avg_cvr,
    ROUND(SUM(is_click) / COUNT(1), 4) AS pctr
FROM (
    SELECT
        probs_ctr,
        probs_cvr,
        is_click,
        GREATEST(0, LEAST(99, CAST((0.8 * probs_ctr + 0.2 * probs_cvr) * 100 AS BIGINT))) AS add_bucket,
        (0.12 * probs_ctr * (1 + probs_cvr)) AS mul_score
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY add_bucket
ORDER BY add_bucket;

-- 3. 同一样本在两种公式下的bucket差值分布
-- 正数=加法bucket更高，负数=乘法bucket更高
SELECT
    CASE
        WHEN bucket_diff < -10 THEN '<-10 (乘法显著更高)'
        WHEN bucket_diff < -5 THEN '-10~-5'
        WHEN bucket_diff < 0 THEN '-5~0'
        WHEN bucket_diff < 5 THEN '0~5'
        WHEN bucket_diff < 10 THEN '5~10'
        ELSE '>=10 (加法显著更高)'
    END AS diff_range,
    COUNT(1) AS cnt,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (), 2) AS pct
FROM (
    SELECT
        GREATEST(0, LEAST(99, CAST((0.8 * probs_ctr + 0.2 * probs_cvr) * 100 AS BIGINT))) AS add_bucket,
        GREATEST(0, LEAST(99, CAST((0.12 * probs_ctr * (1 + probs_cvr)) * 100 AS BIGINT))) AS mul_bucket,
        (0.8 * probs_ctr + 0.2 * probs_cvr) * 100 - (0.12 * probs_ctr * (1 + probs_cvr)) * 100 AS bucket_diff
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY diff_range
ORDER BY MIN(CASE diff_range
    WHEN '<-10 (乘法显著更高)' THEN 0
    WHEN '-10~-5' THEN 1
    WHEN '-5~0' THEN 2
    WHEN '0~5' THEN 3
    WHEN '5~10' THEN 4
    ELSE 5 END);

-- 4. 固定probs_ctr分位下，probs_cvr对两种公式的影响
-- 验证：在高CTR商品中，CVR的差异是否被乘法/加法公式同等放大？
SELECT
    ctr_quantile,
    cnt,
    ROUND(AVG(probs_ctr), 4) AS avg_ctr,
    ROUND(AVG(probs_cvr), 4) AS avg_cvr,
    ROUND(AVG(additive_score), 6) AS add_score,
    ROUND(AVG(multiplicative_score), 6) AS mul_score,
    ROUND(SUM(is_click) / NULLIF(cnt, 0), 4) AS pctr,
    ROUND(SUM(is_conversion) / NULLIF(SUM(is_click), 0), 4) AS pcvr
FROM (
    SELECT
        probs_ctr,
        probs_cvr,
        is_click,
        is_conversion,
        NTILE(10) OVER (ORDER BY probs_ctr ASC) AS ctr_quantile,
        (0.8 * probs_ctr + 0.2 * probs_cvr) AS additive_score,
        (0.12 * probs_ctr * (1 + probs_cvr)) AS multiplicative_score
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY ctr_quantile
ORDER BY ctr_quantile;

-- 5. 与图2右下角对比：固定乘法score区间，观察真实PCTR
-- 这是验证U型曲线的关键查询
SELECT
    score_range,
    cnt,
    ROUND(AVG(probs_ctr), 4) AS avg_probs_ctr,
    ROUND(AVG(probs_cvr), 4) AS avg_probs_cvr,
    ROUND(SUM(is_click) / NULLIF(cnt, 0), 4) AS actual_pctr,
    ROUND(AVG(probs_ctr) - SUM(is_click) / NULLIF(cnt, 0), 4) AS ctr_calibration_error
FROM (
    SELECT
        probs_ctr,
        probs_cvr,
        is_click,
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
        END AS score_range,
        (0.12 * probs_ctr * (1 + probs_cvr)) AS multiplicative_score
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY score_range
ORDER BY
    MIN(CASE score_range
        WHEN '0~0.02' THEN 1
        WHEN '0.02~0.04' THEN 2
        WHEN '0.04~0.06' THEN 3
        WHEN '0.06~0.08' THEN 4
        WHEN '0.08~0.10' THEN 5
        WHEN '0.12~0.15' THEN 6
        WHEN '0.15~0.18' THEN 7
        WHEN '0.18~0.20' THEN 8
        WHEN '0.20+' THEN 9
        ELSE 0 END);
