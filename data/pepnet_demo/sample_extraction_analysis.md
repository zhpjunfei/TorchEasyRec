# 样本提取分析 & 优化

## 原始 SQL

`sql/home_flow_2604_ctrcvr_sorter_label_table_v1.sql`

```sql
WITH ctr_label AS (
    SELECT  MIN(event_unix_time) AS event_unix_time
            ,item_id, item_id AS __item_id__
            ,mmb_id, mmb_id AS __mmb_id__
            ,MAX(page) AS page, MAX(day_h) AS day_h, MAX(week_day) AS week_day
            ,MAX(IF(event = 'exposure',1,0)) AS is_exposure
            ,MAX(IF(event = 'click',1,0)) AS is_click
            ,MAX(IF(event = 'conversion',1,0)) AS is_conversion
    FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
    WHERE   dt = '${bdp.system.bizdate}'
    GROUP BY item_id, mmb_id
)
SELECT  sq0.*, sq1.scene, sq1.request_id
FROM    (
            SELECT  *
                    ,SUM(is_click) OVER (PARTITION BY mmb_id ORDER BY event_unix_time
                        ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING) AS click_cnt
                    ,SUM(is_click) OVER (PARTITION BY mmb_id) AS click_num
            FROM    ctr_label
            WHERE   is_exposure > 0 AND is_click >= is_conversion
        ) sq0
LEFT JOIN (
            SELECT  mmb_id, item_id, request_id, scene
                    ,ROW_NUMBER() OVER (PARTITION BY mmb_id,item_id ORDER BY event_unix_time) AS rnk
            FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
            WHERE   dt = '${bdp.system.bizdate}'
              AND   event = 'exposure' AND request_id IS NOT NULL
        ) sq1
ON  sq0.mmb_id = sq1.mmb_id AND sq0.item_id = sq1.item_id
WHERE   sq0.click_cnt > 0 AND sq0.click_num < 100
  AND   sq1.rnk = 1 AND sq1.request_id IS NOT NULL
;
```

### 原始方案的问题

| 问题                                     | 级别 | 说明                                                                                                        |
| ---------------------------------------- | :--: | ----------------------------------------------------------------------------------------------------------- |
| `GROUP BY (mmb_id, item_id)` 聚合        |  🔴  | 每天每(user,item)只有 1 行，同一天多次曝光的负样本丢失                                                      |
| `click_cnt > 0` 时序过滤                 |  🟡  | 只保留"点击附近"的未点击商品，模型训练时见的全是 hard negatives，线上推理时大量 easy negatives 没训练过     |
| `request_id` 通过 (mmb_id, item_id) 反查 |  🟡  | 如果同一天同(user,item)有多次曝光，LEFT JOIN 只能拿到第 1 次曝光的 request_id，其他曝光行的 request_id 错配 |
| 标签按天 MAX 聚合                        |  🟢  | 同一天内 曝光→点击→二次曝光，第二次曝光本应是负样本但被 MAX 归为正样本。场景较少，影响有限                  |
| `LEFT JOIN` 变 INNER JOIN                |  🟢  | `sq1.rnk=1 AND sq1.request_id IS NOT NULL` 丢掉无 bhv 匹配的行，但 bhv 表通常是全量的                       |

### click_cnt > 0 的工作机制

```sql
SUM(is_click) OVER (
  PARTITION BY mmb_id
  ORDER BY event_unix_time
  ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING
) AS click_cnt
```

操作对象：按天 `MIN(event_unix_time)` 排序的 (user, item) 行序列。

例：用户当天曝光商品序列 A(click)→B→C→D：

| 商品 |  click_cnt   |        保留？        |
| ---- | :----------: | :------------------: |
| A    | (none+1+0)=1 |    ✅ 自己有点击     |
| B    |  (1+0+0)=1   | ✅ 在 A 后面（相邻） |
| C    |  (0+0+0)=0   |     ❌ 离 A 太远     |
| D    | (0+0+none)=0 |     ❌ 离 A 太远     |

如果用户点击稀疏（每天 1-2 个点击），大部分行被过滤。这是一种**时序难例负采样**。

### 对 PEPNet_v2 的潜在压制

`click_cnt > 0` 过滤后，训练数据特征是：

- **所有负样本都是 hard negatives**（与正样本极其相似）
- **样本多样性低**

这可能导致 PEPNet_v2 的 **EPNet MoE gate 坍缩**——gate 需要多样化的输入模式来学习路由，如果所有输入都是"点击附近的商品"，gate 退化到所有样本路由到同一个 expert，MoE 的多 expert 冗余变成纯噪声。相比之下 v1c 的 DBMtl 共享 MLP 对这种数据分布更鲁棒。

## 优化方案对比

### v1（new.sql）

`sql/home_flow_2604_ctrcvr_sorter_label_table_new.sql`

| 改进                | 说明                                                        |
| ------------------- | ----------------------------------------------------------- |
| ✅ 保留逐条曝光     | 去掉 GROUP BY，每 (request_id, item_id) 1 行                |
| ✅ 移除 click_cnt>0 | 保留全量曝光，模型看到完整分布                              |
| ✅ 点击 30 分钟归因 | `BETWEEN exp_time AND exp_time + 1800`                      |
| ✅ 转化点击后 24h   | `BETWEEN click_time AND click_time + 86400`，正确 ESMM      |
| ✅ 跨天转化回看     | 转化表读 `dt >= bizdate-1`                                  |
| ❌ 点击 GROUP BY    | `GROUP BY mmb_id, item_id` 导致同一天第二次曝光点击归因失败 |
| ❌ 无去重           | 无 ROW_NUMBER，同 request 同 item 可能出现重复              |
| ❌ 新表 v2          | 需改管线代码                                                |
| ❌ 丢失 page/day_h  | 字段少，但下游可能需要                                      |

