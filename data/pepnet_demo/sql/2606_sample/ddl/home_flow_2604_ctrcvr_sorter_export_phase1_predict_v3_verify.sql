-- ============================================================
-- probs_ctr/probs_cvr 校准验证 SQL
-- 表: home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
-- 用途: 验证模型预测分数与样本真实点击率/转化率是否一致
-- ============================================================

-- ----------------------------
-- 1. 全局校准（整体 avg 对比）
-- ----------------------------
SELECT
    AVG(probs_ctr)                          AS avg_probs_ctr,
    AVG(is_click)                           AS avg_is_click,
    AVG(probs_ctr) - AVG(is_click)          AS ctr_gap,
    AVG(probs_cvr)                          AS avg_probs_cvr,
    AVG(is_conversion)                      AS avg_is_conversion,
    AVG(probs_cvr) - AVG(is_conversion)     AS cvr_gap,
    COUNT(*)                                AS total_samples,
    SUM(is_click)                           AS total_clicks,
    SUM(is_conversion)                      AS total_conversions
FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
WHERE dt = '20260604';   -- 按实际分区日期修改


-- ----------------------------
-- 2. 分桶校准（Calibration Curve）
-- ----------------------------

-- 2a. CTR 分桶校准
SELECT
    ctr_bucket,
    COUNT(*)                                    AS samples,
    ROUND(AVG(probs_ctr), 4)                   AS avg_probs_ctr,
    ROUND(AVG(is_click),  4)                   AS avg_is_click,
    ROUND(AVG(probs_ctr) - AVG(is_click), 4)   AS ctr_gap,
    ROUND(STDDEV(probs_ctr), 4)                AS probs_ctr_stddev
FROM (
    SELECT
        probs_ctr,
        is_click,
        CASE
            WHEN probs_ctr < 0.05 THEN '[0,  0.05)'
            WHEN probs_ctr < 0.10 THEN '[0.05, 0.10)'
            WHEN probs_ctr < 0.15 THEN '[0.10, 0.15)'
            WHEN probs_ctr < 0.20 THEN '[0.15, 0.20)'
            WHEN probs_ctr < 0.25 THEN '[0.20, 0.25)'
            WHEN probs_ctr < 0.30 THEN '[0.25, 0.30)'
            WHEN probs_ctr < 0.40 THEN '[0.30, 0.40)'
            WHEN probs_ctr < 0.50 THEN '[0.40, 0.50)'
            WHEN probs_ctr < 0.60 THEN '[0.50, 0.60)'
            ELSE '[0.60, 1.0]'
        END AS ctr_bucket
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
    WHERE dt = '20260604'
      AND probs_ctr IS NOT NULL
      AND is_click IS NOT NULL
) t
GROUP BY ctr_bucket
ORDER BY MIN(probs_ctr);


-- 2b. CVR 分桶校准
SELECT
    cvr_bucket,
    COUNT(*)                                       AS samples,
    ROUND(AVG(probs_cvr),  4)                     AS avg_probs_cvr,
    ROUND(AVG(is_conversion), 4)                  AS avg_is_conversion,
    ROUND(AVG(probs_cvr) - AVG(is_conversion), 4) AS cvr_gap,
    ROUND(STDDEV(probs_cvr), 4)                   AS probs_cvr_stddev
FROM (
    SELECT
        probs_cvr,
        is_conversion,
        CASE
            WHEN probs_cvr < 0.02 THEN '[0,  0.02)'
            WHEN probs_cvr < 0.05 THEN '[0.02, 0.05)'
            WHEN probs_cvr < 0.08 THEN '[0.05, 0.08)'
            WHEN probs_cvr < 0.10 THEN '[0.08, 0.10)'
            WHEN probs_cvr < 0.15 THEN '[0.10, 0.15)'
            WHEN probs_cvr < 0.20 THEN '[0.15, 0.20)'
            WHEN probs_cvr < 0.25 THEN '[0.20, 0.25)'
            WHEN probs_cvr < 0.30 THEN '[0.25, 0.30)'
            ELSE '[0.30, 1.0]'
        END AS cvr_bucket
    FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
    WHERE dt = '20260604'
      AND probs_cvr IS NOT NULL
      AND is_conversion IS NOT NULL
) t
GROUP BY cvr_bucket
ORDER BY MIN(probs_cvr);


