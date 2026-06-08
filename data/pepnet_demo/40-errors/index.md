______________________________________________________________________

## date: 2026-06-08 tags: [error, summary, lessons] status: critical related: \["\[[error-1-fixedlr]\]", "\[[error-2-constant-lr]\]", "\[[error-3-noise-undersample]\]", "\[[error-4-fix-not-effective]\]", "\[[error-5-wikilink-frontmatter]\]", "\[[error-6-frontmatter-fragmentation]\]"\]

# 错误与教训 (Index)

> 6 个重大错误, 全部已记录. **错误 3 和错误 4 已于 2026-06-08 关闭** (修复验证通过).

|  #  |                         状态                          |
| :-: | :---------------------------------------------------: |
|  1  |                  ✅ 已记录 (closed)                   |
|  2  |                  ✅ 已记录 (closed)                   |
|  3  | ✅ **已关闭** (eval 确定性修复, 4× bitwise identical) |
|  4  |      ✅ **已关闭** (OSS wheel + smoke test 生效)      |
|  5  |                  ✅ 已记录 (closed)                   |
|  6  |                  ✅ 已记录 (closed)                   |

## 🚨 错误时间线

|  #  | 错误                                  |            触发时间             |  解决时间  | 影响范围       |         严重度          | 状态  |
| :-: | :------------------------------------ | :-----------------------------: | :--------: | :------------- | :---------------------: | :---: |
|  1  | \[\[error-1-fixedlr                   | fixedlr config 引入额外变量\]\] | 2026-05-30 | 2026-06-01     |    单实验 confounded    |  中   |
|  2  | \[\[error-2-constant-lr               | constant_lr 结论 confounded\]\] | 2026-05-31 | 2026-06-06     |    单实验 + 后续推理    |  中   |
|  3  | \[\[error-3-noise-undersample         |  2-run noise 估计严重欠估\]\]   | 2026-06-07 | **2026-06-08** | **几乎所有 v6/v7 结论** | 🔴 高 |
|  4  | \[\[error-4-fix-not-effective         |       修复 ≠ 自动生效\]\]       | 2026-06-07 | **2026-06-08** | 修复部署, 阻塞修后重评  | 🔴 高 |
|  5  | \[\[error-5-wikilink-frontmatter      |  wikilink/frontmatter 损坏\]\]  | 2026-06-08 | 2026-06-08     | 20 个文件 wikilink 失效 |  低   |
|  6  | \[\[error-6-frontmatter-fragmentation |       格式迁移碎片化\]\]        | 2026-06-08 | 2026-06-08     |     4 轮修复才稳定      |  低   |

## 核心教训 (7 条)

### 1. ✅ 任何 eval pipeline 必须先设 seed + cudnn deterministic

本项目教训: 默认不设 seed 导致 5-run std 0.73pp, 耗时 3 天诊断 + 修复. **修后 4 次 bitwise identical, Std=0pp.**

详见 \[[error-3-noise-undersample]\] + \[[../20-experiments/eval-pipeline-fix|修复记录]\].

### 2. 必须做分钟级窗口连续重跑, 检测漂移 vs noise

若 1m22s 内 3 次 CVR 变化 > 0.5pp, 必是系统性问题, 不是 noise. noise 在分钟级窗口 < 0.1pp (per CTR 经验).

### 3. 验证集/数据假设必须显式确认, 不能凭"逻辑合理"推断

详见 \[[error-3-noise-undersample#错误子假设-自检-2026-06-07|错误 3 自检]\].

### 4. 源码修复 ≠ 自动生效, 必须 wheel + OSS + URL + smoke test 四步

详见 \[[error-4-fix-not-effective]\].

### 5. 数据对比前, 先读 SQL 和数据量

详见 \[[../30-data/sql-attribution-30d-vs-24h|30d vs 24h 归因差异]\].

### 6. 用工具批量编辑 markdown 后, 必须检查 frontmatter + wikilink 完整性

**触发**: 2026-06-08. 多次 edit 操作导致 20 个文件 frontmatter `---` 丢失 + wikilink 被 `\` 转义 → Obsidian 不识别.

**根因**: edit tool 的字符串替换会重写文件, 但不保证 frontmatter 定界符 `---` 不被吞. 同时某些 markdown 工具自动在 `[[` 前加 `\` 转义.

**影响**: 所有 wikilink 变成纯文本无法跳转, 耗时约 30min 诊断 + 全局脚本修复. 可逆, 不丢数据.

**预防**:

- [ ] 批量编辑后跑一次验证脚本: grep 检查 `[` 或丢失的 `---`
- [ ] 在 Obsidian 中打开文件列表确认 frontmatter 渲染
- [ ] 避免在 frontmatter 行上做 substring replacement (优先替换正文内容)

### 7. 格式选择是基础设施, 不做渐进式迁移

**触发**: 初始用了 `## date:` 而非标准 `---` 格式, 后经 4 轮修复才最终统一.

**根因**: "先写内容, 格式再改" → 文件数增加后迁移成本线性上升. 每轮修复只治标, 引入新不一致.

**教训**: 新项目先确定格式标准 (Obsidian: `---` frontmatter + `[[wikilink]]`), 一次性创建, 不做后迁.

详见 \[[error-6-frontmatter-fragmentation]\].

## ✅ 已关闭的预防 Checklist (2026-06-08)

```
Eval Pipeline (✅ 已修复, 永久确定性):
  [x] TORCH_MANUAL_SEED=42, NUMPY_MANUAL_SEED=42 (env var)
  [x] USE_DETERMINISTIC_ALGORITHMS=1 (cudnn deterministic)
  [x] EVAL_SEED=42 (重置 DDP + cuBLAS workspace)
  [x] worker_init_fn 固定 DataLoader seed
  [x] eval_config num_steps=123 (对齐 25W)
  [x] 4 次重跑验证: bitwise identical, Std=0pp ✅

Deployment:
  [x] wheel 1.2.16 = git HEAD
  [x] DLC 脚本 URL = 1.2.16
  [x] wheel 上传 OSS ✅
  [x] DLC 容器 smoke test ✅
  [x] env vars 在 set -e 后 export (pip install 前)

Data:
  [ ] 训练数据量 (7d vs 60d)
  [ ] 标签归因窗口 (24h vs 30d)
  [ ] 标签定义
  [ ] 清洗逻辑
  [ ] 校准状态
```

## 单变量变更原则 (项目元规则)

任何"对比"必须只改一个变量, 否则 confounded. 例:

- ❌ 错误 1: 同时改 LR schedule 和 weight_decay
- ❌ 错误 2: 同时改 optimizer 和 data
- ✅ 正确: 一次只改一个变量, N≥5 次重跑验证
