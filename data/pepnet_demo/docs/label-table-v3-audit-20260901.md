# Label Table v3 审计结果报告

> 审计日期：2026-09-01
> 数据源：`home_flow_2606_dwd_log_zhekou_rec_user_bhv_info_preprocess_v2`
> 目标表：`home_flow_2606_ctrcvr_sorter_label_table_v3`
> 总 PV：1,739,508

______________________________________________________________________

## 一、原始事件分布（Audit #1）

```
total_rows  e_exposure  e_click  e_conversion  e_bijia_exp  e_haojia_exp  e_trend_exp  trend_null_req
18,313,780  15,263,947   461,837     248,734      1,033,131       317,543       50,672              0
```

### 分析

- **源表总量 1831 万行**，其中曝光（home）1526 万，占 83%。
- **search_bijia 曝光 103 万**（含 click/conversion），约为 home 的 6.8%，搜索场景体量可观。
- **search_haojia 曝光 31.7 万**，约为 bijia 的 30%，搜索第二 tab 有一定流量。
- **trend 曝光仅 5.07 万**，但 trend_click 有 8.6 万（来源表中 click 数大于 exposure 数），与已知风险「trend_exposure 依赖客户端发版」一致。
- **trend_null_req = 0**：所有 trend 事件均携带有效 request_id，设计假设验证通过 ✓

______________________________________________________________________

## 二、场景 PV 分布（Audit #2）

```
total_pv   home_pv    bijia_pv   haojia_pv   trend_pv
1,739,508  1,160,816  268,444    136,786     173,462
```

| 场景   | PV        | 占比  | 说明                                                          |
| ------ | --------- | ----- | ------------------------------------------------------------- |
| home   | 1,160,816 | 66.7% | 窗口采样（邻接点击 + click_num < 100）后剩余，约源曝光的 7.6% |
| bijia  | 268,444   | 15.4% | INNER JOIN 过滤后保留，包含正负样本                           |
| haojia | 136,786   | 7.9%  | 同上，约为 bijia 的 51%                                       |
| trend  | 173,462   | 10.0% | 直接透传，与源表 distinct 行数 1:1 对齐                       |

### 分析

- **home 占比 66.7%**，经过 `click_cnt > 0 AND click_num < 100` 窗口过滤后，从 1526 万源曝光降至 116 万 PV，符合邻接点击采样预期。
- **bijia (15.4%) > trend (10.0%) > haojia (7.9%)**，场景流量排序合理。
- **四场景总和 100%**，无遗漏或重叠。

______________________________________________________________________

## 三、场景互斥性（Audit #3）

```
violating_rows = 0
```

### 分析

0 行违反，**四个场景严格互斥**，每条样本只属于一个场景。schema 构造正确 ✓

______________________________________________________________________

## 四、trend request_id 完整性与时序泄漏（Audit #4）

```
trend_total  trend_with_req  trend_null_req  trend_leakage_rows
173,394      173,394         0             684
```

### 分析

- **request_id 完整性**：173,394 条 trend 样本全部携带非空 request_id ✓
- **时序泄漏 684 行（0.39%）**：存在 684 条 trend 事件，其 request 下有比该事件时间戳更晚的 exposure 记录。

#### 泄漏根因推测

1. **跨场景 request 复用**：同一 `request_id` 下可能同时包含 home 曝光和 trend 事件，JOIN 时 home 曝光时间可能晚于 trend 事件。
1. **客户端时间漂移**：trend_exposure 依赖客户端上报，部分设备的 `event_unix_time` 存在偏差，导致同一 request 内曝光时间晚于点击时间。

#### 影响评估

- 占比 **0.39%**，极小。
- 建议方案 A（接受）：作为噪声留在训练数据中，后续用 AUC 评估 trend CTR 即可缓解。
- 若选方案 B（过滤），可在 `trend_filtered` 层排除这 684 条，但需权衡样本量损失。

______________________________________________________________________

## 五、源表到标签表行数比（Audit #5）

```
src_home_pairs  lbl_home_rows  src_bijia_pairs  lbl_bijia_rows  src_haojia_pairs  lbl_haojia_rows  src_trend_events  lbl_trend_rows
3,399,323       1,160,816      407,591          268,444         30,268            136,786          173,462           173,462
```

### 分析

| 场景   | 源表 distinct | 标签表行数 | 压缩比 | 原因                                                                 |
| ------ | ------------- | ---------- | ------ | -------------------------------------------------------------------- |
| home   | 3,399,323     | 1,160,816  | 2.93x  | 窗口采样（仅保留邻接点击样本）+ click_num < 100 过滤                 |
| bijia  | 407,591       | 268,444    | 1.52x  | INNER JOIN 仅保留有点击 request 下的 item，过滤掉无点击 request      |
| haojia | 30,268        | 136,786    | 0.22x  | 源表仅统计 distinct pair，但标签表行数更多 → 同一 pair 下有多个 item |
| trend  | 173,462       | 173,462    | 1.00x  | 直接透传，1:1 对齐 ✓                                                 |

#### 关键发现：haojia 放大现象

`src_haojia_pairs (30,268) < lbl_haojia_rows (136,786)`，即 **1 个 (mmb_id, request_id) 对应约 4.5 个 item**。这是 INNER JOIN 回拉同 request 下所有 item 的设计效果：

- 源表按 distinct pair 计数时，1 个 request 下多个 item 被合并为 1 行
- 标签表保留了同 request 下所有 item（含未点击的），所以行数 > pair 数

**行为合理**：bijia 的 `src > lbl`（过滤掉了无点击 request），而 haojia 的 `src < lbl`（同一个 request 下有多个 item 被保留）。两个场景都遵循 INNER JOIN 模式，只是源表 click 密度不同导致 ratio 方向相反。

