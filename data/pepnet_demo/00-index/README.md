______________________________________________________________________

## title: PEPNet Demo - 项目入口 date: 2026-06-08 status: active tags: [MOC, index, pepnet] related: \["\[[10-architecture/pepnet-dcn-ple]\]", "\[[20-experiments/eval-pipeline-fix]\]"\]

# PEPNet Demo — Home Feed Ranking Optimization

> **TL;DR**: 构建并部署 PEPNet_v2 (含 DCNv2 + PLE + CDOT) 到 home feed 排序, 优化 CVR AUC. v6_ple_d 离线 CVR **0.791069 (exact, deterministic)**. **✅ P0 eval 非确定性修复验证通过 (2026-06-08)**, 4 次重跑 bitwise identical, Std=0pp. 修复前 5-run mean 0.7852 有系统性低估偏差 -0.59pp.

## 🚦 当前状态 (2026-06-08)

| 维度              |    状态     | 详情                                          |
| :---------------- | :---------: | :-------------------------------------------- |
| 模型架构          |   ✅ Done   | PEPNetDCNPLE 完整实现 + 6 个 model tests pass |
| 设计矩阵          | ✅ Complete | v6 2×2×2 + v7 全部 13 实验确定性完成          |
| v7 变种           | ✅ Complete | dpage 发现 config bug (已修, 结果 = d=8)      |
| P0 修复验证       | ✅ Verified | 4 次重跑 bitwise identical, **Std=0pp**       |
| OSS wheel 部署    |   ✅ Done   | 1.2.16 已上传生效, smoke test 通过            |
| 在线 A/B          |   ✅ Done   | 1 天观察, exp2 > exp1 +5.3% 显著              |
| 上产决策          |   ⏸️ Hold   | 待设计矩阵重跑完整后定                        |
| error-3           |  ✅ Closed  | noise 根因已修, 4× 确定性验证通过             |
| error-4           |  ✅ Closed  | wheel OSS + smoke test 生效                   |
| MD Reorganization |   ✅ Done   | 21 新文件 + 4 旧根文件删除 + 11 归档          |

## 📑 文件索引

### 🏛️ 10-architecture — 模型架构

- \[[10-architecture/pepnet-v2]\] — PEPNet_v2 基础架构
- \[[10-architecture/pepnet-dcn-ple]\] — PEPNetDCNPLE (本项目使用) ⭐
- \[[10-architecture/model-components]\] — LHUC / CDOT / CrossV2 / ExtractionNet 模块详解
- \[[10-architecture/data-schema]\] — 特征 schema (40+ features)

### 🧪 20-experiments — 实验记录

- \[[20-experiments/v6-design-matrix]\] — 2×2×2 设计矩阵 8/8 完整结果
- \[[20-experiments/v7-ple-d-variants]\] — d=8/16/32, dpage, ph 5 个变种
- \[[20-experiments/v8-experiments]\] — v8 baseline + PLE+d16 调优
- \[[20-experiments/5run-noise-investigation]\] — 0.73pp std 调查与根因
- \[[20-experiments/eval-pipeline-fix]\] — 2026-06-07 P0 修复落地 ⭐
- \[[20-experiments/ab-test-2026-06-06]\] — 1 天在线 A/B 测试
- \[[20-experiments/t-max-correction]\] — GPU 数 / T_max 修正实验

### 📊 30-data — 数据 / SQL

- \[[30-data/sample-v1-60d]\] — 60 天样本集 (线上 base 使用)
- \[[30-data/sample-v2-7d]\] — 7 天样本集 (v6+ exp 使用)
- \[[30-data/sample-v3-pipeline]\] — sample_v3 特征工程全流程：SQL → FG → EasyRec
- \[[30-data/sql-attribution-30d-vs-24h]\] — 标签归因窗口 30d vs 24h 关键差异 ⭐
- \[[30-data/site-mapping]\] — site/level 分布分析

### ❌ 40-errors — 错误与教训

