-- ============================================================
-- 训练数据诊断 SQL
-- 表: home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
-- 用途: 排查 CVR 预测系统性高估的根因
-- ============================================================


-- ----------------------------
-- Q1. 整体样本分布：CTR/CVR 正负比例
-- ----------------------------
SELECT
    COUNT(*)                                            AS total_samples,
    SUM(is_click)                                       AS click_count,
    SUM(is_conversion)                                  AS conversion_count,
    ROUND(SUM(is_click) * 1.0 / COUNT(*), 6)            AS train_ctr,
    ROUND(SUM(is_conversion) * 1.0 / COUNT(*), 6)       AS train_cvr,
    SUM(CASE WHEN request_id IS NOT NULL THEN 1 ELSE 0 END)   AS positive_samples,
    SUM(CASE WHEN request_id IS NULL THEN 1 ELSE 0 END)         AS negative_samples,
    ROUND(SUM(CASE WHEN request_id IS NOT NULL THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 6) AS positive_ratio
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '20260604';   -- 按实际分区日期修改


-- ----------------------------
-- Q2. 正负样本各自的 CTR/CVR 分布（验证 negative sampling 逻辑）
-- ----------------------------
SELECT
    CASE WHEN request_id IS NOT NULL THEN 'positive' ELSE 'negative' END AS sample_type,
    COUNT(*)                                                AS samples,
    ROUND(AVG(is_click), 6)                                 AS avg_is_click,
    ROUND(SUM(is_click) * 1.0 / COUNT(*), 6)                AS click_rate,
    ROUND(AVG(is_conversion), 6)                            AS avg_is_conversion,
    ROUND(SUM(is_conversion) * 1.0 / COUNT(*), 6)           AS conversion_rate
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '20260604'
GROUP BY
    CASE WHEN request_id IS NOT NULL THEN 'positive' ELSE 'negative' END;


-- ----------------------------
-- Q3. 按 item_id 分组：每个 item 的 label 分布
--     目的：找出「训练时转化率高、但评估时转化率极低」的 item
-- ----------------------------
SELECT
    __item_id__,
    COUNT(*)                                            AS samples,
    SUM(is_click)                                       AS clicks,
    SUM(is_conversion)                                  AS conversions,
    ROUND(SUM(is_conversion) * 1.0 / NULLIF(COUNT(*), 0), 4) AS item_conv_rate,
    ROUND(SUM(is_click) * 1.0 / NULLIF(COUNT(*), 0), 4)      AS item_click_rate
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '20260604'
GROUP BY __item_id__
HAVING COUNT(*) >= 10
ORDER BY item_conv_rate DESC
LIMIT 50;


-- ----------------------------
-- Q4. 按 cate_id_path 分组：品类维度的训练 CVR vs 预期 CVR 对比
--     判断偏差是否集中在特定品类
-- ----------------------------
SELECT
    cate_id_path,
    COUNT(*)                                             AS samples,
    ROUND(SUM(is_conversion) * 1.0 / COUNT(*), 4)         AS cate_train_cvr,
    ROUND(AVG(active_days), 1)                            AS avg_active_days
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '20260604'
  AND cate_id_path IS NOT NULL
  AND size(cate_id_path) > 0
GROUP BY cate_id_path
HAVING COUNT(*) >= 100
ORDER BY samples DESC
LIMIT 20;


-- ----------------------------
-- Q5. 时间窗口对齐检查：event_unix_time 分布
--     判断训练样本的曝光时间窗口是否与评估表一致
-- ----------------------------
SELECT
    COUNT(*)                                             AS total,
    MIN(event_unix_time)                                 AS min_event_time,
    MAX(event_unix_time)                                 AS max_event_time,
    ROUND(AVG(event_unix_time), 0)                       AS avg_event_time,
    FROM_UNIXTIME(CAST(MIN(event_unix_time) AS BIGINT))           AS min_time_str,
    FROM_UNIXTIME(CAST(MAX(event_unix_time) AS BIGINT))           AS max_time_str
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '20260604';


-- ----------------------------
-- Q6. 与 export 表交叉验证：同一 dt 下，训练集 vs 预测集的转化差异
--     如果训练集 conversion_rate 明显高于预测集，说明标签定义或统计窗口不一致
-- ----------------------------
SELECT
    'train' AS data_source,
    COUNT(*)                                              AS samples,
    ROUND(SUM(is_conversion) * 1.0 / COUNT(*), 6)         AS conversion_rate
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '20260604'

UNION ALL

SELECT
    'predict' AS data_source,
    COUNT(*)                                              AS samples,
    ROUND(SUM(is_conversion) * 1.0 / COUNT(*), 6)         AS conversion_rate
FROM home_flow_2604_ctrcvr_sorter_export_phase1_predict_v3
WHERE dt = '20260604';


-- ----------------------------
-- Q7. 训练样本中 is_conversion=1 但 request_id=NULL 的异常样本
--     理论上 negative sampling 的样本 request_id=NULL 且 is_conversion=0
--     如果出现 conversion=1 且 request_id=NULL，说明存在数据污染
-- ----------------------------
SELECT
    COUNT(*)                                              AS abnormal_count,
    COUNT(DISTINCT __item_id__)                           AS distinct_items
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '20260604'
  AND request_id IS NULL
  AND is_conversion = 1;


-- ----------------------------
-- Q8. 采样策略检查：正负样本比例是否经过人工调整
--     如果正负样本比例严重失衡（如 1:3 或更高），会导致先验概率偏移
-- ----------------------------
SELECT
    ROUND(
        SUM(CASE WHEN request_id IS NOT NULL THEN 1 ELSE 0 END) * 1.0
        / NULLIF(SUM(CASE WHEN request_id IS NULL THEN 1 ELSE 0 END), 0),
        4
    ) AS pos_neg_ratio,
    SUM(CASE WHEN request_id IS NOT NULL THEN 1 ELSE 0 END) AS positive_cnt,
    SUM(CASE WHEN request_id IS NULL THEN 1 ELSE 0 END)     AS negative_cnt,
    COUNT(*)                                                 AS total
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3
WHERE dt = '20260604';
