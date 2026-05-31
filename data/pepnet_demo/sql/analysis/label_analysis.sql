-- 维度 1：基础分布与“误杀”校验（验证漏洞 1）
-- 勘验逻辑：对比源表曝光 UV 和样本表 UV。如果样本表 UV 大幅低于源表，说明大量纯曝光用户被误杀。同时观察 CTR 是否在合理区间（电商信息流通常在 2%~10% 之间）。
-- 健康标准：sample_uv 应该非常接近 source_exposure_uv（误差 < 5%）。ctr 应符合业务大盘认知。
-- 1. 样本表基础指标
SELECT
    dt,
    COUNT(1) AS total_samples,
    COUNT(DISTINCT mmb_id) AS sample_uv,
    SUM(is_click) AS total_clicks,
    ROUND(SUM(is_click) / COUNT(1), 4) AS ctr,
    SUM(is_conversion) AS total_conversions,
    ROUND(SUM(is_conversion) / NULLIF(SUM(is_click), 0), 4) AS cvr
FROM home_flow_2604_ctrcvr_sorter_label_table_v3
WHERE dt = '${bdp.system.bizdate}'
GROUP BY dt;

-- 2. 源表曝光 UV (用于对比)
SELECT COUNT(DISTINCT mmb_id) AS source_exposure_uv
FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
WHERE dt = '${bdp.system.bizdate}' AND event = 'exposure';

-- 维度 2：归因膨胀校验（验证漏洞 2）
-- 勘验逻辑：对比样本表统计出的点击总数，与源表真实的点击日志总数。如果样本表点击数远大于源表，说明发生了“一点击多归因”。
-- 健康标准：sample_click_cnt 应 小于或等于 source_click_cnt（因为部分点击可能没有前置曝光，或者超出了 30 分钟归因窗口）。如果大于，必须修复 click_base 去重逻辑。
-- 样本表归因点击数
SELECT SUM(is_click) AS sample_click_cnt
FROM home_flow_2604_ctrcvr_sorter_label_table_v3
WHERE dt = '${bdp.system.bizdate}';
-- 源表真实点击数
SELECT COUNT(1) AS source_click_cnt
FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
WHERE dt = '${bdp.system.bizdate}' AND event = 'click';


-- 维度 3：T-1 修正效果校验（验证延迟反馈机制）
-- 勘验逻辑：对比 T-1 日“正常构建”和“修正构建”的 CVR。修正后的 CVR 应该略高，且新增的转化应该集中在 T 日的凌晨（延迟转化）。
-- 健康标准：修正构建的 cvr_cnt 应比正常构建高出 5% ~ 15%（取决于业务的转化延迟率）。
SELECT
    '正常构建' AS build_type,
    SUM(is_conversion) AS cvr_cnt,
    COUNT(DISTINCT IF(is_click=1, mmb_id, NULL)) AS click_uv
FROM home_flow_2604_ctrcvr_sorter_label_table_v3
WHERE dt = TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}','yyyymmdd'), -1, 'dd'), 'yyyymmdd')
-- 注意：这里需要你在正常构建时也保留一份快照，或者对比历史分区
UNION ALL
SELECT
    '修正构建' AS build_type,
    SUM(is_conversion) AS cvr_cnt,
    COUNT(DISTINCT IF(is_click=1, mmb_id, NULL)) AS click_uv
FROM home_flow_2604_ctrcvr_sorter_label_table_v3
WHERE dt = '${date_2}'; -- 修正构建产出的分区



-- 维度 4：时间窗口合理性校验（指导超参调整）
-- 勘验逻辑：分析“点击-曝光”和“转化-点击”的时间差分布。如果 95% 的点击发生在 5 分钟内，30 分钟的窗口可能引入了太多噪声；如果大量转化发生在 24 小时边缘，说明需要延长 CVR 窗口。
