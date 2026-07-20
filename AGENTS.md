# AGENTS.md — Agnes-2.0-Flash 工作规则

## 核心原则

### 1. 先思考，后编码

- 明确陈述假设。如果不确定，宁可提问也不要猜测。
- 存在歧义时，给出多种解释。
- 如果有更简单的方案，应提出反对。
- 感到困惑时停下来。指出不清楚的地方。

### 2. 简单至上

- 用最少代码解决问题。不做投机性内容。
- 不超出需求范围。不为一次性代码做抽象。
- 检验标准：资深工程师会说这过度复杂吗？如果是，就简化。

### 3. 精准修改

- 只动必须改的地方。只清理自己的遗留问题。
- 不要"改进"相邻的代码、注释或格式。
- 不要重构未损坏的部分。匹配现有风格。

### 4. 目标驱动执行

- 定义成功标准。循环直到验证通过。
- 不要照搬步骤。定义成功并迭代。
- 强有力的成功标准让你能独立循环。

### 5. 模型仅用于判断性工作

- 用我（模型）做：分类、起草、总结、信息提取。
- 不要用我做：路由、重试、确定性转换。
- 如果代码能回答，就让代码回答。

### 6. Token 预算不是建议

- 每任务：4,000 token。每会话：30,000 token。
- 接近预算时，总结并重新开始。
- 暴露超出预算的情况。不要静默超限。

### 7. 显式冲突，不要平均处理

- 如果两种模式矛盾，选择其中一种（更新/经过更多测试的）。
- 解释原因。标记另一种待清理。
- 不要混合冲突的模式。

### 8. 先读后写

- 添加代码前，阅读导出项、直接调用方、共享工具。
- "看起来正交"是危险的。如果不确定代码为何如此组织，请提问。

### 9. 测试验证意图，而不仅是行为

- 测试必须编码"为什么"行为重要，而不仅是"做什么"。
- 当业务逻辑变更时，一个不会失败的测试就是错误的。

### 10. 每个重要步骤后设置检查点

- 总结已完成、已验证、剩余的内容。
- 不要从一个无法回溯的状态继续。
- 如果失去头绪，停下来重新陈述。

### 11. 遵循代码库的约定，即使你不认同

- 在代码库内，遵循规范 > 个人品味。
- 如果你真的认为某个约定有害，提出来。不要静默分叉。

### 12. 响亮地失败

- 如果任何内容被静默跳过，"已完成"就是错误的。
- 如果有任何测试被跳过，"测试通过"就是错误的。
- 默认暴露不确定性，而非隐藏它。

______________________________________________________________________

## 实验决策记录

### DECISION: 不需要多 Epoch 验证校准实验趋势稳定

- 基线单 Epoch 后已开始过拟合，多 Epoch 无意义

### BUG FIX: set_current_step 在 epoch-based 训练下从未被调用 (2026-07-17)

**根因：** `set_current_step()` 调用被 `use_step` 条件守卫，但所有实验配置使用 `num_epochs: 1` 而非 `num_steps`，导致 `use_step = False`。

**修复：** 去掉 `use_step` 条件，仅保留 `hasattr` 向后兼容检查。

**影响：** 修复前方案 B/D 的 calibration_loss 始终为 0（\_current_step 始终为 0，schedule 返回 0.0 权重）。修复后 progressive schedule 真正生效。

**注意：** `anneal_temperature` 同样受 `use_step` 守卫，但 AFP 温度调度是已有功能，暂不改动。

### BUG FIX: FX tracing 期间 Proxy 变量不可用于控制流 (2026-07-18)

**现象：** `torch.fx.proxy.TraceError: symbolically traced variables cannot be used as inputs to control flow`

**根因：** PipelineParallel 训练和 model export 阶段会调用 FX symbolic trace 对 `forward()` 进行图追踪。追踪期间，所有 tensor 运算结果变成 `Proxy` 对象，**不能用于 `if/while/for` 控制流判断**（如 `if total_entropy > 0:`、`if ent is not None:` 等）。

**常见触发场景：**

