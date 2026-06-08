______________________________________________________________________

## date: 2026-06-08 tags: [decision, timeline, pepnet]

# Decisions Log — 关键决策时间线

> 记录项目演进中的关键决策点. 详细实验见 \[[20-experiments/index|20-experiments]\], 错误教训见 \[[40-errors/index|40-errors]\].

## 2026-06-04: v6_domain_lsp.config 基于 site/level 分布优化

- \[[30-data/site-mapping|site_mapping]\] 完成, 发现:
  - site 346 (话题): 1.6M PV, click→CVR 0% (content stream)
  - level: B(26%) → F(41%) click→CVR monotonic
- 决策: 用 lsp (Layer-Sensitive Personalization) 替代 raw embedding

## 2026-06-05: 数据策略重大调整 ⭐

- 发现 \[[30-data/sample-v1-60d|60d 样本]\] 与 \[[30-data/sample-v2-7d|7d 样本]\] 标签归因不同 (30d vs 24h)
- 见 \[[30-data/sql-attribution-30d-vs-24h|sql 归因差异详解]\]
- 决策: v6+ 实验用 7d 数据 (v3 SQL), 与线上 base 60d 数据**不可直接比较**
- 教训: 见 \[[40-errors/error-2-constant-lr|错误 2]\]

## 2026-06-06: PLE 突破

- v6_ple 单跑 0.7878 (vs v6_baseline_hbs 0.7822, +0.56pp) ✅
- 决策: 启用 PLE (ExtractionNet) 作为生产候选

## 2026-06-06 14:05: v6_ple_d 突破 ⭐

- v6_ple_d 单跑 **0.7922** (修复前, 落入 0.73pp noise 上限), +0.44pp vs v6_ple
- 决策: v6_ple_d = 候选生产模型 (后经确定性验证 = **0.791069**)
- 后续发现: 1m22s 窗口内 3 次重跑单调下降 -1.31pp, **引出 0.73pp 噪声调查**

## 2026-06-06 18:47: v7 系列启动

- 5 个 v7 变种跑完 (d=8/16/32, dpage, ph)
- 初步判断: dim=8 可能是 sweet spot, 但 d=16/d=32 修复前均值更高 (+0.47pp/+0.28pp), 均落入 0.73pp noise, 待确定性重跑确认

## 2026-06-06: A/B 测试

- 1 天在线 A/B, 3 模型对照
- exp2 (v6_ple_d) vs exp1 (v6_domain_id_only) +5.3% (Z=2.6, p=0.0093) 显著
- exp1/exp2 vs base (pepnet_v4) 退步, 主因 = **9x 数据劣势** + 归因窗口不同
- 决策: A/B 不能下 v6_ple_d vs v4 的结论, 需等公平 A/B

## 2026-06-07: Eval 非确定性根因定位 ⭐⭐

- 用户确认**验证集固定 25W** (不是数据漂移)
- 5-run std 0.73pp, 1m22s 窗口单调下降 -1.31pp
- 根因: eval pipeline 自身非确定性 (no seed / cudnn.deterministic / TF32 / DDP state / GPU mem)
- 决策: 必须先修复 eval 才能重做对比, **暂停所有离线对比**
- 详见 \[[20-experiments/5run-noise-investigation|5-run 噪声调查]\]

## 2026-06-07: P0 修复完成 ⭐

- 4 文件修复: `__init__.py` / `main.py:_evaluate()` / `dataset.py:create_dataloader()` / `v6_ple_d.config`
- 重打 wheel 1.2.15 → 1.2.16
- 改 `tran_v6_ple_d.sh` 装新 wheel + 4 行 `export`
- 教训: 源码修复 ≠ 自动生效, 见 \[[40-errors/error-4-fix-not-effective|错误 4]\]
- 详见 \[[20-experiments/eval-pipeline-fix|修复记录]\]

## 🆕 2026-06-08: Eval 修复验证通过 ⭐

- v6_ple_d 4 次重跑全部 bitwise identical:
  - CVR AUC: 0.791069 (exact, all 4 runs)
  - CTR AUC: 0.790610 (exact, all 4 runs)
  - **Std=0pp** (vs 修复前 0.73pp)
- 修复前 5-run mean 0.7852 有系统性低估偏差 -0.59pp vs 真实值 0.791069
- OSS wheel 1.2.16 已上传生效, smoke test 通过
- **决策**: error-3-noise-undersample ✅ 关闭. error-4-fix-not-effective ✅ 关闭.
- **下一阶段**: 设计矩阵确定性重跑 (8/8 cells, 每实验 1 次)
- 详见 \[[20-experiments/eval-pipeline-fix|修复记录]\]

## 2026-06-08: Wikilink/frontmatter 损坏事故 ⚠️

- 多次 `edit` 操作导致 20 个文件 frontmatter `---` 丢失 + wikilink `[` 转义
- Obsidian 中所有 wikilink 不能跳转, 诊断约 30min
- 修复: 全局 Python 脚本恢复 frontmatter 定界符 + 去除转义
- **教训**: 批量工具编辑 markdown 后必须验证 frontmatter/wikilink 完整性
- **预防**: 编辑后 grep 检查 `[` 或 `## date:` 模式
- 详见 \[[40-errors/index#错误-5-wikilink-frontmatter-损坏|错误 5]\]

## 🆕 2026-06-08: 三个关键结论被推翻 (确定性 vs 修复前) ⭐⭐

确定性重跑揭示修复前 5-run noise 0.73pp 系统性误导:

1. **"PLE 打败 PEPNet" → 假象**: PLE baseline (0.786291) ≈ PEPNet baseline (0.786723), Δ仅 -0.04pp. PLE 本身不提升.
1. **"lsp 有效 +0.30pp" → 假象**: PEPNet+lsp 实际 **-0.13pp**. baseline 跑在 eval 低谷, lsp 跑在正常点.
1. **"d=8 sweet spot" → 暂不成立**: d=16 确定优于 d=8 (CVR +0.07pp, CTR +0.13pp), 须等 d=32.

**唯一正增益**: PLE + f_req_domain in CDOT. 详见 \[[../20-experiments/v6-design-matrix#双指标综合分析|v6 设计矩阵综合分析]\].

## 🆕 2026-06-08: CTR 综合分析结论 ⭐

在线 score 公式 `pCTR * (1+pCVR)` 下, CTR 权重更高. 确定性结果:

| 实验            |      CVR AUC |   CTR AUC    |    ΔCVR     |    ΔCTR     |
| :-------------- | -----------: | :----------: | :---------: | :---------: |
| PEPNet baseline |     0.786723 |   0.788628   |      —      |      —      |
| PLE + d=8       |     0.791069 |   0.790610   |   +0.43pp   |   +0.20pp   |
| **PLE + d=16**  | **0.791747** | **0.791909** | **+0.50pp** | **+0.33pp** |

PLE+d 系列是唯一双正组合. PEPNet+dlsp CTR 最高但 CVR 最低, score 实际有害. **生产候选: PLE + d=16**.

## 待决

- [ ] d=32 确定性重跑 — 确认最优 dim
- [ ] dpage, ph 确定性重跑 — 确认 feature 选择
- [ ] domain_id_only, ple_lsp, ple_dlsp — 补全矩阵
- [ ] 公平 A/B (7d vs 7d, 同归因窗口)
- [ ] 统一归因窗口 (24h vs 30d)
