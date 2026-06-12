______________________________________________________________________

## date: 2026-06-11 tags: [experiment, v10, title-vector, world-knowledge] related: \["\[[v9-experiments]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v10 实验 — 引入 title_vector 世界知识语义 Embedding

> v10 pipeline 与 v9 一致（v1c 编码, v1 SQL 60d+30d归因）. 以 v9_sota 为基线. 实验变量：增加 title_vector（128维预计算世界知识语义embedding, item侧, raw_feature透传无投影）. 所有实验 4卡, batch_size=4096/GPU, 有效=16384. T_max=6700/warmup=1000.

## 实验清单

| 实验         | Config                                   | 变化           |
| :----------- | :--------------------------------------- | :------------- |
| baseline     | `home_flow_2604_v10_baseline.config`     | v9_sota (对照) |
| title_vector | `home_flow_2604_v10_title_vector.config` | + title_vector |

## Config 结构变化

| 维度                                     | baseline | title_vector |
| ---------------------------------------- | -------- | ------------ |
| 所有v9_sota改动                          | ✓        | ✓            |
| title_vector raw_feature (value_dim=128) | ✗        | ✓            |
| T_max                                    | 6700     | 6700         |
| GPU                                      | 4        | 4            |

## 背景

title_vector 是由世界知识模型预计算的 128 维语义 embedding，编码了商品标题的语义信息（品牌、品类、用途、风格等）。作为 raw_feature 透传输入模型（无投影层，value_dim=128），期望为塔提供更丰富的 item 语义信号，提升 CVR 泛化能力。

## 结论

待实验完成后填写。
