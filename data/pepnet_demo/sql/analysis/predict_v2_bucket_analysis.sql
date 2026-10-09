-- ============================================================
-- home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2 分析SQL
-- 用途：评估T-1模型预测质量、score分布、融合公式对比
-- 表说明：使用前一天模型预测当天样本，dt为预测日期
-- ============================================================

-- ============================================================
-- 1. 基础分布与质量校验
-- ============================================================
SELECT
    COUNT(1) AS total_samples,
    COUNT(DISTINCT mmb_id) AS unique_mmb,
    SUM(is_click) AS total_clicks,
    ROUND(SUM(is_click) / COUNT(1), 4) AS overall_ctr,
    SUM(is_conversion) AS total_conversions,
    ROUND(SUM(is_conversion) / NULLIF(SUM(is_click), 0), 4) AS overall_cvr,
    ROUND(AVG(probs_ctr), 4) AS avg_probs_ctr,
    ROUND(AVG(probs_cvr), 4) AS avg_probs_cvr,
    ROUND(AVG(logits_ctr), 4) AS avg_logits_ctr,
    ROUND(AVG(logits_cvr), 4) AS avg_logits_cvr
FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
WHERE dt = '${bdp.system.bizdate}';


-- ============================================================
-- 2. Score Bucket 分布（两种融合公式）
-- ============================================================
-- bucket = int(score * 100) 取整
-- 加法：0.8*probs_ctr + 0.2*probs_cvr
-- 乘法：0.12*probs_ctr*(1+probs_cvr)
SELECT
    dt,
    -- ===== 加法融合 =====
    COUNT(CASE WHEN additive_score_bucket IS NOT NULL THEN 1 END) AS additive_cnt,
    AVG(CASE WHEN additive_score_bucket IS NOT NULL THEN probs_ctr END) AS additive_avg_ctr,
    AVG(CASE WHEN additive_score_bucket IS NOT NULL THEN probs_cvr END) AS additive_avg_cvr,
    SUM(CASE WHEN additive_score_bucket IS NOT NULL THEN is_click END) AS additive_clicks,
    ROUND(SUM(CASE WHEN additive_score_bucket IS NOT NULL THEN is_click END)
          / NULLIF(COUNT(CASE WHEN additive_score_bucket IS NOT NULL THEN 1 END), 0), 4) AS additive_pctr,
    -- ===== 乘法融合 =====
    COUNT(CASE WHEN multiplicative_score_bucket IS NOT NULL THEN 1 END) AS multiplicative_cnt,
    AVG(CASE WHEN multiplicative_score_bucket IS NOT NULL THEN probs_ctr END) AS multiplicative_avg_ctr,
    AVG(CASE WHEN multiplicative_score_bucket IS NOT NULL THEN probs_cvr END) AS multiplicative_avg_cvr,
    SUM(CASE WHEN multiplicative_score_bucket IS NOT NULL THEN is_click END) AS multiplicative_clicks,
    ROUND(SUM(CASE WHEN multiplicative_score_bucket IS NOT NULL THEN is_click END)
          / NULLIF(COUNT(CASE WHEN multiplicative_score_bucket IS NOT NULL THEN 1 END), 0), 4) AS multiplicative_pctr
