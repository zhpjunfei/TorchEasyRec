______________________________________________________________________

## date: 2026-06-26 tags: [experiment, index] status: active related: \["\[[v6-design-matrix]\]", "\[[v14-experiments]\]", "\[[eval-pipeline-fix]\]"\]

# 20-experiments — 实验记录

> 从 v6 到 v14 的所有实验记录。按版本时间线排列。

## 版本时间线

| 版本 | 文件                              | 关键主题                             |     状态     |
| :--- | :-------------------------------- | :----------------------------------- | :----------: |
| v6   | \[[v6-design-matrix]\]            | 2×2×2 设计矩阵, 8/8 cells 完整       |  completed   |
| v7   | \[[v7-ple-d-variants]\]           | d=8/16/32, dpage, ph 5 个变种        |  completed   |
| v7   | \[[v7-control-weight]\]           | 样本加权 / 选择偏差                  |  completed   |
| v8   | \[[v8-experiments]\]              | baseline + PLE+d16 调优              |  completed   |
| v9   | \[[v9-experiments]\]              | 全日期衰减修复                       |  completed   |
| v10  | \[[v10-experiments]\]             | DIN 序列优化                         |  completed   |
| v11  | \[[v11-contrastive-learning]\]    | 对比学习 → Label Smoothing → LR 调度 |  completed   |
| v12  | \[[v12-experiments]\]             | 损失优化策略                         |  completed   |
| v13  | \[[v13-experiments]\]             | 优化方向审核                         |  completed   |
| v14  | \[[v14-experiments]\]             | out_task_space_weight 全扫描完结     | ✅ completed |
| v14  | \[[v14-optimization-plan]\]       | 路线图（Round 1，已被 codex 版取代） |  superseded  |
| v15  | \[[v14-optimization-plan-codex]\] | Codex 深度审查版路线图（UV 级优化）  |    draft     |

## 基础设施实验

| 文件                           | 说明                    | 状态      |
| :----------------------------- | :---------------------- | :-------- |
| \[[5run-noise-investigation]\] | 0.73pp std 调查与根因   | completed |
| \[[ab-test-2026-06-06]\]       | 1 天在线 A/B 测试       | completed |
| \[[eval-pipeline-fix]\]        | P0 eval 非确定性修复 ⭐ | completed |
| \[[t-max-correction]\]         | GPU 数 / T_max 修正实验 | completed |
