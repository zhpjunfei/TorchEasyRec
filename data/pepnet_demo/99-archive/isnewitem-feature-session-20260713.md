______________________________________________________________________

## tags: [session, isNewItem, feature-engineering, new-item] date: 2026-07-13 status: active

# Session: isNewItem_fg 特征接入 + 新帖排序能力验证

## 目标

改善精排模型对新帖的排序表现，提升 re-rank 新帖曝光占比。

## 完成工作

### 1. isNewItem_fg 特征接入（Approach A — SQL 直算）

- **v3.sql** — DDL `isnewitem_fg ARRAY<STRING>` + SELECT `ARRAY(CASE WHEN pub_hours < 5 THEN '1' ELSE '0' END)`（训练数据侧）
- **Config** — `feature_configs { id_feature { vocab_list: ["0", "1"]; stub_type: true } }`，不改变模型参数
- **feature_groups** — 加入 `isnewitem_fg`（所有 v1f 系列 config）

### 2. 命名规范相关问题排查

- 原用 `isNewItem_fg`（驼峰），ODPS SQL 列名默认小写 → 产出 `isnewitem_fg`
- FG handler 和 tzrec 配置的列名匹配是大写敏感的
- **修复**: 所有 config/脚本/SQL 改为全小写 `isnewitem_fg`（~13 个文件）

### 3. 指标验证结果

使用 `v1f_gauc.config` 跑训练 + eval，产出：

| 维度           | 旧帖   | 新帖       | 结论        |
| -------------- | ------ | ---------- | ----------- |
| CTR AUC        | 0.7138 | **0.7257** | ✅ 新帖更好 |
| CVR AUC        | 0.7590 | **0.7619** | ✅ 相当     |
| CTR 预测分 avg | 0.376  | **0.389**  | ✅ 新帖略高 |
| 实际 转化/点击 | 0.336  | **0.348**  | ✅ 趋势一致 |

**结论: 模型对新帖的排序能力不存在问题。** Re-rank 30% 差距应从粗排/偏置排查。

### 4. 关键踩坑记录

| 问题                                   | 根因                                                        | 解决                                      |
| -------------------------------------- | ----------------------------------------------------------- | ----------------------------------------- |
| `no input for feature to do bucketize` | `_fg` 后缀特征在 FG JSON 和 `feature_groups` 中都需要有定义 | Approach A 绕过 FG handler，直接 SQL 产出 |
| ODPS 列名不匹配                        | SQL `AS isNewItem_fg` 产出小写 `isnewitem_fg`               | 全量统一小写                              |
| `segment_auc` 无输出                   | `segment_auc` 通过模型特征管道读值，需 `feature_groups`     | 加入 `feature_groups` 即可                |
| `grouped_auc` 在 v14 无输出            | v14 数据表无 `isnewitem_fg` 列                              | 需在 v14 的数据 pipeline SQL 中加入       |
| `grouped_auc` 不能放 `train_metrics`   | Protobuf `TrainMetricConfig` 不支持 `GroupedAUC`            | 只能用 eval `metrics`                     |
| 产线 eval 不跑                         | 训练脚本没有 `--eval_input_path`，eval_dataloader 为 None   | 需加 eval input 或在 config 中配置        |
| ruff lint 报错                         | `.py` 后缀的文件本质是 shell 脚本                           | `exclude` 到 `.ruff.toml`                 |

### 5. 待确认

- ~~物品信息表 `...preprocess_v3.sql` 增加 `isnewitem_fg` 字段（线上 inference）~~ 已回滚
- 产线训练需要 `--eval_input_path` 才能看到 `grouped_auc`

## 涉及文件

| 文件                                     | 改动                                                     |
| ---------------------------------------- | -------------------------------------------------------- |
| SQL: `v3.sql`                            | DDL + SELECT `isnewitem_fg ARRAY<STRING>`                |
| SQL: `fix_sample_v3.sql`                 | 回退（无改动）                                           |
| SQL: `upsample.sql`                      | filter `isnewitem_fg[0]='0'/'1'`                         |
| Config: `v1f.config`                     | `feature_groups` + `stub_type` + `segment_auc`           |
| Config: `v1f_gauc.config`                | `grouped_auc{isnewitem_fg}`                              |
| Config: 其他 7 个 config                 | `feature_name` / `expression` / `feature_names` 统一小写 |
| 脚本: `predict_*.sh`, `analyze_*.sql/py` | 列名统一小写                                             |
| `.ruff.toml`                             | 排除 shell 脚本类 `.py` 文件                             |
| AGENTS.md                                | 已存在（项目规则）                                       |
| opencode.json                            | contextPaths 引用 AGENTS.md                              |

## 相关文档

- `20-experiments/isnewitem-segment-auc-analysis.md` — 详细指标分析