FROM (
    SELECT
        dt,
        mmb_id,
        probs_ctr,
        probs_cvr,
        is_click,
        is_conversion,
        -- 加法 score bucket (0~100)
        GREATEST(0, LEAST(100, CAST(ROUND((0.8 * probs_ctr + 0.2 * probs_cvr) * 100) AS BIGINT))) AS additive_score_bucket,
        -- 乘法 score bucket (0~100)
        GREATEST(0, LEAST(100, CAST(ROUND((0.12 * probs_ctr * (1 + probs_cvr)) * 100) AS BIGINT))) AS multiplicative_score_bucket
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY dt;


-- ============================================================
-- 3. 详细 Bucket 分布（加法融合，10个桶）
-- ============================================================
SELECT
    bucket,
    cnt,
    ROUND(pctr, 4) AS pctr,
    ROUND(pcvr, 4) AS pcvr,
    ROUND(avg_probs_ctr, 4) AS avg_probs_ctr,
    ROUND(avg_probs_cvr, 4) AS avg_probs_cvr,
    ROUND(calibration_ctr, 4) AS calibration_ctr,
    ROUND(calibration_cvr, 4) AS calibration_cvr
FROM (
    SELECT
        bucket,
        COUNT(1) AS cnt,
        ROUND(SUM(is_click) / COUNT(1), 4) AS pctr,
        ROUND(SUM(is_conversion) / NULLIF(SUM(is_click), 0), 4) AS pcvr,
        ROUND(AVG(probs_ctr), 4) AS avg_probs_ctr,
        ROUND(AVG(probs_cvr), 4) AS avg_probs_cvr,
        -- 校准指标：预测均值 vs 实际比率
        ROUND(ABS(AVG(probs_ctr) - SUM(is_click) / COUNT(1)) / NULLIF(AVG(probs_ctr), 0), 4) AS calibration_ctr,
        ROUND(ABS(AVG(probs_cvr) - SUM(is_conversion) / NULLIF(SUM(is_click), 0))
              / NULLIF(AVG(probs_cvr), 0), 4) AS calibration_cvr
    FROM (
        SELECT
            probs_ctr,
            probs_cvr,
            is_click,
            is_conversion,
            -- 10个桶：0~9, 10~19, ..., 90~99
            CAST((0.8 * probs_ctr + 0.2 * probs_cvr) * 10 AS BIGINT) AS bucket
        FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
        WHERE dt = '${bdp.system.bizdate}'
    ) t
    GROUP BY bucket
    ORDER BY bucket
);


-- ============================================================
-- 4. 详细 Bucket 分布（乘法融合，10个桶）
-- ============================================================
SELECT
    bucket,
    cnt,
    ROUND(pctr, 4) AS pctr,
    ROUND(pcvr, 4) AS pcvr,
    ROUND(avg_probs_ctr, 4) AS avg_probs_ctr,
    ROUND(avg_probs_cvr, 4) AS avg_probs_cvr,
    ROUND(calibration_ctr, 4) AS calibration_ctr
FROM (
    SELECT
        bucket,
        COUNT(1) AS cnt,
        ROUND(SUM(is_click) / COUNT(1), 4) AS pctr,
        ROUND(SUM(is_conversion) / NULLIF(SUM(is_click), 0), 4) AS pcvr,
        ROUND(AVG(probs_ctr), 4) AS avg_probs_ctr,
        ROUND(AVG(probs_cvr), 4) AS avg_probs_cvr,
        ROUND(ABS(AVG(probs_ctr) - SUM(is_click) / COUNT(1)) / NULLIF(AVG(probs_ctr), 0), 4) AS calibration_ctr
    FROM (
        SELECT
            probs_ctr,
            probs_cvr,
            is_click,
            is_conversion,
            CAST((0.12 * probs_ctr * (1 + probs_cvr)) * 10 AS BIGINT) AS bucket
        FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
        WHERE dt = '${bdp.system.bizdate}'
    ) t
    GROUP BY bucket
    ORDER BY bucket
);


-- ============================================================
-- 5. 100个桶精细分布（加法融合）
-- ============================================================
SELECT
    bucket,
    cnt,
    ROUND(cnt * 100.0 / SUM(cnt) OVER (), 4) AS pct_of_total,
    ROUND(pctr, 4) AS pctr,
    ROUND(pcvr, 4) AS pcvr,
    ROUND(avg_probs_ctr, 4) AS avg_probs_ctr,
    ROUND(avg_probs_cvr, 4) AS avg_probs_cvr,
    ROUND(SUM(cnt) OVER (ORDER BY bucket) / SUM(cnt) OVER (), 4) AS cum_pct,
    ROUND(SUM(is_click) OVER (ORDER BY bucket) / NULLIF(SUM(cnt) OVER (ORDER BY bucket), 0), 4) AS cum_pctr
FROM (
    SELECT
        bucket,
        cnt,
        is_click,
        is_conversion,
        avg_probs_ctr,
        avg_probs_cvr,
        ROUND(is_click * 1.0 / cnt, 4) AS pctr,
        ROUND(is_conversion * 1.0 / NULLIF(is_click, 0), 4) AS pcvr
    FROM (
        SELECT
            GREATEST(0, LEAST(99, CAST((0.8 * probs_ctr + 0.2 * probs_cvr) * 100 AS BIGINT))) AS bucket,
            COUNT(1) AS cnt,
            SUM(is_click) AS is_click,
            SUM(is_conversion) AS is_conversion,
            AVG(probs_ctr) AS avg_probs_ctr,
            AVG(probs_cvr) AS avg_probs_cvr
        FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
        WHERE dt = '${bdp.system.bizdate}'
        GROUP BY bucket
    ) t1
) t2
ORDER BY bucket;


-- ============================================================
-- 6. AUC 计算（CTR 和 CVR）
-- 使用排序法：AUC = (sum_rank_positive - pos*(pos+1)/2) / (pos*neg)
-- ============================================================
-- CTR AUC
SELECT
    'ctr' AS task,
    ROUND(
        (SUM(CASE WHEN is_click = 1 THEN rank_pos ELSE NULL END)
         - pos_cnt * (pos_cnt + 1) / 2.0)
        / NULLIF(neg_cnt * pos_cnt, 0),
        4
    ) AS auc
FROM (
    SELECT
        is_click,
        ROW_NUMBER() OVER (ORDER BY probs_ctr ASC) AS rank_pos
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
CROSS JOIN (
    SELECT
        SUM(CASE WHEN is_click = 1 THEN 1 ELSE 0 END) AS pos_cnt,
        SUM(CASE WHEN is_click = 0 THEN 1 ELSE 0 END) AS neg_cnt
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) c
GROUP BY task, pos_cnt, neg_cnt;

-- CVR AUC（注意：CVR标签是点击后的转化，分母是click=1的子集）
SELECT
    'cvr' AS task,
    ROUND(
        (SUM(CASE WHEN is_conversion = 1 THEN rank_pos ELSE NULL END)
         - pos_cnt * (pos_cnt + 1) / 2.0)
        / NULLIF(neg_cnt * pos_cnt, 0),
        4
    ) AS auc
FROM (
    SELECT
        is_conversion,
        ROW_NUMBER() OVER (ORDER BY probs_cvr ASC) AS rank_pos
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}' AND is_click = 1
) t
CROSS JOIN (
    SELECT
        SUM(CASE WHEN is_conversion = 1 THEN 1 ELSE 0 END) AS pos_cnt,
        SUM(CASE WHEN is_conversion = 0 THEN 1 ELSE 0 END) AS neg_cnt
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}' AND is_click = 1
) c
GROUP BY task, pos_cnt, neg_cnt;