- \[[40-errors/index]\] — 错误总结 (4 个重大错误)
- \[[40-errors/error-1-fixedlr]\] — fixedlr config 引入额外变量
- \[[40-errors/error-2-constant-lr]\] — constant_lr 结论 confounded
- \[[40-errors/error-3-noise-undersample]\] — 2-run noise 估计严重欠估
- \[[40-errors/error-4-fix-not-effective]\] — 修复 ≠ 自动生效 (wheel 部署)

### 📦 99-archive — 历史归档

- May 29-30 老文件 (15 个), 已被新文件取代, 保留供追溯

## 🔑 关键数字

| 指标               |                  数值 | 备注                          |
| :----------------- | --------------------: | :---------------------------- |
| 候选模型           | v6_ple_d (= v7_ple_d) | dim=8, f_req_domain in CDOT   |
| 离线 CVR (确定性)  |          **0.791069** | 修复后 exact, Std=0pp         |
| 修复前 CVR (5-run) |       0.7852 ± 0.73pp | 系统性低估 -0.59pp            |
| 训练数据           |          7 天, ~1.5亿 | 60d 数据的 1/9                |
| 验证集             |              25W 固定 | bizdate=0602, 1% 采样         |
| 训练硬件           |                 2×A10 | eff_batch=4096, ~3.5h/epoch   |
| 修复后 Eval        |            **确定性** | 4× bitwise identical, Std=0pp |
| 上产候选           |                  待定 | 需全设计矩阵重跑后决定        |

## 🔗 外部资源

- 训练 SQL: `data/pepnet_demo/sql/sample_v2/`
- 训练脚本: `data/pepnet_demo/sql/sample_v2/tran_v6_ple_d.sh`
- Config: `data/pepnet_demo/config/v6/home_flow_2604_v6_ple_d.config`
- 修复 wheel: `dist/tzrec-1.2.16-py2.py3-none-any.whl` ✅ OSS 已上传生效

## 🔌 Obsidian 接入

> **5 秒完成, 把这套笔记变双向链接知识图谱**.

### 步骤

1. 打开 Obsidian → 左下角 **"Open folder as vault"** (不是 "Create new vault")
1. 选择本仓库的 `data/pepnet_demo/` 目录
1. Obsidian 自动识别:
   - 6 个子目录 (`00-index/`, `10-architecture/`, ...)
   - `[[wikilinks]]` 双向链接
   - `#tags` 标签聚合
   - Frontmatter 元数据

> ⚠️ 不要用 "Create new vault" — 它会创建新空文件夹. **必须用 "Open folder as vault"** 才能打开已有目录.

### 推荐使用方式

| 操作         | 快捷键 / 动作              |
| :----------- | :------------------------- |
| 跳转链接     | `[[` 触发自动补全          |
| 反向链接面板 | 右侧栏点 "Linked mentions" |
| 全局图谱     | `Ctrl/Cmd + G` 看文件关联  |
| 标签搜索     | `#error` 找所有错误        |
| 快速切换     | `Ctrl/Cmd + O` 文件搜索    |
| MOC 入口     | 打开 `00-index/README.md`  |

### 推荐的 3 个 Graph View 视图

1. **过滤 #error**: 看 \[[40-errors/index|4 个错误]\] 如何与 \[[20-experiments/eval-pipeline-fix]\] 互链
1. **过滤 #experiment**: 看 v6/v7 设计矩阵 + A/B + 5-run 调查的依赖图
1. **过滤 #critical**: 看 ⭐ 标记的 4 个核心文件:
   - \[[10-architecture/pepnet-dcn-ple]\]
   - \[[20-experiments/eval-pipeline-fix]\]
   - \[[20-experiments/5run-noise-investigation]\]
   - \[[30-data/sql-attribution-30d-vs-24h]\]

### 不需要 Obsidian 也能用

- 纯 VSCode + Markdown Preview Enhanced: 装 [Markdown Notes](https://marketplace.visualstudio.com/items?itemName=kortina.vscode-markdown-notes) 插件让 `[[wikilinks]]` 可跳转
- 纯文本浏览: `find . -name "*.md" | xargs cat`, 用 ripgrep 搜 tag

### 已有 vault 怎么办?

把 `data/pepnet_demo/` 作为现有 vault 的**子目录**即可, 不会冲突. Obsidian 会自动索引所有子目录.
