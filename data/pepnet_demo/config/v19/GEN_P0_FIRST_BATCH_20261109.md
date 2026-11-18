# GEN_P0_FIRST_BATCH_20261109 — 第一梯队 4 config 生成记录

**日期**：2026-11-09　**基线**：`home_flow_2608_v19_multiscene_v6f_kv_fusion.config`（单变量派生，新增文件不动既有）
**依据**：`PLAN_CTR_NEXT_20261107.md` 变更单（§二 + §9.8 终版）；用户指令"确认生成"
**生成脚本**：`gen_p0_first_batch_20261109.py`（锚点式插入 + 全量验证，幂等可重跑；解释器 `/usr/local/bin/python3`）

## 一、产物与验证汇总【事实读数】

| config（均在 `config/v19/`）     | 变更                                             | diff 纯新增            | proto 冒烟 | 专项核对                    |
| -------------------------------- | ------------------------------------------------ | ---------------------- | ---------- | --------------------------- |
| `..._v6f_p04_exposurert5.config` | 5 标量定义 + all 组 5 引用（+6 头注）            | **PASS** 141 行 0 删改 | **PASS**   | 列名 vs 编码表 DDL 5/5 ✓    |
| `..._v6f_p02a_seqts.config`      | 2 ts raw_feature + 2 组引用（+6 头注）           | **PASS** 60 行 0 删改  | **PASS**   | 边界逐值 = §9.8 终版 2/2 ✓  |
| `..._v6f_p03_overlap10.config`   | 10 common_ratio 定义 + all 组 10 引用（+5 头注） | **PASS** 145 行 0 删改 | **PASS**   | 列名 vs DDL 10/10 ✓         |
| `..._v6f_p02b_timegate4.config`  | 4×time_gate_dim + grad_clipping 搭车（+9 头注）  | **PASS** 18 行 0 删改  | **PASS**   | time_gate_dim==ts emb 4/4 ✓ |

汇总：**diff 4/4 ｜ proto 5/5（含基线对照）｜ 边界 2/2 ｜ time_gate_dim 4/4**。EasyRecConfig 解析用 pipeline_pb2 + `types.ModuleType` 包注册绕 fbgemm（同判决实验规程）。

## 二、各臂变更明细

**P0-4**：`user__cnt_exposure_rt{1h,3h,12h,24h}`（raw_feature emb=8，边界逐字照抄 `user__cnt_exposure_15d` 模板 19 cuts: 1.0~420.0）+ `user__num_exposure_avg_current_price_15d`（raw_feature emb=8）；定义插 cnt_exposure_15d 块后，引用插 all 组 `user__cnt_exposure_15d` 行后。

**P0-2a**：chajia/search sequence_feature 块尾（L10787↔10788、L10947↔10948 位）各插 ts raw_feature（`feature_name: "ts"` / `expression: "user:ts"` / emb=8，**边界=SQL-11 per-seq 分位数定标终版**）；组引用按 **ts 只挂全名不成对**惯例（照 `click_50_seq__ts`）各加 1 行。维度账逐位核实：两序列 DIN 输出 **216→224** ✓（与变更单一致）。

**P0-3**：`offline_like_{brand,first_cate_id,second_cate_id,third_cate_id,site}_common_ratio` + `offline_order_*` 同 5 实体，共 10 个 raw_feature（emb=8，边界 0.05/0.1/0.2/0.35/0.5/0.7 同族借位）；插 common_ratio 家族末块（`offline_search_click_site_common_ratio`）后；all 组同名 10 引用。

**P0-2b**：click_10/click_50/conversion_20/favorite_10 四个 din_encoder 在 attn_mlp 后加 `time_gate_dim`（见下修正）；`train_config` 内搭车 `grad_clipping {clipping_type:"norm", max_gradient:5.0, enable_global_grad_clip:true}`（proto 字段核实：train.proto `GradClipping`，字段名逐字匹配）。

## 三、决策与修正【决策/修正记录】

1. **变更单修正（bug 级）**：favorite_10 的 ts embedding_dim=**4**（其余三序列=8）。T3 规则 = "time_gate_dim = ts 的 embedding_dim"（取**末 N 维** ts 嵌入做门控）——变更单"4 个统一加 8"对 favorite_10 会把 username 尾 4 维误卷入门控。已按事实读数改为 **favorite_10 time_gate_dim=4**（8/8/8/4），验证 5 逐序列核对通过。【事实读数→修正】
1. **T3 维度账精度修正**：T3 归档" DIN 输出 224→216"只对 ts=8 的序列成立（click_10/50、conversion_20 ✓）；**favorite_10 实为 220→212**。P0-2a 的"216→224"逐位核实无误。下游维度链动态适配（T3 归档明示"不连坐"），无显式维度需改，此账仅供读数对照。【事实读数】
1. **P0-4 num 边界借位决策**：`user__num_exposure_avg_current_price_15d` 无自身分布数据，借位 `user__num_click_avg_current_price_15d` 的 19 cuts 价格边界（漏斗同侧近邻：曝光均价 vs 点击均价；emb=8）。若读数异常，下轮可 SQL 分位数定标复判（同 P0-2a 流程）。【决策】
1. **grad_clipping 搭车选臂**：PLAN"选一臂带上"→ 选 **P0-2b**（试探档、归因本就松；门控乘性调制梯度风险最高处最需要保险）。若 P0-2b 读数显著需归因，补无 clipping 对照。【决策】
1. 训练口径不变：20261030 样本集、同 eval 指纹、T_max 纪律（记录实际步数核对调度）；判据沿用 §二 共同规格（Δctr ≥ +0.10pp 续投 / |Δ| ≤ 0.05pp 弃 / 过闸 3-seed 符号闸）。

## 四、工具纪律备忘【工具记录】

- **BSD grep `\|` 不做交替**：本会话又踩 5 次（P0-4/P0-3 列、train_config、grad_clipping、判决 config 文件名均曾误报"不存在"）——一律 `grep -a` + 单模式或 `grep -E`。
- WorkBuddy 自带 python3.13 无 protobuf；proto 冒烟用 `/usr/local/bin/python3`（3.11.9，有 protobuf）。
- 生成脚本幂等：改脚本重跑即全量重生成 + 全量重验证。

______________________________________________________________________

*创建：2026-11-09。证据锚：`PLAN_CTR_NEXT_20261107.md`（变更单/判据）、`SUMMARY_20261030_ALL_RUNS.md`（基线读数）、编码表 DDL（列核实）、T3 归档（time_gate 机制与双因子警示）。*
