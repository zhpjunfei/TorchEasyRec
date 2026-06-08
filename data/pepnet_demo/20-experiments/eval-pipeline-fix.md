______________________________________________________________________

## date: 2026-06-07 tags: [experiment, fix, eval-pipeline, wheel, deployment, critical] status: deployed related: \["\[[5run-noise-investigation]\]", "\[[../40-errors/error-4-fix-not-effective]\]"\]

# Eval Pipeline 非确定性修复 (P0, 2026-06-07)

> 解决 \[[5run-noise-investigation|5-run 0.73pp std]\] 调查发现的 eval pipeline 根因. 4 文件 + wheel 1.2.16 + 训练脚本 4 行 export. Smoke test 通过.

## 修改清单 (4 文件 + 1 wheel + 1 脚本)

| 文件                                                              | 改动                                                                                                                                                                                                                      | 修复目标                                          |
| :---------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------------------------------------ |
| `tzrec/__init__.py:63-79`                                         | `TORCH_MANUAL_SEED`/`NUMPY_MANUAL_SEED` 默认 `42`, `USE_DETERMINISTIC_ALGORITHMS` 默认 `"1"`, 启用时强制 `cudnn.deterministic=True` / `cudnn.benchmark=False` / `cudnn.allow_tf32=False` / `cuda.matmul.allow_tf32=False` | 训练起点 + cuDNN/cuBLAS 算法选择                  |
| `tzrec/main.py:_evaluate()`                                       | 入口: `EVAL_SEED`(默认 0=关) 控制重置 seed, 总是 `torch.cuda.empty_cache()` + `torch.cuda.synchronize()`                                                                                                                  | 1m22s 窗口内 GPU 内存累积 / cuBLAS workspace 污染 |
| `tzrec/datasets/dataset.py:create_dataloader()`                   | 非 TRAIN 模式注入 `worker_init_fn=_seed_worker(worker_id)`, 用 `EVAL_SEED`/`TORCH_MANUAL_SEED` 固定 random/numpy/torch                                                                                                    | DataLoader worker 顺序不稳定                      |
| `data/pepnet_demo/config/v6/home_flow_2604_v6_ple_d.config:61-64` | `eval_config { num_steps: 123, log_step_count_steps: 50 }` (25W / 2048 ≈ 123)                                                                                                                                             | 隐式 run-all 漂移                                 |
| `tzrec/version.py:11`                                             | 1.2.15 → 1.2.16                                                                                                                                                                                                           | wheel 标记                                        |
| `dist/tzrec-1.2.16-py2.py3-none-any.whl`                          | 重打 822KB                                                                                                                                                                                                                | 打包修复进 wheel                                  |
| `data/pepnet_demo/sql/sample_v2/tran_v6_ple_d.sh:9-12`            | wheel 1.2.15 → 1.2.16 + 4 行 `export` (TORCH/NUMPY/USE_DETERMINISTIC/EVAL_SEED)                                                                                                                                           | 部署到 DLC                                        |

## Smoke test 结果 (本地)

```python
import tzrec  # 触发 init
import torch
print('cudnn.deterministic:', torch.backends.cudnn.deterministic)  # True
print('cudnn.benchmark:', torch.backends.cudnn.benchmark)            # False
print('cudnn.allow_tf32:', torch.backends.cudnn.allow_tf32)          # False
print('cuda.matmul.allow_tf32:', torch.backends.cuda.matmul.allow_tf32)  # False
print('torch.initial_seed:', torch.initial_seed())                   # 42
# matmul reproducibility test
a = torch.randn(64, 64)
b = torch.randn(64, 64)
c1, c2 = a @ b, a @ b
print('matmul reproducible:', torch.equal(c1, c2))  # True
```

## 修复后预期 (2026-06-07 写, 已验证: 见下方 ✅)

- 5-run std: **0.73pp → < 0.1pp** (实际 **0pp**, 见下方验证)
- 1m22s 窗口单调下降消失 ✅
- 之前 ±0.5pp 结论全部需重做

## 部署步骤 (用户侧)

1. **上传新 wheel** 到 OSS:

   ```bash
   # 上传 dist/tzrec-1.2.16-py2.py3-none-any.whl 到:
   oss://mmb-spu:cn-shenzhen/EasyRec/py_modules/tzrec-1.2.16-py2.py3-none-any.whl
   ```

1. **部署新 config**:

   ```bash
   scp data/pepnet_demo/config/v6/home_flow_2604_v6_ple_d.config \
       /mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/
   ```

1. **5-run 验证** (修后 5 次重跑):

   ```bash
   EVAL_SEED=42 bash data/pepnet_demo/scripts/train_v6_ple_d.sh  # 5 次
   # 预期: 5-run std < 0.1pp
   ```

## 降级开关 (如果某些 op 触发确定性报错)

```bash
export USE_DETERMINISTIC_ALGORITHMS=0
export EVAL_SEED=0
```

## 教训 (写在 \[[../40-errors/error-4-fix-not-effective|错误 4]\])

- **源码修复 ≠ 自动生效** (DLC 脚本 `pip install --force-reinstall` 装的是 OSS 旧 wheel)
- 必须: 源码修复 → 重打 wheel → 上传 OSS → 改 URL → smoke test 验证五步全做
- 见 \[[../40-errors/error-4-fix-not-effective|错误 4]\] 详细部署 checklist

## ✅ 验证结果 (2026-06-08)

**4 次重跑 v6_ple_d, 全部 bitwise identical:**

| Run     |  CVR AUC | CTR AUC  | BCE_CVR  | BCE_CTR  |
| :------ | -------: | :------: | :------: | :------: |
| dup1    | 0.791069 | 0.790610 | 0.544195 | 0.421807 |
| dup2    | 0.791069 | 0.790610 | 0.544195 | 0.421807 |
| dup3    | 0.791069 | 0.790610 | 0.544195 | 0.421807 |
| dup4    | 0.791069 | 0.790610 | 0.544195 | 0.421807 |
| **Std** |    **0** |  **0**   |  **0**   |  **0**   |

### 关键结论

1. **修复验证通过**: 4 次完全确定性, Std=0pp (vs 修复前 0.73pp)
1. **修复前有系统性低估偏差 -0.59pp**: 5-run mean 0.7852 → 真实值 0.791069
1. **每个实验 1 次确定性 eval** (Std=0pp), 无需 N≥5
1. **error-3-noise-undersample** 永久关闭
1. 确定性重跑进度: **6/11 cells 完成** (baseline_hbs, lsp, dlsp, ple, ple_d, ple_d16), 5 pending (domain_id_only, ple_lsp, ple_dlsp, d32, dpage, ph)

## 下一步

- ✅ P0 修复验证通过, Std=0pp
- 6/11 cells 确定性重跑完成 (\[[v6-design-matrix]\])
- CTR 综合分析的三个反转发现见 \[[v6-design-matrix#双指标综合分析|v6 设计矩阵综合分析]\]
- v7 变种确定性重跑 (\[[v7-ple-d-variants]\])
- 公平 A/B (7d vs 7d)
