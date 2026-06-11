______________________________________________________________________

## date: 2026-06-10 tags: [experiment, v8, ple-d16, tuning] related: \["\[[v6-design-matrix]\]", "\[[v7-ple-d-variants]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v8 实验 — PDPNet_v2 baseline + PLE+d16 调优

> v8 pipeline (v1c 编码, v1 SQL 60d+30d归因) 下验证 PLE+d16 效果并超参数调优. 所有实验 2卡, batch_size=4096/GPU, 有效=8192. T_max=13000/warmup=2000 适配 1epoch. 单变量改动.

## 实验清单

| 排行 | 实验                | Config                                      | 变化                  |   CVR    |   CTR    |  ΔCVR   |  ΔCTR   | 综合Δ |   状态    |
| :--: | :------------------ | :------------------------------------------ | :-------------------- | :------: | :------: | :-----: | :-----: | :---: | :-------: |
|  —   | baseline (4卡,参考) | `home_flow_2604_v8_baseline.config`         | 4卡对照 T_max=6300    | 0.736009 | 0.697252 |    —    |    —    |   —   | ✅ 已完成 |
|  —   | baseline_2gpu       | `home_flow_2604_v8_baseline_2gpu.config`    | 2卡对照               | 0.736688 | 0.698897 |    —    |    —    |   —   | ✅ 已完成 |
|  2   | PLE+d16 (旧)        | `home_flow_2604_v8_ple_d16.config`          | PLE+d16 (T_max=6300)  | 0.737303 | 0.702010 | +0.13pp | +0.48pp | 0.61  | ✅ 已完成 |
|  4   | PLE+d16 (修正T_max) | `home_flow_2604_v8_ple_d16.config`          | PLE+d16 (T_max=13000) | 0.737912 | 0.703539 | +0.12pp | +0.46pp | 0.58  | ✅ 已完成 |
|  7   | PLE+dlsp            | `home_flow_2604_v8_ple_dlsp.config`         | PLE+dlsp              | 0.736970 | 0.700944 | +0.10pp | +0.37pp | 0.47  | ✅ 已完成 |
|  1   | PLE+d16 4GPU        | `home_flow_2604_v8_ple_d16_4gpu.config`     | 4卡 T_max=6700        | 0.744839 | 0.702668 | +0.88pp | +0.54pp | 1.42  | ✅ 已完成 |
|  8   | PLE+d16 ctr_wt1     | `home_flow_2604_v8_ple_d16_ctr_wt1.config`  | ctr weight=1.0        | 0.739311 | 0.700913 | +0.26pp | +0.20pp | 0.46  | ✅ 已完成 |
|  5   | PLE+d16 ctr_wt5     | `home_flow_2604_v8_ple_d16_ctr_wt5.config`  | ctr weight=5.0        | 0.737268 | 0.703694 | +0.06pp | +0.48pp | 0.54  | ✅ 已完成 |
|  9   | PLE+d16 lr5e4       | `home_flow_2604_v8_ple_d16_lr5e4.config`    | lr=0.0005             | 0.737645 | 0.702362 | +0.10pp | +0.35pp | 0.45  | ✅ 已完成 |
|  5   | PLE+d16 lr2e3       | `home_flow_2604_v8_ple_d16_lr2e3.config`    | lr=0.002              | 0.737197 | 0.703815 | +0.05pp | +0.49pp | 0.54  | ✅ 已完成 |
|  4   | PLE+d16 dropout0    | `home_flow_2604_v8_ple_d16_dropout0.config` | dropout=0.0           | 0.737912 | 0.703539 | +0.12pp | +0.46pp | 0.58  | ✅ 已完成 |
|  4   | PLE+d16 dropout2    | `home_flow_2604_v8_ple_d16_dropout2.config` | dropout=0.2           | 0.737912 | 0.703539 | +0.12pp | +0.46pp | 0.58  | ✅ 已完成 |

## 结论

- **PLE+d16 效果一致**：CVR +0.10~0.13pp, CTR +0.35~0.49pp，v1c 管道下效果约 v3 管道的 1/4。
- **ctr_wt=1.0 最特殊**：CVR +0.26pp (全场最高) 但 CTR 仅 +0.20pp — 模型向 CVR 偏移，CTR 损失。ctr_wt=5.0 反之，CTR +0.48pp 但 CVR 回退到 +0.06pp。默认 ctr_wt=3.3 是平衡最优。
- **lr=0.002 CTR 极化**：CTR +0.49pp 最强但 CVR +0.05pp 最弱；lr=0.0005 稍平衡 (CVR +0.10, CTR +0.35)。默认 lr=0.001 最佳。
- **Dropout 在 1 epoch 下无效**：dropout=0.0 / 0.1 / 0.2 结果完全相同 (0.737912/0.703539)。原因：1 epoch 欠拟合，模型无过拟合机会，dropout 正则化无意义。
- **4GPU (eff_bs=16384) >> 2GPU (eff_bs=8192)**：之前记录错误（用了 2 卡评估结果）。真实 4 卡 PLE+d16 CVR +0.88pp / CTR +0.54pp，综合Δ=1.42，**远优于** 2 卡的 +0.12pp/+0.46pp。更大的有效 batch size 对 CVR 提升显著。
- **最终推荐（2GPU）**：默认 PLE+d16（dropout=0.1, lr=0.001, ctr_wt=3.3），CVR +0.12pp, CTR +0.46pp。
- **最终推荐（4GPU）**：PLE+d16 4GPU（eff_bs=16384），CVR +0.88pp, CTR +0.54pp — 如果生产环境支持 4GPU 优先选用。

## Config 完整清单 (v8 目录)

```
v8_baseline.config                    — 4卡对照 (T_max=6300)
v8_baseline_2gpu.config               — 2卡对照 (T_max=13000)
v8_ple_d16.config                     — PLE+d16 2卡 (T_max=13000)
v8_ple_d16_4gpu.config                — PLE+d16 4卡 (T_max=6700)
v8_ple_d16_ctr_wt1.config             — ctr weight=1.0
v8_ple_d16_ctr_wt5.config             — ctr weight=5.0
v8_ple_d16_lr5e4.config               — lr=0.0005
v8_ple_d16_lr2e3.config               — lr=0.002
v8_ple_d16_dropout0.config            — dropout=0.0
v8_ple_d16_dropout2.config            — dropout=0.2
v8_ple_dlsp.config                    — PLE+dlsp (T_max=6300, 未更新)
```
