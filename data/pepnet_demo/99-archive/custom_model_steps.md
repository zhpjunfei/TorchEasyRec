# TorchEasyRec 自定义模型流程

本文以 `PEPNet_v2` 为例，说明在 TorchEasyRec 中新增一个模型需要完成的 8 个步骤。

______________________________________________________________________

## ① proto message 定义

**文件**: `tzrec/protos/models/multi_task_rank.proto`（多任务排序类） / `rank_model.proto`（单任务排序） / `match_model.proto`（召回）

定义模型的配置结构 —— config 文件中能设置哪些参数、类型、默认值。

```protobuf
message PEPNet_v2 {
    optional uint32 epnet_hidden_unit = 1;
    optional float  epnet_gamma = 2 [default = 2.0];
    optional string epnet_scale_type = 3 [default = 'tanh'];

    repeated uint32 ppnet_hidden_units = 4;
    optional string ppnet_activation = 5 [default = 'nn.ReLU'];
    repeated float ppnet_dropout_ratio = 6;
    optional float  ppnet_gamma = 7 [default = 2.0];
    optional string ppnet_scale_type = 8 [default = 'tanh'];

    optional CDOTConfig cdot = 9;
    optional string cdot_group_name = 10 [default = 'all'];
    optional string bias_group_name = 11 [default = 'all'];
    optional string lhuc_group_name = 12 [default = 'domain'];
    optional string main_group_name = 13 [default = 'all'];

    repeated TaskTower task_towers = 14;
    optional bool cvr_add_ctr_logits = 15 [default = true];
}
```

编译后生成 `multi_task_rank_pb2.py`，内含 Python 类 `PEPNet_v2`。模型在 `__init__` 中通过 `self._model_config` 读取这些字段。

______________________________________________________________________

## ② 注册 oneof 字段

**文件**: `tzrec/protos/model.proto`

把模型类型加入 `ModelConfig` 的 `oneof model`，定义配置文件中用什么字段名引用这个模型。

```protobuf
message ModelConfig {
    repeated FeatureGroupConfig feature_groups = 1;

    oneof model {
        // 排序模型 (100-199)
        DLRM dlrm = 100;
        DeepFM deepfm = 101;
        // ...

        // 多任务排序模型 (200-299)
        PEPNet pepnet = 206;
        UltraHSTU ultra_hstu = 207;
        PEPNet_v2 pepnet_v2 = 208;          // ← 新增

        // 匹配模型 (300-399)
        DSSM dssm = 301;
        // ...
    }
}
```

### oneof 解析链路

```
config.WhichOneof("model") → "pepnet_v2"                    # snake_case 字段名
getattr(config, "pepnet_v2").__class__.__name__ → "PEPNet_v2"  # PascalCase 类名
BaseModel.create_class("PEPNet_v2") → Python 模型类
```

### 字段编号命名空间

| 范围    | 用途           |
| ------- | -------------- |
| 100-199 | 单任务排序模型 |
| 200-299 | 多任务排序模型 |
| 300-399 | 匹配/召回模型  |
| 400-499 | TDM            |
| 500+    | 通用模型       |

______________________________________________________________________

## ③ 编译 proto

**命令**:

```bash
python -m grpc_tools.protoc -I . \
    tzrec/protos/*.proto tzrec/protos/models/*.proto \
    --python_out=. --pyi_out=.
```

**作用**: 将 `.proto` 编译为 Python 可用的 `_pb2.py`（序列化/反序列化）和 `_pb2.pyi`（类型提示）。

编译产物核心是一个序列化的 `FileDescriptor`（嵌入在 `.py` 文件中的二进制字符串），protobuf 运行时通过 `_descriptor_pool.Default().AddSerializedFile(...)` 反序列化来获得 message schema。

**必须编译，否则步骤 ① 和 ② 不会生效** —— Python 无法 import 新 message，`model_pb2.ModelConfig` 也不认识 `pepnet_v2` 字段。

______________________________________________________________________