### v2（new2.sql）

`sql/home_flow_2604_ctrcvr_sorter_label_table_new2.sql`

| 改进                           | 说明                                                   |
| ------------------------------ | ------------------------------------------------------ |
| ✅ ROW_NUMBER 去重             | `PARTITION BY request_id, item_id` 严谨                |
| ✅ 写原表 v1                   | 下游零改动                                             |
| ✅ 全字段保留                  | page, day_h, week_day, __item_id__, __mmb_id__         |
| ✅ LEFT JOIN + MAX 无 GROUP BY | 所有点击/转化事件独立判断，不漏标                      |
| ❌ 点击窗口 24h                | 太宽松，可能归因非因果点击                             |
| ❌ 转化从曝光算                | `BETWEEN exp_time AND exp_time + 86400`，ESMM 语义错误 |
| ❌ 无跨天回看                  | 当天曝光、次日转化的样本转化漏标                       |

### v3（融合版 ✅ 推荐）

`sql/home_flow_2604_ctrcvr_sorter_label_table_v3.sql`

```
取 new2 的框架（ROW_NUMBER 去重、写原表、全字段、无 GROUP BY）
          +
取 new 的归因（点击 30min、转化点击后 24h）
          +
单脚本双 INSERT：正常 dt=T + 修正 dt=T-1
```

| 维度          | 方案                                                                                      |
| ------------- | ----------------------------------------------------------------------------------------- |
| 曝光去重      | `ROW_NUMBER() OVER (PARTITION BY request_id, item_id)`                                    |
| 点击去重      | `ROW_NUMBER() OVER (PARTITION BY mmb_id, item_id)` 保留首次点击，防止 JOIN 倾斜           |
| 转化去重      | 无。同天同用户同商品不会多次转化                                                          |
| 写表          | `_v3` 新表，独立于线上 \_v1                                                               |
| 字段          | page, day_h, week_day, __item_id__, __mmb_id__ 全部保留                                   |
| 点击归因      | **30 分钟窗口**（曝光后 30min 内的点击才归因）                                            |
| 转化归因      | **点击后 24 小时**（`cv.conversion_time >= clk.click_time AND < clk.click_time + 86400`） |
| 转化跨天      | 通过双模式解决（见下文）                                                                  |
| 点击 GROUP BY | 无。每条曝光独立 LEFT JOIN 点击事件，不聚合不漏标                                         |
| 转化 JOIN     | 无 GROUP BY，`LEFT JOIN + MAX(IF(...))` 处理时间窗口                                      |
| 用户过滤      | 从 `exposure_base` 统计曝光量，`HAVING COUNT(1) < 3000`（保留纯曝光负样本）               |

### 双模式修正跨天转化（单脚本双 INSERT ✅）

T+1 管线下，构建 `dt=T` 时 `dt=T+1` 分区不存在，跨天转化必然漏标。

**单脚本双 INSERT**：`v3.sql` 包含两个独立的 WITH+INSERT 块，一次执行同时产出 `dt=T` 和 `dt=T-1`：

|    构建    | 产出分区 | exposure/click 读取 |    conversion 读取    |
| :--------: | :------: | :-----------------: | :-------------------: |
| **① 正常** |  `dt=T`  |       `dt=T`        |        `dt=T`         |
| **② 修正** | `dt=T-1` |      `dt=T-1`       | `dt=T-1` 到 `dt=T` ✅ |

**修正的场景**：

```
                   dt=T-1                  dt=T (T+1 时已存在)
                    │                       │
曝光 T-1 23:50 ─────┤
点击 T   00:10 ─────┼──────────────────────┤
转化 T   20:00 ─────┼──────────────────────┤
                    │                       │
 正常构建: conv 只读到 T-1 → 转化在 T 分区 → ❌ 漏标
 修正构建: conv 读到 T     → 转化被捕获   → ✅ 追回
```

### 转换归因验证

```
曝光 t=0h → 第 1 次点击 t=0.2h → 第 2 次点击 t=1h → 转化 t=23h

v1 (GROUP BY click, MIN click_time=0.2h):
  → 转化 t=23h, click_time+24h=24.2h → in window ✅
  → 但第二次点击(1h)被 GROUP BY 丢失

v2 (转化从曝光算 24h):
  → 转化 t=23h, exposure+24h=24h → in window ✅
  → 但如果转化在 26h（点击后 2h）, exposure+24h=24h → out ❌

v3 (无 GROUP BY, 逐条判断):
  → click1(0.2h)+conv=23h: 23-0.2=22.8h < 24h ✅
  → click2(1h)+conv=23h: 23-1=22h < 24h ✅
  → MAX=1 ✅ 正确归因
```

## 各版 SQL 文件

| 文件              | 说明                                                                             |     状态      |
| ----------------- | -------------------------------------------------------------------------------- | :-----------: |
| `sql/...v1.sql`   | 原始版：GROUP BY + click_cnt>0                                                   |   当前线上    |
| `sql/...new.sql`  | v1 改进版：逐条曝光 + 30min+24h 归因，但点击 GROUP BY 漏标 + 新表                |   ❌ 有 Bug   |
| `sql/...new2.sql` | v2 改进版：ROW_NUMBER + LEFT JOIN + 写原表，但转化窗口不对                       | 🟡 转化归因错 |
| `sql/...v3.sql`   | **融合版**：单脚本双 INSERT（正常 dt=T + 修正 dt=T-1），归因正确 + 独立新表 \_v3 |    ✅ 推荐    |