-- ============================================================
-- 7. KS 统计量（CTR 和 CVR）
-- KS = max|TPR - FPR|
-- ============================================================
-- CTR KS
SELECT
    'ctr' AS task,
    ROUND(MAX(ABS(tpr - fpr)), 4) AS ks
FROM (
    SELECT
        bucket,
        SUM(is_click) AS cum_pos,
        SUM(CASE WHEN is_click = 0 THEN 1 ELSE 0 END) AS cum_neg,
        SUM(SUM(is_click)) OVER () AS total_pos,
        SUM(SUM(CASE WHEN is_click = 0 THEN 1 ELSE 0 END)) OVER () AS total_neg,
        SUM(is_click) / NULLIF(SUM(SUM(is_click)) OVER (), 0) AS tpr,
        SUM(CASE WHEN is_click = 0 THEN 1 ELSE 0 END) / NULLIF(SUM(SUM(CASE WHEN is_click = 0 THEN 1 ELSE 0 END)) OVER (), 0) AS fpr
    FROM (
        SELECT
            is_click,
            CAST((0.8 * probs_ctr + 0.2 * probs_cvr) * 10 AS BIGINT) AS bucket
        FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
        WHERE dt = '${bdp.system.bizdate}'
    ) t
    GROUP BY bucket
) t;

