set odps.sql.type.system.odps2=true;

-- ==========================================
-- 1. 曝光主表 (粒度: request_id + item_id)
-- ==========================================
WITH exposure_base AS (
    SELECT
        event_unix_time,
        request_id,
        mmb_id,
        item_id,
        scene,
        page,
        day_h,
        week_day,
        -- 防止同一个 request 下同一个 item 重复曝光，取时间最早的一条
        ROW_NUMBER() OVER(PARTITION BY request_id, item_id ORDER BY event_unix_time) as rn
    FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE   dt = '${bdp.system.bizdate}'
    AND     event = 'exposure'
    AND     request_id IS NOT NULL
),

-- ==========================================
-- 2. 行为表 (点击与转化)
-- ==========================================
action_base AS (
    SELECT
        mmb_id,
        item_id,
        event,
        event_unix_time as action_time
    FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE   dt = '${bdp.system.bizdate}'
    AND     event IN ('click', 'conversion')
),

-- ==========================================
-- 3. 用户活跃度过滤 (保留原逻辑中的防刷单机制)
-- ==========================================
user_active_filter AS (
    SELECT mmb_id
    FROM action_base
    WHERE event = 'click'
    GROUP BY mmb_id
    HAVING COUNT(1) < 100 -- 过滤掉当天点击超过100次的爬虫/刷单/极度活跃用户
)

-- ==========================================
-- 4. 最终样本拼接与归因
-- ==========================================
INSERT OVERWRITE TABLE home_flow_2604_ctrcvr_sorter_label_table_v1 PARTITION (dt = '${bdp.system.bizdate}')
SELECT
    exp.event_unix_time,
    exp.item_id,
    exp.item_id AS __item_id__,
    exp.scene,
    exp.mmb_id,
    exp.mmb_id AS __mmb_id__,
    exp.request_id,
    exp.page,
    exp.day_h,
    exp.week_day,
    -- 归因逻辑：曝光后 24 小时内是否有点击
    MAX(IF(act_click.event = 'click' AND act_click.action_time >= exp.event_unix_time
           AND act_click.action_time <= exp.event_unix_time + 86400, 1, 0)) AS is_click,
    -- 归因逻辑：点击后 24 小时内是否有转化 (严谨的 CTCVR 逻辑)
    MAX(IF(act_conv.event = 'conversion' AND act_conv.action_time >= exp.event_unix_time
           AND act_conv.action_time <= exp.event_unix_time + 86400, 1, 0)) AS is_conversion
FROM    exposure_base exp
-- 关联点击行为
LEFT JOIN action_base act_click
ON      exp.mmb_id = act_click.mmb_id AND exp.item_id = act_click.item_id AND act_click.event = 'click'
-- 关联转化行为
LEFT JOIN action_base act_conv
ON      exp.mmb_id = act_conv.mmb_id AND exp.item_id = act_conv.item_id AND act_conv.event = 'conversion'
-- 关联活跃度过滤表
INNER JOIN user_active_filter uaf
ON      exp.mmb_id = uaf.mmb_id
WHERE   exp.rn = 1  -- 去重：同一个 request 下同一个 item 只保留一条
GROUP BY
    exp.event_unix_time, exp.request_id, exp.mmb_id, exp.item_id,
    exp.scene, exp.page, exp.day_h, exp.week_day
;
