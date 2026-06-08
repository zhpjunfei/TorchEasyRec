______________________________________________________________________

## date: 2026-05-30 tags: [error, confounded, fixedlr, lesson] status: resolved

# 错误 1: fixedlr config 引入额外变量

## 触发时间

2026-05-30

## 上下文

- 当时在调 baseline 模型 `pepnet.config` (cosine LR + weight_decay=0.01)
- 想测试"去掉 weight_decay, 用 constant_lr 训练到底"的效果
- 创建了 `pepnet_fixedlr.config`, 改了 LR schedule + 去掉 weight_decay
- 跑出 **CVR 0.76970**, 显著优于 baseline 0.742
- 当时认为: "constant_lr + 无 wd 是真优化"

## 错误行为

- 得出"constant_lr 优于 cosine"的结论
- 准备用 fixedlr 作为生产 baseline

## 根因

**同时改了两个变量**:

1. `cosine_annealing_learning_rate` → `constant_lr`
1. 去掉 `weight_decay=0.01` (part_optimizers)

这两个变量**共同**导致 CVR +2.7pp, 无法归因到任何一个.

## 为什么出错

- 没有坚持"单变量变更"原则
- 急于看到改进, 把多个改动打包成一个实验
- 看到大改进没怀疑 confounded

## 正确做法

**保持 baseline 只改一个变量**:

- 方案 A: 只改 LR schedule (保留 weight_decay=0.01)
- 方案 B: 只去掉 weight_decay (保留 cosine LR)
- 跑完两个, 再决定是否组合

## 实际验证 (2026-06-01)

| 配置                                     | 变化                         |    CVR AUC     |
| :--------------------------------------- | :--------------------------- | :------------: |
| pepnet.config (cosine)                   | —                            |     0.742      |
| pepnet_fixedlr (constant_lr **仅改 LR**) | cosine→constant_lr           |  **0.730** ❌  |
| pepnet_fixedlr_v2 (同时改两个)           | cosine→constant + 去 wd=0.01 | 0.76970 (假象) |

**真相**: constant_lr **反而**让 CVR 从 0.742 降到 0.730, weight_decay=0.01 是关键.

## 预防

- [ ] **任何"对比"必须只改一个变量** (单变量变更原则)
- [ ] 看到大改进 (>1pp) 立即怀疑 confounded
- [ ] 改动列表写在实验记录顶部, 评审时检查

## 关联

- \[[error-2-constant-lr]\] — 类似 confounded 模式
- \[[index|错误总结]\]
