# TorchEasyRec E2E 训练流程

本文以 `PEPNet_v2` 为例，说明从配置到训练的完整数据流。

______________________________________________________________________

## 1. 启动命令

```bash
python tzrec/train_eval.py \
    --pipeline_config_path=data/pepnet_demo/config/home_flow_2604_pepnet.config \
    --train_input_path=... \
    --eval_input_path=... \
    --model_dir=experiments/pepnet_v2
```

入口 `tzrec/train_eval.py` → 调用 `tzrec/main.py::train_and_evaluate()`。

______________________________________________________________________

## 2. 完整数据流

```
配置文件 (.config)
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 1. config_util.load_pipeline_config()                          │
│    → 读取 .config 文件，protobuf text_format.Merge() 解析     │
│      为 EasyRecConfig（pipeline_pb2.EasyRecConfig）           │
│    → 包含 ModelConfig + DataConfig + TrainConfig + ...        │
│   文件: tzrec/utils/config_util.py:25                         │
└────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. init_process_group()                                        │
│    → 初始化 torch.distributed                                 │
│    → 确定 device（cuda / cpu）                                 │
│   文件: tzrec/utils/dist_util.py:57                           │
└────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. _create_features(feature_configs)                           │
│    → 遍历 feature_configs，创建 Feature 对象列表               │
│    → IdFeature / RawFeature / SequenceFeature / ...           │
│    → 每个 Feature 自动注册对应的 embedding 表                    │
│   文件: tzrec/main.py:94                                       │
└────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 4. create_dataloader(data_config, features, input_path)        │
│    → 根据 dataset_type 创建 IterableDataset（Dataset）          │
│      （OdpsDataset / ParquetDataset / CsvDataset / ...）       │
│                                                                 │
│    Dataset 内部结构:                                            │
│    ├── Reader：读取原始数据（ODPS / Parquet / CSV / Kafka）    │
│    ├── DataParser：将原始数据解析为 Batch 对象                 │
│    │   ├── parse() → Dict[str, Tensor]                         │
│    │   └── to_batch() → Batch                                  │
│    │       ├── dense_features: Dict[str, KeyedTensor]          │
│    │       ├── sparse_features: Dict[str, KeyedJaggedTensor]   │
│    │       └── labels: Dict[str, Tensor]                       │
│    └── NegativeSampler（可选）                                  │
│                                                                 │
│    → Dataset.__iter__() 中:                                    │
│      for input_data in reader.to_batches(...):                 │
│          output_data = sampler(input_data)  # 负采样（可选）    │
│          batch = data_parser.parse(output_data)                 │
│          batch = data_parser.to_batch(output_data)              │
│          yield batch                                            │
│                                                                 │
│    → 外层包 DataLoader(batch_size=None)                         │
│   文件: tzrec/datasets/dataset.py:740, 301                     │
│         tzrec/datasets/data_parser.py:184                      │
└────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 5. _create_model(model_config, features, labels)               │
│    → config_util.which_msg(model_config, "model")              │
│      → model_config.WhichOneof("model") = "pepnet_v2"          │
│      → getattr(config, "pepnet_v2").__class__.__name__         │
│        = "PEPNet_v2"                                           │
│    → BaseModel.create_class("PEPNet_v2")                       │
│      → _MODEL_CLASS_MAP 中查找，返回 PEPNet_v2 类              │
│    → model = PEPNet_v2(model_config, features, labels, ...)    │
│                                                                 │
│    __init__ 中:                                                 │
│    ├── self.init_input() → EmbeddingGroup（所有 embedding）     │
│    ├── 读取 self._model_config 构造各模块                      │
│    │   ├── CDOT cdot = CDOT(num_slots, input_dim, ...)         │
│    │   ├── LayerNorm nn.ModuleDict("main"/"allint_out"/...)    │
│    │   ├── LHUC_EPNet epnet(lhuc_dim, output_dim, ...)         │
│    │   └── LHUC_PPNet task_towers[](input_dim, nn_dims, ...)   │
│    └── loss/metric 注册                                         │
│                                                                 │
│    → 外包 TrainWrapper(model)                                   │
│   文件: tzrec/main.py:127                                       │
│         tzrec/utils/config_util.py:73                           │
│         tzrec/models/model.py:37 (RegisterABCMeta)              │
│         tzrec/models/pepnet_v2.py:39                            │
└────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 6. 创建优化器（main.py:662-756）                                │
│    → Sparse optimizer（embedding 参数）                        │
│      apply_optimizer_in_backward(fused_optimizer, embedding)   │
│    → Dense optimizer（MLP 参数）                                │
│      KeyedOptimizerWrapper(adamw, params)                      │
│    → part_optimizers（分治法，如 weight_decay 只对 .weight）   │
│    → CombinedOptimizer([sparse, dense, part, ...])             │
│    → TZRecOptimizer（包裹 grad scaler + gradient accumulation）│
│   文件: tzrec/main.py:662                                       │
└────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 7. Sharding plan（分布式）                                      │
│    → EmbeddingShardingPlanner.collective_plan()                │
│    → DistributedModelParallel(model, device, sharders, plan)   │
│    → 单机单卡相当于 DDP                                         │
│   文件: tzrec/utils/plan_util.py:94                             │
└────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 8. _train_and_evaluate(model, optimizer, dataloaders)          │
│    → for i_epoch in range(num_epochs):                        │
│      │                                                         │
│      ├── create_train_pipeline(model, optimizer)               │
│      │   → 有 sparse: TrainPipelineSparseDist                  │
│      │   → 纯 dense: TrainPipelineBase                          │
│      │                                                         │
│      └── for i_step in range(max_step_per_epoch):              │
│          │                                                     │
│          ├── pipeline.progress(iterator)                       │
│          │   ├── _next_batch()                                 │
│          │   │   → next(dataloader) → Batch                    │
│          │   │                                                 │
│          │   ├── forward: TrainWrapper.forward(batch)          │
│          │   │   ├── with autocast:                            │
│          │   │   │   predictions = model.predict(batch)        │
│          │   │   │   losses = model.loss(predictions, batch)   │
│          │   │   │   total_loss = sum(losses.values())         │
│          │   │   └── return total_loss, (losses, preds, batch) │
│          │   │                                                 │
│          │   └── backward: loss.sum().backward()               │
│          │       → 含 grad scaler + gradient accumulation      │
│          │                                                     │
│          ├── optimizer.step()                                  │
│          ├── lr_scheduler.step()                               │
│          ├── model.update_metric(predictions, batch)           │
│          │                                                     │
│          └── 定期:                                              │
│              ├── checkpoint_util.save_model()                  │
│              │   → model/optimizer state dict                  │
│              └── _evaluate(model, eval_dataloader)             │
│                  → with torch.no_grad():                       │
│                    ├── forward（同训练，无 backward）            │
│                    ├── update_metric(predictions, batch)       │
│                    └── compute_metric() → AUC / Recall / ...   │
│                                                                 │
│   文件: tzrec/main.py:317 (_train_and_evaluate)                 │
│         tzrec/models/model.py:235 (TrainWrapper)               │
│         tzrec/utils/dist_util.py:335 (create_train_pipeline)   │
└────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ 9. 导出（训练完成后）                                          │
│    python tzrec/export.py \                                    │
│        --pipeline_config_path=xxx.config \                     │
│        --checkpoint_path=... --export_dir=...                  │
│                                                                 │
│    → 从 checkpoint 恢复模型                                     │
│    → ScriptWrapper(model) 包裹（内嵌 DataParser）               │
│    → torch.fx.symbolic_trace() + torch.jit.script()            │
│    → 导出:                                                      │
│      ├── scripted_model.pt  （TorchScript 模型）               │
│      ├── pipeline.config     （线上配置）                       │
│      └── fg.json             （特征工程图）                     │
│                                                                 │
│   文件: tzrec/main.py:892                                       │
│         tzrec/utils/export_util.py:76                           │
└────────────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## 3. PEPNet_v2 前向详细流程

```python
class PEPNet_v2(MultiTaskRank):
    def predict(self, batch: Batch) -> Dict[str, torch.Tensor]:

        # ── (1) Embedding lookup ──────────────────────────────
        grouped_features = self.build_input(batch)
        # 对每个 feature_group 做 embedding lookup
        # 返回 {group_name: Tensor(batch, group_concat_dim)}

        # ── (2) 从 main group 拆出每个特征的 embedding ────────
        main_features = grouped_features[self._main_group_name]
        main_feature_tensors = torch.split(
            main_features, self._main_feature_dim_list, dim=1
        )

        # ── (3) Bias 提取 ─────────────────────────────────────
        # 每个特征的第 0 维作为 bias（第一个 embedding element）
        bias_vec, bias_sum = self._extract_bias(main_feature_tensors)

        # ── (4) CDOT 前向 ─────────────────────────────────────
        # 取每个特征前 input_dim 维作为 CDOT 输入
        cdot_input = self._extract_cdot(main_feature_tensors)
        allint_out, allint_mid_out = self.cdot(cdot_input)
        #   → CDOT.forward():
        #     (a) per-slot Dense → concat → compress MLP
        #     (b) sub_compress_weight 加权融合
        #     (c) split → allint_out, allint_mid_out

        # ── (5) 组件独立 LayerNorm → concat ──────────────────
        # 每一路先过自己的 LayerNorm，再拼接
        concat_parts.append(self.component_ln["main"](main_features))
        concat_parts.append(self.component_ln["allint_out"](allint_out))
        concat_parts.append(self.component_ln["bias"](bias_vec))
        concat_parts.append(self.component_ln["allint_mid"](allint_mid_out))
        deep_input = torch.cat(concat_parts, dim=1)

        # ── (6) EPNet（LHUC 缩放）─────────────────────────────
        # 根据 domain 特征（user_id+doc_id+req_page embedding）
        # 生成缩放因子，逐元素乘 deep_input
        lhuc_features = grouped_features[self._lhuc_group_name]
        ep_scale = self.epnet(lhuc_features)      # tanh, 范围 [-4, 6]
        deep_input = deep_input * ep_scale

        # ── (7) PPNet per-task tower ─────────────────────────
        for i, task_tower_cfg in enumerate(self._task_tower_cfgs):
            tower_name = task_tower_cfg.tower_name
            tower_output = self._task_towers[i](deep_input, lhuc_input)
            # → LHUC_PPNet.forward():
            #   (a) Dense → BN → Activation → Dropout
            #   (b) LHUC 缩放（逐层递增 tanh 幅度）
            #   (c) 最终 Dense 到 num_class（logits）

            # ── (8) 后处理 ─────────────────────────────────────
            if tower_name == "cvr" and ctr_logits is not None:
                tower_output = tower_output + ctr_logits  # logit 级融合
            else:
                tower_output = tower_output + bias_sum    # bias 补偿

            if tower_name == "ctr":
                ctr_logits = tower_output

            tower_outputs[tower_name] = tower_output

        # ── (9) 输出 ██████████████████████████████████
        return self._multi_task_output_to_prediction(tower_outputs)
        #   → 对每个任务 apply sigmoid（二分类）或 softmax（多分类）