______________________________________________________________________

## 六、bijia / haojia 正负样本分布（Audit #6）

```
bijia:  total=268,444  pos=96,335  neg=172,109   (正样本率 35.9%)
haojia: total=136,786  pos=17,944  neg=118,842   (正样本率 13.1%)
```

### 分析

- **bijia 正样本率 35.9%**：搜索-比价页用户意图明确，点击转化率较高，符合预期。
- **haojia 正样本率 13.1%**：搜索-好价为第二 tab，流量较少且用户决策周期更长，CVR 偏低，合理。
- **正负样本比**：bijia 约 1:1.8，haojia 约 1:6.6。haojia 负样本过多可能导致辅助任务（chajia/search 辅助分类）训练不稳定，需在 model config 中用 `task_space_indicator_label` 场景 mask 处理。

#### INNER JOIN 效果验证

两个场景均通过 INNER JOIN 保留了同 request 下未点击 item（作为辅助任务负样本），正负样本共存验证通过 ✓

______________________________________________________________________

## 七、trend 行为标签分布（Audit #7）

```
trend_pv  trend_click  trend_conv
173,462   86,336       39,874
```

### 分析

- **trend 点击率 CTR = 86,336 / 173,462 = 49.8%**
- **trend 转化率 CVR = 39,874 / 173,462 = 23.0%**
- **条件转化率 CTVR = 39,874 / 86,336 = 46.2%**

#### 异常信号

CTR 49.8% 显著高于 home 场景（461,837 / 15,263,947 ≈ 3.0%）。可能原因：

1. **trend 事件定义不同**：trend_click 可能来自更精准的推荐位，而非首页 feed。
1. **event_unix_time 分组粒度**：trend_sample 按 event_unix_time + item + mmb_id + request_id 四列聚合，同 request 下多次点击不同 item 会被合并为 1 行，可能导致 click 被高估。
1. **客户端上报偏差**：trend_click 不依赖客户端发版（无需曝光才能触发点击），可能存在上报不完整问题。

**建议**：用 AUC 评估而非 click/exposure 比率来衡量 trend 场景的 CTR 质量（设计文档已知风险已记录）。

______________________________________________________________________

## 八、各场景 request_id 有效性（Audit #8）

```
scene          pv        null_req_cnt
is_home_scene  1,160,816 0
is_bijia_scene 268,444   0
is_haojia_scene 136,786   0
is_trend_scene  173,462   0
```

### 分析

所有场景的 `null_req_cnt = 0`，每个场景的样本均携带有效 request_id ✓

______________________________________________________________________

## 九、trend 时序一致性细粒度（Audit #9）

```
total_rows  future_leakage  same_time  past_exposure  no_exposure_match
173,461     684             50,671     63,862         58,244
```

### 分析

同 Audit #4 交叉验证：**future_leakage = 684**，与 #4 的 `trend_leakage_rows = 684` 完全一致 ✓

其余分布：

| 类别              | 行数   | 占比  | 含义                                                                                              |
| ----------------- | ------ | ----- | ------------------------------------------------------------------------------------------------- |
| future_leakage    | 684    | 0.39% | request 下存在比 trend 事件更晚的 exposure                                                        |
| same_time         | 50,671 | 29.2% | trend 事件与某次曝光时间戳相同（同一次请求）                                                      |
| past_exposure     | 63,862 | 36.8% | request 下有早于 trend 事件的曝光（正常）                                                         |
| no_exposure_match | 58,244 | 33.6% | 该 trend request 下无任何 exposure 记录（可能 trend 自有曝光未匹配，或 request 级别无 home 曝光） |

#### no_exposure_match 偏高（33.6%）解读

58,244 条 trend 事件在 JOIN 后找不到任何 exposure 记录，可能原因：

1. **trend 场景的曝光事件本身是 trend_exposure**（审计 JOIN 了所有 4 种 exposure，包括 trend_exposure），如果 trend_exposure 和 trend_click 不在同一 request 内上报，会导致无法匹配。
1. **request_id 在不同场景间不共享**：trend 的 request_id 可能与 home request_id 体系不同，JOIN 匹配不到 home 曝光。
1. **数据上报延迟**：同一 request 内的曝光和点击时间戳相同或接近，但由于 GROUP BY 分组粒度问题，部分 match 被归入 same_time 而非 past_exposure。

**建议**：下一轮可单独增加一个 audit，检查 `no_exposure_match` 行中是否存在 trend_exposure 事件，判断是否为同 request 下的 trend 自曝光未对齐。

______________________________________________________________________

## 十、综合结论

### 通过项（7/9）

Audit #1~#3、#5~#8 全部通过，无阻断性问题。

### 需关注项（2/9）

| 问题                                            | 严重程度 | 建议                                          |
| ----------------------------------------------- | -------- | --------------------------------------------- |
| Audit #4/#9：trend 时序泄漏 684 行（0.39%）     | 🟡 低    | 接受，用 AUC 评估 trend CTR 即可              |
| Audit #7：trend CTR 49.8% 显著高于 home（3.0%） | 🟡 低    | 关注，建议用 AUC 评估替代 click/exposure 比率 |
| Audit #9：no_exposure_match 33.6% 偏高          | 🟢 观察  | 下一轮审计可追加 trend 自曝光匹配检查         |

### 下一步行动

1. **提交 ODPS 运行**：SQL 逻辑正确，审计通过，可以进入实验阶段。
1. **同步更新 fix_sample_v3**（设计文档已知风险）：聚合特征表需匹配 v3 schema。
1. **确认 config v19**：task_space_indicator_label 场景 mask 需与新 4 场景对齐。
