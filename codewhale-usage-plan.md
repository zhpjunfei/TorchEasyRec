# CodeWhale 使用方案 — TorchEasyRec 折扣推荐算法

## 项目概况

- **框架：** TorchEasyRec（阿里开源，PyTorch 推荐模型框架）
- **核心架构：** PEPNet + DCNv2 + PLE，用于多任务精排
- **场景：** 折扣帖子下拉流推荐（召回→粗排→精排）
- **代码规模：** ~23,000 行 Python（tzrec/ 目录下）
- **实验体系：** 已有 v15 系列实验（序列处理方式探索）
- **数据源：** ODPS（阿里大数据平台）

______________________________________________________________________

## 一、核心使用场景

### 场景 1：代码理解与架构分析

**目的：** 快速理解陌生模块、理清调用链路

```bash
# 分析 PEPNetDCNPLE 模型的前向传播流程
codewhale --provider openai --model agnes-2.0-flash \
  exec "阅读 /Users/zhangjunfei/mmb/TorchEasyRec/tzrec/models/pepnet_dcn_ple.py 的 forward 方法，
  画出数据从输入到输出的完整流动路径，标注每个模块的输入输出维度"

# 梳理 CDOT 模块的作用
codewhale --provider openai --model agnes-2.0-flash \
  exec "分析 tzrec/modules/cdot.py 的核心逻辑，
  解释 CDOT gating 机制如何工作，以及它与 DCNv2 的交互关系"

# 理解特征工程管线
codewhale --provider openai --model agnes-2.0-flash \
  exec "梳理 tzrec/features/ 下所有 feature 类型的继承关系，
  说明 ID 特征、KV 特征、组合特征在训练时的处理流程差异"
```

### 场景 2：实验配置生成与变体创建

**目的：** 基于现有 config 快速生成实验变体

```bash
# 基于 v15 基线生成新实验配置
codewhale --provider openai --model agnes-2.0-flash \
  exec "基于 /Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/config/v15/
  的 home_flow_2604_v15_calibration_d_fusion.config，
  创建一个新变体 v16：将 PLE extraction_networks 的 layer2 expert_num 从 8 改为 16，
  同时在 CVR tower 中增加一个 dropout 0.1，
  输出完整的 protobuf config 文本"

# 批量生成实验矩阵
codewhale --provider openai --model agnes-2.0-flash \
  exec "读取 v15-experiments.md 中的变体设计思路，
  生成 5 个新的实验变体方案（v16a-v16e），
  每个方案只改动 1-2 个超参数，
  输出为 Markdown 表格格式"
```

### 场景 3：实验结果分析与报告生成

**目的：** 自动解读实验数据，生成结构化报告

```bash
# 分析实验日志
codewhale --provider openai --model agnes-2.0-flash \
  exec "分析 /Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/20-experiments/
  下的实验记录，对比各变体的 AUC/CVR lift 变化，
  找出最有效的修改方向，给出下一步实验建议"

# 生成实验总结
codewhale --provider openai --model agnes-2.0-flash \
  exec "读取 v15-experiments.md 的全部内容，
  生成一份面向团队的技术总结，
  包含：实验目标、关键发现、证否/证实的方案、
  遗留问题和下一步计划"
```

### 场景 4：代码修改与 Bug 修复

**目的：** 让 AI 直接修改代码并验证

```bash
# 修改模型架构
codewhale --provider openai --model agnes-2.0-flash \
  exec "在 tzrec/models/pepnet_dcn_ple.py 中，
  为 PEPNetDCNPLE 类添加一个新的可选参数 enable_cvr_shortcut，
  当为 True 时，CVR tower 的输出 logits 会与 CTR tower 的输出做残差连接，
  修改后确保 forward 方法正确处理这个分支"

# 添加新模块
codewhale --provider openai --model agnes-2.0-flash \
  exec "参考 tzrec/modules/cdot.py 的实现风格，
  在 tzrec/modules/ 下创建一个新模块 selective_attention.py，
  实现一个轻量级的序列注意力机制，
  支持 target_item 对 user_sequence 的注意力加权，
  输出维度与输入一致"
```

### 场景 5：测试用例编写

**目的：** 补全缺失的单元测试

```bash
# 为新模块写测试
codewhale --provider openai --model agnes-2.0-flash \
  exec "阅读 tzrec/models/pepnet_dcn_ple.py 的 PEPNetDCNPLE 类，
  参考同目录下 pepnet_dcn_ple_test.py 的现有测试风格，
  补充以下测试用例：
  1. 测试不同 batch_size 下的 forward 兼容性
  2. 测试启用/禁用 cvr_shortcut 的输出一致性
  3. 测试 embedding dim 不一致时的错误处理"
```

### 场景 6：多模型并行实验（Fleet 模式）

**目的：** 同时对比多个方案

```bash
# 启动 Fleet 并行实验
codewhale --provider openai --model agnes-2.0-flash \
  fleet exec "并行分析以下 3 个方向的改进潜力：
  Lane 1: 分析 PEPNet gate 机制，找出可能的瓶颈
  Lane 2: 分析 DCNv2 交叉层数与效果的边际效应
  Lane 3: 分析 PLE CGC 路由的 expert 分配均匀性"
```