-- CVR KS
SELECT
    'cvr' AS task,
    ROUND(MAX(ABS(tpr - fpr)), 4) AS ks
FROM (
    SELECT
        bucket,
        SUM(is_conversion) AS cum_pos,
        SUM(CASE WHEN is_conversion = 0 THEN 1 ELSE 0 END) AS cum_neg,
        SUM(SUM(is_conversion)) OVER () AS total_pos,
        SUM(SUM(CASE WHEN is_conversion = 0 THEN 1 ELSE 0 END)) OVER () AS total_neg,
        SUM(is_conversion) / NULLIF(SUM(SUM(is_conversion)) OVER (), 0) AS tpr,
        SUM(CASE WHEN is_conversion = 0 THEN 1 ELSE 0 END) / NULLIF(SUM(SUM(CASE WHEN is_conversion = 0 THEN 1 ELSE 0 END)) OVER (), 0) AS fpr
    FROM (
        SELECT
            is_conversion,
            CAST((0.8 * probs_ctr + 0.2 * probs_cvr) * 10 AS BIGINT) AS bucket
        FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
        WHERE dt = '${bdp.system.bizdate}' AND is_click = 1
    ) t
    GROUP BY bucket
) t;


-- ============================================================
-- 8. 两种融合公式的 score 相关性分析
-- 对比同一商品在两种公式下的score差异
-- ============================================================
SELECT
    COUNT(1) AS total,
    ROUND(CORR(additive_score, multiplicative_score), 4) AS score_corr,
    ROUND(AVG(ADDITIVE_SCORE - MULTIPLICATIVE_SCORE), 4) AS avg_score_diff,
    ROUND(MAX(ABS(ADDITIVE_SCORE - MULTIPLICATIVE_SCORE)), 4) AS max_score_diff,
    -- 排名冲突率：两种公式排名顺序不一致的比例
    ROUND(
        SUM(CASE WHEN additive_rank <> multiplicative_rank THEN 1 ELSE 0 END)
        / NULLIF(COUNT(1), 0), 4
    ) AS rank_disagreement_rate
