______________________________________________________________________

## date: 2026-06-26 tags: [architecture, index] status: active related: ["[[pepnet-dcn-ple]]", "[[pepnet-v2]]", "[[model-components]]", "[[data-schema]]"]

# 10-architecture — 模型架构

> 本项目使用的模型架构与组件文档。

## 笔记列表

| 文件 | 说明 | 状态 |
| :--- | :--- | :---: |
| [[pepnet-dcn-ple]] | PEPNetDCNPLE — 本项目主模型 ⭐ | production-candidate |
| [[pepnet-v2]] | PEPNet_v2 基础架构 | active |
| [[model-components]] | LHUC / CDOT / CrossV2 / ExtractionNet 模块详解 | active |
| [[data-schema]] | 特征 schema (40+ features) | active |
| [[dice-bn-online-risk]] | Dice + BatchNorm 线上推理风险评估 | active |

## 架构关系

```
PEPNet_v2 (base)
    └── PEPNetDCNPLE (production candidate)
            ├── model-components (LHUC, CDOT, CrossV2, ExtractionNet)
            └── dice-bn-online-risk (推理风险评估)
```

## 外部引用

- 实现代码: `tzrec/models/pepnet_dcn_ple.py`
- 模块实现: `tzrec/modules/`
