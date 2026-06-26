______________________________________________________________________

## date: 2026-05-30 tags: [archive, error, log] status: archived related: ["[[../40-errors/index]]"]

# 实验报错记录

## 1. ODPS 网络连接断开

### 现象

```
requests.exceptions.ConnectionError: Caught ConnectionError in DataLoader worker process 8.
...
ConnectionResetError: [Errno 104] Connection reset by peer
```

DataLoader worker 读取 ODPS 表时连接被对端重置，发生在训练第一步（step 0）。

### 原因

ODPS tunnel 连接超时或网络波动。DLC 训练节点到 ODPS 服务端之间的 TCP 连接被中间设备或服务端主动断开。

### 出现次数

- pepnet_cdot_domain_dcnv2_warmup1000: 1 次
- pepnet_cdot_domain_dcnv2_warmup1000_domain2: 1 次

### 解法

**重跑任务**。基础设施问题，重试即可恢复，非模型/config 错误。

______________________________________________________________________

## 2. OSS 挂载断开

### 现象

训练过程中 OSS 挂载目录 `/oss/` 不可读，DataLoader 读取 `oss://` 路径的特征数据时报错。

### 原因

DLC 集群的 OSS 挂载点（ossfs）偶发断开，多发生在长任务中。

### 出现次数

1 次（pepnet_cdot_domain 训练中期）

### 解法

重跑任务。必要时缩短任务时间（降低 epoch 或 step 数）。

______________________________________________________________________

## 3. `eval_batch_size` 字段不存在

### 现象

在 config 中设置 `eval_config { eval_batch_size: 4096 }` 导致 proto 解析报错。

### 原因

`EvalConfig` proto 只包含两个字段：

```protobuf
message EvalConfig {
    optional uint32 num_steps = 1;
    optional uint32 log_step_count_steps = 2 [default = 10];
}
```

`eval_batch_size` 不存在。Eval 使用 `data_config.batch_size`。

### 出现次数

1 次（初始 config 编写时）

### 解法

删除 `eval_batch_size` 字段。如需不同 batch size，通过 `data_config.batch_size` 控制。

______________________________________________________________________

## 4. FX_TRACE / JIT_SCRIPT 单测失败

### 现象

本地运行 `pytest tests/` 时，FX symbolic trace 或 JIT script 相关的单测失败。

### 原因

TorchEasyRec 部分单测需要 `fbgemm_gpu` CUDA 扩展。本地开发环境为 CPU/MPS，缺少 `fbgemm_gpu`，导致 FX trace 和 JIT compile 路径无法通过。

### 出现次数

每次 full test suite

### 解法

通过 mock prelude 跳过 GPU 相关组件：

```python
import test_prelude  # /tmp/test_prelude.py
```

只运行模型特定单测（如 `tzrec/models/pepnet_v2_test.py`）。

______________________________________________________________________

## 5. `save_checkpoints_epochs` 与 `save_checkpoints_steps` 互斥

### 现象

Config 中同时设置 `save_checkpoints_epochs: 1` 和 `save_checkpoints_steps: 500`，导致行为不符合预期。

### 原因

`main.py` L352-356 中两者互斥（XOR）。同时设置时只有其中一个生效。

### 出现次数

1 次（step-based eval 配置时）

### 解法

使用 step-based 时设 `save_checkpoints_epochs: 0` + `save_checkpoints_steps: 500`。

______________________________________________________________________

## 6. `tod_wall` node 非预期

### 现象

`torch.fx.symbolic_trace` 对 PEPNet_v2 模型 trace 时报 `tod_wall` node 未预期错误。

### 原因

`tod_wall` 函数（`torchrec` 的 time-of-day 模块）内部使用 `datetime.now()`，FX trace 无法处理。

### 出现次数

1 次（开发 PEPNet_v2 时）

### 解法

使用 `@torch.fx.wrap` 装饰器标记 `datetime` 操作为叶子节点：

```python
@torch.fx.wrap
def get_tod_wall(x):
    ...
```

______________________________________________________________________

## 7. Attention `key_padding_mask` 广播

### 现象

多头注意力中 `key_padding_mask` 维度不匹配 `(B, L)` vs `(B, 1, 1, L)`。

### 原因

TorchEasyRec 的 attention 实现和序列特征拼接方式之间的维度约定不一致。

### 出现次数

1 次（开发序列特征处理时）

### 解法

显式 reshape mask 维度。

______________________________________________________________________

## 错误分类统计

| 类型     | 错误                     |  频率  | 严重程度 | 预防         |
| -------- | ------------------------ | :----: | :------: | ------------ |
| 基础设施 | ODPS Connection Reset    | ⭐⭐⭐ |    中    | 重试         |
| 基础设施 | OSS 挂载断开             |  ⭐⭐  |    中    | 重试         |
| 配置     | `eval_batch_size` 不存在 |   ⭐   |    低    | 查阅 proto   |
| 配置     | `save_checkpoints` 互斥  |   ⭐   |    低    | 查阅源码     |
| 环境     | fbgemm_gpu 缺失          | ⭐⭐⭐ |    低    | mock 跳过    |
| 模型     | FX trace 不支持 runtime  |   ⭐   |    低    | `@fx.wrap`   |
| 模型     | attention mask 广播      |   ⭐   |    低    | 显式 reshape |

## 经验总结

1. **DLC 基础设施不稳定** — ODPS 和 OSS 都是偶发网络问题，重跑即可。必要的话在 DataLoader 侧加 `retry` 机制。
1. **TorchEasyRec proto 需查阅源码** — proto 字段不如文档齐全，遇到字段报错直接在 `.proto` 文件确认。
1. **fbgemm_gpu = CUDA only** — 本地开发环境无法跑完整测试，需 mock 或直接跳过 GPU 相关用例。
1. **FX trace 不兼容所有 Python 特性** — 使用 `torch.fx.wrap` 标记非 torch 操作。