1. 在 `loss()` 方法中累加 tensor 值后做 `if > 0:` 判断
1. 在 `loss()` 方法中使用 `getattr` 获取 tensor 属性后判断 `is not None`
1. 在 `forward()` 方法中访问 `scaler.get_temperature().item()`（已有 `isinstance(Proxy)` guard 的除外）

**修复原则：**

- **外层 guard 优先：** 将 `is_fx_tracing()` 检查放在**整个涉及 tensor 比较/累加的代码块外层**，而不是内部某一行。内层 guard 太晚——Proxy 已经在前面被创建/累加了。
- **已有模式参考：** calibration loss 和 contrastive loss 中使用 `isinstance(x, torch.fx.Proxy)` 检查后 `break`，这是正确的做法。
- **import：** `from torch.fx._symbolic_trace import is_fx_tracing`

**反面示例（错误）：**

```python
# ❌ 内层 guard 太晚——total_entropy 已经是 Proxy
total_entropy += ent  # ← Proxy 在这里产生
if not is_fx_tracing():  # ← 太晚了！
    if total_entropy > 0:  # ← TraceError!
```

**正面示例（正确）：**

```python
# ✅ 外层 guard 完全跳过 Proxy 区域
if not is_fx_tracing():
    total_entropy = 0.0
    for afp_mod in afp_list:
        ent = getattr(afp_mod, "_partition_entropy", None)
        total_entropy += ent
    if total_entropy > 0:  # ← 正常 float 比较，安全
```

**经验教训：**

- 每次在 `loss()` 或 `forward()` 中引入涉及 tensor 运算+控制流的代码时，第一时间考虑 FX tracing 兼容性
- 不要只 guard `torch.tensor()` 那一行——整个计算链都需要被保护
- `is_fx_tracing()` 检查应该包裹**整个**可能产生 Proxy 的代码块

## PCGrad 梯度手术实现规范

### 核心原则
- 所有梯度手术类（PCGrad、Pareto、UncertaintyWeight 等）必须通过 **loss key 名称** 识别任务角色，而非依赖 dict 遍历顺序。
- 默认参数必须是显式传参，禁止依赖隐式默认值。
- `.reshape(-1)` 而非 `.view(-1)`：DDP/TorchRec 分布式环境下梯度 tensor 可能不连续。
- 混合精度安全：`_flatten_grads` 中 `torch.zeros` 的 dtype 必须与 `params[0].dtype` 一致。

### 典型反模式
```python
# ❌ 依赖 dict 顺序推断任务优先级
for i, (name, loss_val) in enumerate(losses.items()):
    # name 可能是 "binary_cross_entropy_ctr" 或任意 key
    # 顺序变了，CVR 优先就失效了

# ❌ view(-1) 在 DDP 下崩溃
grads.append(g.view(-1))

# ✅ 通过 key 识别任务
ctr_keys = [k for k in losses if "ctr" in k]
cvr_keys = [k for k in losses if "cvr" in k or "ctcvr" in k]
```

## PCGrad OOM 修复经验 (2026-07-20)

### 问题
`retain_graph=True` 在 30GB+ 模型上 OOM。前向激活图本身占 30GB，
`retain_graph` 阻止中间激活被释放，第二次 `autograd.grad` 时没有内存。

### 解决方案
- 主路径：通过 `predict_fn` + `loss_fn` 参数，每任务重算 forward，
  backward 后立即释放激活图，peak memory = O(forward_graph)。
  开销：N 次 forward ≈ 20% 额外时间，换来 OOM 消除。
- 回退路径：detach 其他任务 loss 后调用 `autograd.grad`，
  仅在 `predict_fn` 不可用时使用（小模型）。

### 关键约束
- `backward()` 不接受 `allow_unused` 参数，只有 `autograd.grad()` 接受。
- DDP 下 `.reshape(-1)` 而非 `.view(-1)`（tensor 可能不连续）。
- backward hook 中 `_patch_gradients` 必须直接赋值 `p.grad`，
  不能检查 `p.grad is None` 后 continue（首次调用时全是 None）。