## ④ 模型 Python 文件

**文件**: `tzrec/models/pepnet_v2.py`

```python
class PEPNet_v2(MultiTaskRank):
    """PEPNet_v2: Enhanced PEPNet with CDOT, Bias, LHUC-EPNet, LHUC-PPNet."""

    def __init__(self, model_config, features, labels, sample_weights=None, **kwargs):
        super().__init__(...)
        # 读取 proto 配置
        self._main_group_name = self._model_config.main_group_name
        # 构建网络层
        self.epnet = LHUC_EPNet(...)
        self.cdot = CDOT(...)
        self.component_ln = nn.ModuleDict(...)
        # ...

    def predict(self, batch):
        # 前向逻辑
```

### 类名约束

类名必须和 proto message 类名**完全一致**（大小写敏感）：

```
which_msg() 返回 "PEPNet_v2"  →  Python 类必须是 class PEPNet_v2
```

### 自动注册机制

`BaseModel` 使用 `RegisterABCMeta` 元类。Python 解释器加载本文件时，元类的 `__new__` 自动执行：

```python
register_class(_MODEL_CLASS_MAP, "PEPNet_v2", PEPNet_v2)
```

把类名注册进全局映射表。`auto_import()` 扫描 `tzrec/models/` 目录，自动 import 所有非 `_test` 的 `.py` 文件，触发上述注册。

______________________________________________________________________

## ⑤ 测试文件

**文件**: `tzrec/models/pepnet_v2_test.py`

```python
class PEPNet_v2Test(unittest.TestCase):
    def test_pepnet_v2_no_cdot(self):
        # 构造 PEPNet_v2 proto config
        pepnet_v2_config = multi_task_rank_pb2.PEPNet_v2(
            epnet_hidden_unit=256,
            # ...
        )
        model_config = model_pb2.ModelConfig(
            feature_groups=feature_groups,
            pepnet_v2=pepnet_v2_config,
        )
        # 构建模型
        pepnet_v2 = PEPNet_v2(model_config, features, labels, ...)
        init_parameters(pepnet_v2)
        pepnet_v2.eval()
        # mock 输入 forward
        predictions = pepnet_v2(batch)
        # 验证 shape / 数值
        self.assertEqual(predictions["ctr"].shape, (batch_size, 1))
```

**作用**: 验证模型结构正确、前向能跑通、输出 shape 符合预期。

测试需要手动构造 proto message 和 mock batch，因为正常流程中这些由框架的 DataParser 和 config 解析器生成。这是**第一个不依赖框架训练流程就能发现 bug** 的地方（维度不匹配、参数未注册、forward 崩溃等）。

______________________________________________________________________

## ⑥ 配置文件

**文件**: `data/pepnet_demo/config/home_flow_2604_pepnet.config`

```protobuf
train_input_path: "odps://{PROJECT}/tables/sample_train"
eval_input_path: "odps://{PROJECT}/tables/sample_eval"
model_dir: "experiments/pepnet_v2"

train_config {
    sparse_optimizer { adagrad_optimizer { lr: 0.001 } }
    dense_optimizer { adam_optimizer { lr: 0.001 } }
    num_epochs: 1
}

data_config {
    batch_size: 8192
    dataset_type: OdpsDataset
    label_fields: "clk" "buy"
    num_workers: 8
}

feature_configs {
    id_feature {
        feature_name: "user_id"
        expression: "user:user_id"
        embedding_dim: 16
        hash_bucket_size: 1000000
    }
}
# ...

model_config {
    feature_groups {
        group_name: "all"
        feature_names: "user_id" "item_id" "cate_id"
        group_type: DEEP
    }
    pepnet_v2 {
        epnet_hidden_unit: 256
        ppnet_hidden_units: [256]
        cdot { input_dim: 16 output_dim: 4 mid_dim: 32 }
        bias_group_name: "all"
        lhuc_group_name: "domain"
        main_group_name: "all"
        task_towers {
            tower_name: "ctr"
            label_fields: "clk"
            mlp { hidden_units: [512, 256, 128] }
        }
        task_towers {
            tower_name: "cvr"
            label_fields: "buy"
            mlp { hidden_units: [512, 256, 128] }
        }
        cvr_add_ctr_logits: true
    }
    losses {
        binary_cross_entropy {}
    }
    metrics { auc {} }
    num_class: 2
}
```

