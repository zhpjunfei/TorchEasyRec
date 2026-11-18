# 多问题修复总结

**日期**: 2026-10-22
**状态**: ✅ 全部修复完成

______________________________________________________________________

## 一、已修复问题

### 1.1 标签泄漏问题（P0）

**文件**: `config/v19/home_flow_2608_v19_multiscene_v2_fix_label_leak.config`

**修复内容**:

- ctr tower添加`task_space_indicator_label: "is_home_scene"`
- cvr tower添加`task_space_indicator_label: "is_home_scene"`（防御性）
- 移除不存在的`is_home_scene_click`字段

**效果**:

- CTR loss: 1.747 → 2.671 (+52.8%)
- CTCVR loss: 0.206 → 0.304 (+47.6%)
- CTR GAUC: 0.7010 → 0.7022 (+0.17%)

### 1.2 MLP维度不匹配（P0）（2026-10-22 修正落点）

**文件**: `config/v19/home_flow_2608_v19_phase1_{chajia,p0,p0_v2,search}.config`（各 3 个辅助塔；初版误记为 v2 配置，v2 本来就是 `[512,256,128]`）

**修复内容**:

- 辅助任务MLP从`[128, 64]`改为 **`[512, 256, 128]`**（与 multiscene 基线及 phase1_bijia_only/phase2 对齐，顺带消除跨 Phase 宽度混淆变量；初版 `[128,64,128]` 方案作废）
- 统一所有配置的tower输出维度为128（9/9 验证通过）

**效果**: 解决`compute_gradient_conflict()`运行时错误

### 1.3 Trend数据重复问题（P0）

**文件**: `sql/2609/home_flow_2606_ctrcvr_sorter_label_table_v5.sql`

**修复内容**:

- 第137行: `SELECT event_unix_time` → `SELECT MIN(event_unix_time) AS event_unix_time`
- 第160行: `GROUP BY event_unix_time, item_id, mmb_id, request_id` → `GROUP BY item_id, mmb_id, request_id`

**数据验证结果**（2026-10-22 修正）:

- 重复率: **100%**（12.0M 行全部落在重复组合里；原"37% (4.5M/12M)"是组合数÷行数的无意义比值，作废）
- 标签矛盾: 98.6% (4.4M/4.5M 组合)
- 有效噪声率: ≈9.9%（原 3.6% 低估约 3 倍）
- 预期修复后: 重复率\<1%, 矛盾率\<5%, trend 行数 ≈4.5M

______________________________________________________________________

## 二、验证SQL

**文件**: `sql/2609/verify_trend_duplicate.sql`

包含4个验证SQL：

- SQL1: 基础统计（总行数、唯一item数、唯一request数）
- SQL2: 重复分布（2行/3行/4行的组合数）
- SQL3: 标签矛盾（mixed_labels/all_click/all_no_click）
- SQL4: 各场景行数对比

______________________________________________________________________

## 三、下一步行动

### 立即执行

1. **重新生成样本表**

   ```bash
   # 使用修复后的label_table_v5.sql重新运行60d汇总脚本
   # 生成dt='20261020'的新样本
   ```

1. **运行验证SQL确认修复效果**

   ```sql
   -- 运行 sql/2609/verify_trend_duplicate.sql
   -- 预期：
   -- - 重复率 < 1%
   -- - mixed_labels < 5%
   -- - trend样本量 ≈4.5M（>4M 即正常；原 >5M 门槛会把正确修复判失败）
   ```

1. **启动训练对比实验**

   ```bash
   bash data/pepnet_demo/config/v19/train_v19_multiscene.sh \
     home_flow_2608_v19_multiscene_v2_fix_label_leak.config \
     20261020
   ```

### 预期效果

| 指标          | 当前值 | 预期值      | 提升                     |
| ------------- | ------ | ----------- | ------------------------ |
| home CTR GAUC | 0.702  | 0.702~0.710 | 预期区间（不承诺 +1.1%） |
| trend GAUC    | 0.639  | 0.700+      | 预期值，需实测           |
| trend重复率   | 100%   | \<1%        | 数据质量达标             |

______________________________________________________________________

## 四、文档索引

| 文档         | 路径                                       | 说明                 |
| ------------ | ------------------------------------------ | -------------------- |
| 完整修复报告 | `config/v19/TREND_DUPLICATE_FIX_REPORT.md` | 趋势重复问题详细分析 |
| 标签泄漏修复 | `config/v19/LABEL_LEAK_FIX_V2.md`          | CTR/CVR掩码修复      |
| MLP维度修复  | `config/v19/BUG_FIX_MLP_DIMENSION.md`      | 梯度冲突计算修复     |
| CVR校准分析  | `config/v19/CVR_CALIBRATION_CORRECTED.md`  | ESMM乘积校准分析     |
| 下一步行动   | `config/v19/NEXT_STEPS.md`                 | 执行清单             |

______________________________________________________________________

**修复完成时间**: 2026-10-22 00:10
**修复人**: Agnes (Codex) + 用户
**状态**: 等待样本重新生成和验证