______________________________________________________________________

## 二、针对你工作流的专项方案

### 召回阶段

```bash
# 分析召回模块代码
codewhale --provider openai --model agnes-2.0-flash \
  exec "分析 /Users/zhangjunfei/mmb/TorchEasyRec/tzrec/models/ 下
  所有 match_model*.py 文件，梳理可用的召回模型有哪些，
  各自的适用场景是什么"

# 设计新的召回策略
codewhale --provider openai --model agnes-2.0-flash \
  exec "基于 TorchEasyRec 的匹配模型架构，
  设计一个针对折扣帖子的双塔召回模型方案，
  包含：用户塔特征（历史点击折扣品、折扣敏感度）、
  物品塔特征（折扣力度、类目、价格带），
  输出模型结构和特征定义"
```

### 粗排阶段

```bash
# 粗排模型轻量化
codewhale --provider openai --model agnes-2.0-flash \
  exec "分析 PEPNetDCNPLE 模型的参数量和计算量，
  设计一个粗排版本：保留核心交互结构但减少 MLP 层数，
  目标是参数量压缩到原模型的 1/3 以内，
  输出新旧模型对比表"
```

### 精排阶段

```bash
# 多任务优化
codewhale --provider openai --model agnes-2.0-flash \
  exec "当前精排使用 PLE 做多任务学习（CTR/CVR/ occupation），
  分析现有的任务塔结构，提出 3 个改进方向：
  1. 任务权重动态调整
  2. 引入校准模块（calibration）
  3. 任务间知识蒸馏
  每个方向给出具体实现方案和预期收益"

# 特征交叉优化
codewhale --provider openai --model agnes-2.0-flash \
  exec "分析当前 config 中定义的 feature_configs，
  识别哪些特征组合可能产生有价值的交叉特征，
  推荐 5 个值得尝试的 combo_feature 定义"
```

______________________________________________________________________

## 三、高效使用技巧

### 1. 利用 AGENTS.md 上下文

项目根目录已有 AGENTS.md（工作规则），CodeWhale 会自动加载：

```bash
# 在 TorchEasyRec 目录下执行，AI 会自动遵循 AGENTS.md 的规则
cd /Users/zhangjunfei/mmb/TorchEasyRec
codewhale --provider openai --model agnes-2.0-flash \
  exec "按照 AGENTS.md 中的工作规则，
  分析 calibration.py 中 compute_soft_ece 函数的数值稳定性"
```

### 2. 指定工作空间

```bash
# 限定 AI 只能操作指定目录
codewhale --provider openai --model agnes-2.0-flash \
  -C /Users/zhangjunfei/mmb/TorchEasyRec \
  exec "修改 tzrec/modules/calibration.py 中的温度缩放实现"
```

### 3. 渐进式任务分解

不要一次给太长的指令，分步进行：

```bash
# Step 1: 先理解
codewhale --provider openai --model agnes-2.0-flash \
  exec "阅读 tzrec/modules/cdot.py，总结 CDOT 模块的功能和接口"

# Step 2: 再分析
codewhale --provider openai --model agnes-2.0-flash \
  exec "基于刚才理解的 CDOT 模块，分析它在 PEPNetDCNPLE 中的使用位置"

# Step 3: 最后修改
codewhale --provider openai --model agnes-2.0-flash \
  exec "基于上面的分析，修改 CDOT 的 gating 逻辑，
  增加一个可学习的 temperature 参数"
```

### 4. 利用 --prompt 参数快速单轮

```bash
# 快速问答，不需要进入交互模式
codewhale --provider openai --model agnes-2.0-flash \
  --prompt "TorchEasyRec 中 PLE 和 MMoE 的核心区别是什么？
  用 3 句话概括"
```

______________________________________________________________________

## 四、推荐的日常 Workflow

```
早上到公司
  ↓
codewhale exec "检查昨晚实验的日志，汇总各变体的 AUC/CVR 变化"
  ↓
codewhale exec "基于实验结果，推荐今天优先验证的 2 个方向"
  ↓
[手动跑实验]
  ↓
下午
  ↓
codewhale exec "分析 v16 实验的 train_loss 曲线，判断是否过拟合"
  ↓
codewhale exec "生成今天的实验日报，包含：已完成、进行中、阻塞项"
  ↓
晚上
  ↓
codewhale exec "整理本周所有实验结论，更新 v15-experiments.md"
```

______________________________________________________________________

## 五、注意事项

1. **API Key 管理：** 每次执行需确保 `AGNES_API_KEY` 环境变量已设置
1. **Token 消耗：** 大文件分析（如完整 forward 方法）会消耗较多 token，
   建议分模块逐步分析
1. **代码修改安全：** 涉及核心模型代码的修改，建议先用 `--provider openai`
   让 AI 给出 diff，人工审核后再 apply
1. **实验数据隔离：** 所有实验相关分析建议限定在 `data/pepnet_demo/` 目录下
1. **ODPS 数据不可直接访问：** CodeWhale 只能分析本地代码和文件，
   无法直接查询 ODPS 数据，需要导出本地样本或统计结果
