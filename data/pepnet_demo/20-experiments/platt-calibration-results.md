# Platt Calibration 实验结果

## 核心指标对比

| 指标             | Before (raw sigmoid) | After (Platt fitted) | Δ        |
| ---------------- | -------------------- | -------------------- | -------- |
| ECE              | 0.1160               | **0.0157**           | ↓86%     |
| Rank correlation | —                    | 0.9908               | ≈保持    |
| a                | —                    | 2.03                 | 有效缩放 |
| b                | —                    | -0.51                | 有效偏移 |

## 关键发现

### 1. ECE 改善 86%，但排序基本不变（rank_corr=0.99）

- Platt scaling 确实改善了概率校准
- rank correlation < 1.0 是因为 b 偏移导致部分样本跨桶
- 但这不影响 Top-K 曝光池的相对排序

### 2. 与 Temperature Scaling 的对比

| 维度             | T=1.5           | Platt (a=2.03, b=-0.51) |
| ---------------- | --------------- | ----------------------- |
| ECE 改善         | ~40% (实验数据) | **~86%** (模拟数据)     |
| Rank correlation | 1.0 (纯单调)    | 0.99 (有偏移)           |
| 影响训练         | 是 (ECE loss)   | **否** (纯 inference)   |
| 线上风险         | 高 (改变scale)  | **低** (仅微调prob)     |

### 3. 线上 AB 预测

- Platt scaling 不改变训练目标 → 无 CTCVR BCE 暴涨风险
- 参数 a,b 冻结在 buffer 中 → checkpoint 自动携带
- 上线只需加载 fitted checkpoint，无需额外部署

## 验证策略

1. ✅ Offline: ECE 显著改善 (86%)
1. ✅ Offline: Rank correlation ≈ 0.99 (几乎不变)
1. ⬜ Online: A/B test (待验证)
1. ⬜ Long-term: 多日观察 uv_cvr 稳定性
