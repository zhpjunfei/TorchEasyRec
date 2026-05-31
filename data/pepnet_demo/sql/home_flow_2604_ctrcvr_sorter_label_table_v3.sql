set odps.sql.type.system.odps2=true;
CREATE TABLE IF NOT EXISTS home_flow_2604_ctrcvr_sorter_label_table_v3
(
    event_unix_time bigint
    ,__item_id__ string
    ,item_id string
    ,scene string
    ,__mmb_id__ string
    ,mmb_id string
    ,request_id string
    ,page string
    ,day_h bigint COMMENT 'event_time在当天的第几小时'
    ,week_day bigint COMMENT 'event_time在一周得第几天'
    ,is_click BIGINT
    ,is_conversion BIGINT
)
PARTITIONED BY
(
    dt string
)
LIFECYCLE 90
;



-- ==========================================
-- 单脚本双模式：正常构建 dt=T + 修正构建 dt=T-1
--
-- T+1 管线，${bdp.system.bizdate} = T
-- ① 正常：产出 dt=T，转化只读当天
-- ② 修正：产出 dt=T-1，转化读到 T（此时 T 已存在）
-- ==========================================

-- ==========================================
-- ① 正常构建：产出 dt=T 分区
-- ==========================================
WITH exposure_base AS (
    SELECT  event_unix_time, request_id, mmb_id, item_id, scene, page, day_h, week_day,
            ROW_NUMBER() OVER (PARTITION BY request_id, item_id ORDER BY event_unix_time) AS rn
    FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE dt = '${bdp.system.bizdate}'
        AND event = 'exposure'
        AND request_id IS NOT NULL
),
click_base AS (
    -- 去重：同用户对同商品一天多次点击只保留首次，防止 JOIN 倾斜
    SELECT mmb_id, item_id, click_time
    FROM (
        SELECT  mmb_id, item_id, event_unix_time AS click_time,
                ROW_NUMBER() OVER (PARTITION BY mmb_id, item_id ORDER BY event_unix_time) AS rn
        FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
        WHERE dt = '${bdp.system.bizdate}' AND event = 'click'
    ) t WHERE rn = 1
),
conversion_base AS (
    SELECT  mmb_id, item_id, event_unix_time AS conversion_time
    FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE dt = '${bdp.system.bizdate}'
        AND event = 'conversion'
),
user_filter AS (
    -- 防刷：排除单日曝光量过大的用户（爬虫/刷子）
    -- 从 exposure_base 统计，而非 click_base，以保留纯曝光负样本
    -- 当天曝光量 >= 3000 视为极端异常用户（爬虫/刷子）
    SELECT mmb_id FROM exposure_base GROUP BY mmb_id HAVING COUNT(1) < 3000
),
exposure_deduped AS (
    SELECT * FROM exposure_base WHERE rn = 1
)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_label_table_v3 PARTITION (dt = '${bdp.system.bizdate}')
SELECT
    exp.event_unix_time, exp.item_id, exp.item_id AS __item_id__, exp.scene,
    exp.mmb_id, exp.mmb_id AS __mmb_id__, exp.request_id, exp.page, exp.day_h, exp.week_day,
    MAX(IF(clk.click_time IS NOT NULL, 1, 0)) AS is_click,
    MAX(IF(clk.click_time IS NOT NULL AND cv.conversion_time IS NOT NULL
           AND cv.conversion_time >= clk.click_time
           AND cv.conversion_time < clk.click_time + 86400, 1, 0)) AS is_conversion
FROM exposure_deduped exp
LEFT JOIN click_base clk
    ON exp.mmb_id = clk.mmb_id AND exp.item_id = clk.item_id
    AND clk.click_time >= exp.event_unix_time
    AND clk.click_time < exp.event_unix_time + 1800
LEFT JOIN conversion_base cv
    ON exp.mmb_id = cv.mmb_id AND exp.item_id = cv.item_id
    AND cv.conversion_time >= exp.event_unix_time
INNER JOIN user_filter uaf ON exp.mmb_id = uaf.mmb_id
GROUP BY exp.event_unix_time, exp.request_id, exp.mmb_id, exp.item_id,
         exp.scene, exp.page, exp.day_h, exp.week_day
;

-- ==========================================
-- ② 修正构建：产出 dt=T-1 分区（转化多读一天 T）
-- ==========================================
WITH exposure_base AS (
    SELECT  event_unix_time, request_id, mmb_id, item_id, scene, page, day_h, week_day,
            ROW_NUMBER() OVER (PARTITION BY request_id, item_id ORDER BY event_unix_time) AS rn
    FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE dt = TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}', 'yyyymmdd'), -1, 'dd'), 'yyyymmdd')
        AND event = 'exposure'
        AND request_id IS NOT NULL
),
click_base AS (
    SELECT mmb_id, item_id, click_time
    FROM (
        SELECT  mmb_id, item_id, event_unix_time AS click_time,
                ROW_NUMBER() OVER (PARTITION BY mmb_id, item_id ORDER BY event_unix_time) AS rn
        FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
        WHERE dt = TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}', 'yyyymmdd'), -1, 'dd'), 'yyyymmdd')
            AND event = 'click'
    ) t WHERE rn = 1
),
conversion_base AS (
    SELECT  mmb_id, item_id, event_unix_time AS conversion_time
    FROM home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE dt >= TO_CHAR(DATEADD(TO_DATE('${bdp.system.bizdate}', 'yyyymmdd'), -1, 'dd'), 'yyyymmdd')
        AND dt <= '${bdp.system.bizdate}'
        AND event = 'conversion'
),
user_filter AS (
    SELECT mmb_id FROM exposure_base GROUP BY mmb_id HAVING COUNT(1) < 3000
),
exposure_deduped AS (
    SELECT * FROM exposure_base WHERE rn = 1
)
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_label_table_v3 PARTITION (
    dt = '${date_2}'
)
SELECT
    exp.event_unix_time, exp.item_id, exp.item_id AS __item_id__, exp.scene,
    exp.mmb_id, exp.mmb_id AS __mmb_id__, exp.request_id, exp.page, exp.day_h, exp.week_day,
    MAX(IF(clk.click_time IS NOT NULL, 1, 0)) AS is_click,
    MAX(IF(clk.click_time IS NOT NULL AND cv.conversion_time IS NOT NULL
           AND cv.conversion_time >= clk.click_time
           AND cv.conversion_time < clk.click_time + 86400, 1, 0)) AS is_conversion
FROM exposure_deduped exp
LEFT JOIN click_base clk
    ON exp.mmb_id = clk.mmb_id AND exp.item_id = clk.item_id
    AND clk.click_time >= exp.event_unix_time
    AND clk.click_time < exp.event_unix_time + 1800
LEFT JOIN conversion_base cv
    ON exp.mmb_id = cv.mmb_id AND exp.item_id = cv.item_id
    AND cv.conversion_time >= exp.event_unix_time
INNER JOIN user_filter uaf ON exp.mmb_id = uaf.mmb_id
GROUP BY exp.event_unix_time, exp.request_id, exp.mmb_id, exp.item_id,
         exp.scene, exp.page, exp.day_h, exp.week_day
;