FROM (
    SELECT
        mmb_id,
        request_id,
        probs_ctr,
        probs_cvr,
        is_click,
        (0.8 * probs_ctr + 0.2 * probs_cvr) AS additive_score,
        (0.12 * probs_ctr * (1 + probs_cvr)) AS multiplicative_score,
        ROW_NUMBER() OVER (PARTITION BY dt ORDER BY (0.8 * probs_ctr + 0.2 * probs_cvr) DESC) AS additive_rank,
        ROW_NUMBER() OVER (PARTITION BY dt ORDER BY (0.12 * probs_ctr * (1 + probs_cvr)) DESC) AS multiplicative_rank
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t;


-- ============================================================
-- 9. MMB 维度分析：头部MMB的模型表现
-- ============================================================
SELECT
    mmb_id,
    COUNT(1) AS sample_cnt,
    ROUND(SUM(is_click) / COUNT(1), 4) AS pctr,
    ROUND(SUM(is_conversion) / NULLIF(SUM(is_click), 0), 4) AS pcvr,
    ROUND(AVG(probs_ctr), 4) AS avg_probs_ctr,
    ROUND(AVG(probs_cvr), 4) AS avg_probs_cvr,
    -- MMB级别的AUC
    ROUND(
        (SUM(CASE WHEN is_click = 1 THEN rank_pos ELSE NULL END)
         - pos_cnt * (pos_cnt + 1) / 2.0)
        / NULLIF(neg_cnt * pos_cnt, 0),
        4
    ) AS mmb_ctr_auc
FROM (
    SELECT
        mmb_id,
        is_click,
        is_conversion,
        probs_ctr,
        probs_cvr,
        ROW_NUMBER() OVER (PARTITION BY mmb_id ORDER BY probs_ctr ASC) AS rank_pos,
        SUM(CASE WHEN is_click = 1 THEN 1 ELSE 0 END) OVER (PARTITION BY mmb_id) AS pos_cnt,
        SUM(CASE WHEN is_click = 0 THEN 1 ELSE 0 END) OVER (PARTITION BY mmb_id) AS neg_cnt
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
) t
GROUP BY mmb_id, pos_cnt, neg_cnt
HAVING COUNT(1) >= 100  -- 至少100个样本才统计
ORDER BY sample_cnt DESC
LIMIT 50;


-- ============================================================
-- 10. Score × 实际行为 交叉表（乘法融合，100桶）
-- 验证高score商品是否真的对应高PCTR
-- ============================================================
SELECT
    CASE
        WHEN multiplicative_score_bucket < 10 THEN '0~9'
        WHEN multiplicative_score_bucket < 20 THEN '10~19'
        WHEN multiplicative_score_bucket < 30 THEN '20~29'
        WHEN multiplicative_score_bucket < 40 THEN '30~39'
        WHEN multiplicative_score_bucket < 50 THEN '40~49'
        WHEN multiplicative_score_bucket < 60 THEN '50~59'
        WHEN multiplicative_score_bucket < 70 THEN '60~69'
        WHEN multiplicative_score_bucket < 80 THEN '70~79'
        WHEN multiplicative_score_bucket < 90 THEN '80~89'
        ELSE '90~99'
    END AS score_range,
    cnt,
    ROUND(pctr, 4) AS pctr,
    ROUND(probs_ctr_avg, 4) AS probs_ctr_avg,
    ROUND(probs_cvr_avg, 4) AS probs_cvr_avg,
    -- 校准偏差：PCTR - 预测CTR
    ROUND(pctr - probs_ctr_avg, 4) AS ctr_calibration_bias,
    ROUND(pcvr, 4) AS pcvr,
    ROUND(probs_cvr_avg - pcvr, 4) AS cvr_calibration_bias
FROM (
    SELECT
        GREATEST(0, LEAST(99, CAST((0.12 * probs_ctr * (1 + probs_cvr)) * 100 AS BIGINT))) AS multiplicative_score_bucket,
        COUNT(1) AS cnt,
        SUM(is_click) / COUNT(1) AS pctr,
        SUM(is_conversion) / NULLIF(SUM(is_click), 0) AS pcvr,
        AVG(probs_ctr) AS probs_ctr_avg,
        AVG(probs_cvr) AS probs_cvr_avg
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
    WHERE dt = '${bdp.system.bizdate}'
    GROUP BY multiplicative_score_bucket
) t
ORDER BY score_range;


-- ============================================================
-- 11. 与图2对比验证：乘法融合各bucket的CTR/CVR分布
-- 复现第二张分析图中的 orange(CTR) 和 gray(CVR) 曲线
-- ============================================================
SELECT
    bucket,
    cnt,
    ROUND(avg_probs_ctr * 100, 2) AS ctr_normalized,
    ROUND(avg_probs_cvr * 100, 2) AS cvr_normalized,
    ROUND(pctr * 100, 2) AS pctr_normalized,
    clicks,
    cnt AS samples
FROM (
    SELECT
        bucket,
        COUNT(1) AS cnt,
        AVG(probs_ctr) AS avg_probs_ctr,
        AVG(probs_cvr) AS avg_probs_cvr,
        SUM(is_click) AS clicks,
        SUM(is_click) * 1.0 / COUNT(1) AS pctr
    FROM (
        SELECT
            probs_ctr,
            probs_cvr,
            is_click,
            is_conversion,
            CAST((0.12 * probs_ctr * (1 + probs_cvr)) * 100 AS BIGINT) AS bucket
        FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v2
        WHERE dt = '${bdp.system.bizdate}'
    ) t
    WHERE bucket >= 0 AND bucket <= 24
    GROUP BY bucket
) t
ORDER BY bucket;