**作用**: 最终的模型使用入口。配置串联了：

- 特征定义与分组
- 模型类型与参数
- Loss、Metric、Optimizer

______________________________________________________________________

______________________________________________________________________

## ⑦ E2E 验证

前 6 步完成后，需要做端到端验证确保模型能跑通。验证分三个层次：

### 层次一：模块级测试

对新引入的子模块（如 `CDOT`、`LHUC_EPNet`、`LHUC_PPNet`）写独立测试，验证 forward、backward、输出 shape：

**文件**: `tzrec/modules/cdot_test.py` / `tzrec/modules/lhuc_net_test.py`

```python
class CDOTTest(unittest.TestCase):
    def test_cdot_basic(self):
        cdot = CDOT(num_slots=4, input_dim=8, output_dim=4, mid_dim=16)
        x = torch.randn(2, 4, 8)
        allint_out, allint_mid_out = cdot(x)
        self.assertEqual(allint_out.size(), (2, 16))  # batch x num_slots*output_dim

    def test_cdot_gradient_flow(self):
        cdot = CDOT(num_slots=3, input_dim=8, output_dim=4, mid_dim=8)
        x = torch.randn(2, 3, 8, requires_grad=True)
        allint_out, _ = cdot(x)
        loss = allint_out.sum()
        loss.backward()
        for name, param in cdot.named_parameters():
            self.assertIsNotNone(param.grad, f"gradient missing for {name}")
```

测试要点：

- forward 输出 shape 正确
- 梯度能反向传播到所有参数（gradient flow）
- 极端输入（全零、大数值）不产生 NaN/Inf

### 层次二：模型级测试

对完整模型做前向测试，覆盖不同配置组合：

**文件**: `tzrec/models/pepnet_v2_test.py`

```bash
# 运行命令（需要 mock 缺失的依赖）
TZREC_SKIP_AUTO_IMPORT=1 python3 -c "
import sys; sys.path.insert(0, '/tmp')
import test_prelude
import pytest
sys.exit(pytest.main(['-v', 'tzrec/models/pepnet_v2_test.py',
    'tzrec/modules/cdot_test.py', 'tzrec/modules/lhuc_net_test.py']))
"
```

输出预期:

```
tzrec/modules/cdot_test.py::CDOTTest::test_cdot_basic PASSED
tzrec/modules/lhuc_net_test.py::LHUC_EPNetTest::test_epnet_basic PASSED
tzrec/models/pepnet_v2_test.py::PEPNet_v2Test::test_pepnet_v2_no_cdot PASSED
tzrec/models/pepnet_v2_test.py::PEPNet_v2Test::test_pepnet_v2_with_cdot PASSED
```

### 层次三：E2E 训练验证

在有 `fbgemm_gpu` 的完整环境中，使用第⑥步的 config 文件跑真实训练：

```bash
python tzrec/train_eval.py \
    --pipeline_config_path=data/pepnet_demo/config/home_flow_2604_pepnet.config \
    --train_input_path=odps://{PROJECT}/tables/train \
    --eval_input_path=odps://{PROJECT}/tables/eval \
    --model_dir=experiments/pepnet_v2
```

验证点：

- 训练启动不报错，loss 能正常下降
- 定期 eval 能产出 metric（AUC、Recall 等）
- checkpoint 能正常保存和恢复
- 导出为 TorchScript 无报错

### 关于 mock 环境

当开发环境缺少 `fbgemm_gpu`、`graphlearn` 等依赖时，可以用 `test_prelude.py` 做 mock 替换：

