-- ============================================================
-- DataWorks ODPS-SQL: Label 相关列分布分析
-- 表名: home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1df
-- 项目空间: mmb_sage (cn-shenzhen)
-- ============================================================

-- 第一步：查看表的 DDL 结构，确认 label 相关的列名
-- 在 DataWorks 中执行此查询，确认表结构和字段名称
DESCRIBE home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1df;

-- 第二步：统计总行数
SELECT
    COUNT(*) AS total_rows
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1df;

-- ============================================================
-- 第三步：Label 分布分析（根据实际字段名调整）
-- 常见的 label 相关字段可能包括:
-- - label (二分类标签)
-- - is_buy / clicked / converted (各种转化标签)
-- - ctr_label / cvr_label (CTR/CVR 预测标签)
-- - label_1h / label_3d / label_7d (多时间窗口标签)
-- 请根据实际情况替换以下字段名！
-- ============================================================

-- 3.1: Label 值分布（假设字段名为 'label'）
SELECT
    CASE
        WHEN label IS NULL THEN 'NULL'
        WHEN label = 0 THEN '0 (Negative)'
        WHEN label = 1 THEN '1 (Positive)'
        ELSE CAST(label AS VARCHAR)
    END AS label_value,
    COUNT(*) AS count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1df
WHERE label IS NOT NULL  -- 排除 NULL 值统计
GROUP BY label
ORDER BY count DESC;

-- 3.2: 如果有多个时间窗口的 label
-- 假设字段名为: label_1h, label_3d, label_7d
SELECT
    COUNT(*) AS total_rows,

    -- 1小时标签分布
    SUM(CASE WHEN label_1h IS NOT NULL THEN 1 ELSE 0 END) AS label_1h_not_null,
    SUM(CASE WHEN label_1h = 1 THEN 1 ELSE 0 END) AS label_1h_positive,
    SUM(CASE WHEN label_1h = 0 THEN 1 ELSE 0 END) AS label_1h_negative,
    ROUND(SUM(CASE WHEN label_1h = 1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN label_1h IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS label_1h_pos_pct,

    -- 3天标签分布
    SUM(CASE WHEN label_3d IS NOT NULL THEN 1 ELSE 0 END) AS label_3d_not_null,
    SUM(CASE WHEN label_3d = 1 THEN 1 ELSE 0 END) AS label_3d_positive,
    SUM(CASE WHEN label_3d = 0 THEN 1 ELSE 0 END) AS label_3d_negative,
    ROUND(SUM(CASE WHEN label_3d = 1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN label_3d IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS label_3d_pos_pct,

    -- 7天标签分布
    SUM(CASE WHEN label_7d IS NOT NULL THEN 1 ELSE 0 END) AS label_7d_not_null,
    SUM(CASE WHEN label_7d = 1 THEN 1 ELSE 0 END) AS label_7d_positive,
    SUM(CASE WHEN label_7d = 0 THEN 1 ELSE 0 END) AS label_7d_negative,
    ROUND(SUM(CASE WHEN label_7d = 1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(SUM(CASE WHEN label_7d IS NOT NULL THEN 1 ELSE 0 END), 0), 2) AS label_7d_pos_pct

FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1df;

-- ============================================================
-- 第四步：Label 分布可视化（用于理解数据）
-- ============================================================

-- 4.1: Label 直方图分布（连续型 label 场景）
-- 如果 label 是连续值而非 0/1
SELECT
    NTILE(10) OVER (ORDER BY label) AS decile,
    MIN(label) AS min_label,
    MAX(label) AS max_label,
    COUNT(*) AS count,
    ROUND(AVG(label), 4) AS avg_label
FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1df
WHERE label IS NOT NULL
GROUP BY NTILE(10) OVER (ORDER BY label)
ORDER BY decile;

-- 4.2: 不同时间窗口 Label 的相关性分析
SELECT
    COUNT(*) AS total,

    -- 双正 (1,1)
    SUM(CASE WHEN label_1h = 1 AND label_3d = 1 THEN 1 ELSE 0 END) AS both_positive,
    -- 1正3负 (1,0)
    SUM(CASE WHEN label_1h = 1 AND label_3d = 0 THEN 1 ELSE 0 END) AS one_pos_three_neg,
    -- 1负3正 (0,1)
    SUM(CASE WHEN label_1h = 0 AND label_3d = 1 THEN 1 ELSE 0 END) AS one_neg_three_pos,
    -- 双负 (0,0)
    SUM(CASE WHEN label_1h = 0 AND label_3d = 0 THEN 1 ELSE 0 END) AS both_negative

FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1df
WHERE label_1h IS NOT NULL AND label_3d IS NOT NULL;

-- ============================================================
-- 第五步：Label 缺失值分析
-- ============================================================

SELECT
    COUNT(*) AS total_rows,

    SUM(CASE WHEN label IS NULL THEN 1 ELSE 0 END) AS label_missing,
    ROUND(SUM(CASE WHEN label IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS label_missing_pct,

    SUM(CASE WHEN label_1h IS NULL THEN 1 ELSE 0 END) AS label_1h_missing,
    ROUND(SUM(CASE WHEN label_1h IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS label_1h_missing_pct,

    SUM(CASE WHEN label_3d IS NULL THEN 1 ELSE 0 END) AS label_3d_missing,
    ROUND(SUM(CASE WHEN label_3d IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS label_3d_missing_pct

FROM home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1df;

-- ============================================================
-- 使用说明
-- ============================================================
/*
在 DataWorks 中运行的步骤：
1. 打开 https://dataworks.data.aliyun.com/cn-shenzhen/datastudio?defaultProjectId=252434
2. 选择你的项目空间（mmb_sage）
3. 点击"新建查询"或打开已有的 SQL 查询窗口
4. 复制上述 SQL 代码，分块执行
5. 注意：
   - 首先执行 DESCRIBE 确认实际的 label 字段名
   - 然后根据实际字段名修改 SQL 中的字段引用
   - ODPS-SQL 语法可能与标准 SQL 略有差异
*/
