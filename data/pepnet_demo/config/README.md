# config — 训练配置

## 目录结构

```
config/
├── dssm/                              # DSSM 模型配置
├── home_flow_2604_pepnet.config       # 初始 PEPNet 配置
├── home_flow_2604_pepnet_v4_cdot32_weight_long_v1f.config  # v4 CDOT 配置
├── v0/ v1/ ... v14/                   # 按版本组织的实验配置
```

## 版本对照

| 版本  | 对应实验笔记                                     | 说明                  |
| :---- | :----------------------------------------------- | :-------------------- |
| v0–v5 | —                                                | 早期探索 (99-archive) |
| v6    | \[[../20-experiments/v6-design-matrix]\]         | 2×2×2 设计矩阵        |
| v7    | \[[../20-experiments/v7-ple-d-variants]\]        | PLE d 变种            |
| v8    | \[[../20-experiments/v8-experiments]\]           | baseline + PLE+d16    |
| v9    | \[[../20-experiments/v9-experiments]\]           | 全日期衰减修复        |
| v10   | \[[../20-experiments/v10-experiments]\]          | DIN 序列优化          |
| v11   | \[[../20-experiments/v11-contrastive-learning]\] | 对比学习              |
| v12   | \[[../20-experiments/v12-experiments]\]          | 损失优化              |
| v13   | \[[../20-experiments/v13-experiments]\]          | 优化审核              |
| v14   | \[[../20-experiments/v14-experiments]\]          | out_task_space_weight |

## 使用方式

训练配置通过 `--config` 参数指定。每个版本目录内通常包含 baseline 及多个变种配置。