```python
# /tmp/test_prelude.py 核心机制
class FbgemmMetaFinder:
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        if fullname.startswith('fbgemm_gpu'):
            return ModuleSpec(fullname, FbgemmAutoLoader(...))
sys.meta_path.insert(0, FbgemmMetaFinder)

# Python fallback 替换 fbgemm op
_jt._fbgemm_permute_pooled_embs = _python_permute_pooled_embs
```

**mock 只能用于层次一和二的测试，不能用于层次三的 E2E 训练。**

______________________________________________________________________

## ⑧ 打包 whl

所有验证通过后，将项目打包为 wheel 分发给线上环境。

### 安装构建工具

```bash
pip install build
```

### 打包

```bash
cd /path/to/TorchEasyRec
python3 -m build --wheel
```

### 产出

```
dist/tzrec-1.2.12-py2.py3-none-any.whl
```

文件名各段含义:

| 段           | 值        | 含义                                      |
| ------------ | --------- | ----------------------------------------- |
| distribution | `tzrec`   | 包名（`setup.cfg` 的 `name`）             |
| version      | `1.2.12`  | 版本号（`tzrec/version.py` 读取）         |
| python tag   | `py2.py3` | 兼容 Python 2 和 3（纯 Python 无 C 扩展） |
| abi tag      | `none`    | 无 ABI 约束                               |
| platform tag | `any`     | 跨平台                                    |

### 构建流程

```
python -m build --wheel
  1. 读取 setup.cfg → setuptools 构建后端
  2. 执行 python setup.py bdist_wheel
  3. 复制源码到临时 build/ 目录
      copying tzrec/models/pepnet_v2.py → build/.../wheel/...
      copying tzrec/protos/model_pb2.py → build/.../wheel/...
      ...
  4. 安装 egg-info 元数据（METADATA、WHEEL、RECORD）
  5. 压缩为 .whl（本质是 .zip 改后缀）
  6. 清理临时目录
```

### 安装到目标环境

```bash
pip install dist/tzrec-1.2.12-py2.py3-none-any.whl
```

______________________________________________________________________

## 完整数据流

```
配置文件 (.config)
  → protobuf 解析为 ModelConfig (model_pb2.ModelConfig)
    → config.WhichOneof("model") = "pepnet_v2"
      → getattr(config, "pepnet_v2") → PEPNet_v2 message
        → .__class__.__name__ = "PEPNet_v2"   # config_util.which_msg()
          → BaseModel.create_class("PEPNet_v2")
            → _MODEL_CLASS_MAP["PEPNet_v2"] → PEPNet_v2 类
              → PEPNet_v2(model_config, features, labels, ...)
                → .predict(batch)              # 训练 / 评估 / 导出

# 验证与分发流程
模型实现 → 模块测试 → 模型测试 → E2E 训练 → 打包 whl → 部署
```

______________________________________________________________________

## 总结

| 步骤                 | 文件/命令                  | 输入                   | 产出                       |
| -------------------- | -------------------------- | ---------------------- | -------------------------- |
| ① proto message 定义 | `protos/models/*.proto`    | protobuf schema        | message 数据结构           |
| ② 注册 oneof         | `protos/model.proto`       | oneof 字段             | 配置文件可引用该模型       |
| ③ 编译 proto         | `grpc_tools.protoc`        | `.proto` 文件          | `_pb2.py` / `_pb2.pyi`     |
| ④ 模型实现           | `models/*.py`              | proto config           | `PEPNet_v2` 类（自动注册） |
| ⑤ 测试               | `models/*_test.py`         | mock config + data     | 验证正确性                 |
| ⑥ 配置文件           | `*.config`                 | 模型 + 数据 + 训练参数 | 训练入口                   |
| ⑦ E2E 验证           | 模块测试 + 模型测试 + 训练 | mock / 真实数据        | 确认模型可正常训练导出     |
| ⑧ 打包 whl           | `python -m build --wheel`  | 全部源码 + proto       | `.whl` 分发包              |