```

______________________________________________________________________

## 4. 关键设计要点

| 组件                               | 输入                            | 输出                         | 作用                              |
| ---------------------------------- | ------------------------------- | ---------------------------- | --------------------------------- |
| `EmbeddingGroup`                   | Batch                           | `{group_name: Tensor}`       | 特征分组 + embedding lookup       |
| `CDOT`                             | `(batch, num_slots, input_dim)` | `allint_out, allint_mid_out` | 特征交叉压缩变换                  |
| `component_ln`                     | 各路 tensor                     | 各路归一化后 tensor          | 组件级 LayerNorm，消除量纲差异    |
| `LHUC_EPNet`                       | domain embedding                | `(batch, deep_dim)` 缩放因子 | 大范围调幅（[-4, 6]），全局个性化 |
| `LHUC_PPNet`                       | tower input + lhuc input        | `(batch, num_class)` logits  | 每层 LHUC 缩放，任务塔精细建模    |
| `_multi_task_output_to_prediction` | `{tower_name: logits}`          | `{tower_name: probs}`        | sigmoid / softmax 转换            |

______________________________________________________________________

## 5. 当前环境的限制

完整 E2E 训练需要 `fbgemm_gpu`：

| 环境      | 安装方式                       | 说明                             |
| --------- | ------------------------------ | -------------------------------- |
| CPU       | `pip install fbgemm-gpu-cpu`   | 可跑训练，无 GPU 加速            |
| GPU       | `pip install fbgemm-gpu-cu129` | 需要 CUDA 12.9                   |
| 当前 mock | `test_prelude.py` 替换 op      | **仅适用于单元测试**，不能跑 E2E |

______________________________________________________________________

## 6. 相关文件索引

| 步骤         | 文件                             | 关键行           |
| ------------ | -------------------------------- | ---------------- |
| 入口         | `tzrec/train_eval.py`            | 16-72            |
| 配置加载     | `tzrec/utils/config_util.py`     | 25-48            |
| 特征创建     | `tzrec/main.py`                  | 94-112           |
| Feature 定义 | `tzrec/features/feature.py`      | 1184-1196        |
| Dataset      | `tzrec/datasets/dataset.py`      | 87-375, 740-827  |
| DataParser   | `tzrec/datasets/data_parser.py`  | 184-277, 402-500 |
| 模型创建     | `tzrec/main.py`                  | 127-159          |
| BaseModel    | `tzrec/models/model.py`          | 37-38, 235-288   |
| PEPNet_v2    | `tzrec/models/pepnet_v2.py`      | 26-278           |
| 训练循环     | `tzrec/main.py`                  | 317-546          |
| Pipeline     | `tzrec/utils/dist_util.py`       | 335-376          |
| 优化器       | `tzrec/main.py`                  | 662-756          |
| 分布式       | `tzrec/utils/plan_util.py`       | 94-100           |
| Checkpoint   | `tzrec/utils/checkpoint_util.py` | 541-581          |
| 导出         | `tzrec/main.py`                  | 892-1009         |
| 导出工具     | `tzrec/utils/export_util.py`     | 76-114           |