-- ----------------------------
-- 3. 按 item_id 分组的校准（按场景验证）
-- ----------------------------
SELECT
    item_id,
    COUNT(*)                                      AS samples,
    ROUND(AVG(probs_ctr),    4)                   AS avg_probs_ctr,
    ROUND(AVG(is_click),       4)                 AS avg_is_click,
    ROUND(AVG(probs_ctr) - AVG(is_click), 4)      AS ctr_gap,
    ROUND(AVG(probs_cvr),    4)                   AS avg_probs_cvr,
    ROUND(AVG(is_conversion), 4)                  AS avg_is_conversion,
    ROUND(AVG(probs_cvr) - AVG(is_conversion), 4) AS cvr_gap
FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
WHERE dt = '20260604'
  AND item_id IS NOT NULL
GROUP BY item_id
ORDER BY samples DESC;


-- ----------------------------
-- 4. Brier Score（概率校准质量度量）
-- ----------------------------
SELECT
    AVG(POW(probs_ctr - is_click,  2))            AS brier_ctr,
    ROUND(POW(AVG(is_click),  2) * (1 - AVG(is_click)),  4)  AS brier_ctr_blind,
    AVG(POW(probs_cvr - is_conversion, 2))        AS brier_cvr,
    ROUND(POW(AVG(is_conversion), 2) * (1 - AVG(is_conversion)), 4) AS brier_cvr_blind,
    ROUND(
        (AVG(POW(probs_ctr - is_click,  2))
         - POW(AVG(is_click),  2) * (1 - AVG(is_click)))
        / NULLIF(POW(AVG(is_click),  2) * (1 - AVG(is_click)), 0),
        4
    ) AS brier_ctr_improvement,
    ROUND(
        (AVG(POW(probs_cvr - is_conversion, 2))
         - POW(AVG(is_conversion), 2) * (1 - AVG(is_conversion)))
        / NULLIF(POW(AVG(is_conversion), 2) * (1 - AVG(is_conversion)), 0),
        4
    ) AS brier_cvr_improvement
FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
WHERE dt = '20260604'
  AND probs_ctr IS NOT NULL
  AND probs_cvr IS NOT NULL;


-- ----------------------------
-- 5. CVR 根因诊断：logits 与 probs 映射关系
--    若 avg_logit_from_probs ≈ avg_logits_cvr → sigmoid 映射正确，问题在训练数据
--    若两者差距大 → sigmoid 后处理有 bug
-- ----------------------------
SELECT
    AVG(probs_cvr)                                    AS avg_probs_cvr,
    AVG(LOG(probs_cvr / (1 - probs_cvr)))             AS avg_logit_from_probs,
    AVG(logits_cvr)                                   AS avg_logits_cvr,
    COUNT(CASE WHEN probs_cvr > 0.9 THEN 1 END)       AS probs_gt_09_cnt,
    COUNT(*)                                          AS total
FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
WHERE dt = '20260604'
  AND probs_cvr IS NOT NULL
  AND probs_cvr > 0 AND probs_cvr < 1;


-- ----------------------------
-- 6. CVR 根因诊断：抽取 probs 与 label 差距最大的 top 20 样本
-- ----------------------------
SELECT
    item_id,
    ROUND(probs_ctr, 4)   AS probs_ctr,
    ROUND(probs_cvr, 4)   AS probs_cvr,
    ROUND(logits_ctr, 4)  AS logits_ctr,
    ROUND(logits_cvr, 4)  AS logits_cvr,
    is_click,
    is_conversion
FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
WHERE dt = '20260604'
ORDER BY ABS(probs_cvr - is_conversion) DESC
LIMIT 20;
