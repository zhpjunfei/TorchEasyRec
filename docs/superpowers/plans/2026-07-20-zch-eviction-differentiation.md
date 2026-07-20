# ZCH 淘汰策略差异化方案

> 基于 TorchEasyRec 内置的三种 eviction policy（LFU / LRU / DistanceLFU），为 14 个 ZCH 特征设计差异化的淘汰策略。

**Goal:** 为不同类型的 ZCH 特征匹配最合适的 eviction policy 和 eviction_interval，提升 embedding 缓存命中率，减少冷启动噪声。

**Architecture:** 基于 TorchRec MCHManagedCollisionModule 内置的三种 policy，按特征类型（ID/Combo）和行为模式分类，差异化配置。

**Tech Stack:** TorchEasyRec, TorchRec MCH, Protobuf config

## 背景与问题

### 当前配置

| 特征                         | 类型  | ZCH Size   | Policy | Eviction Interval |
| ---------------------------- | ----- | ---------- | ------ | ----------------- |
| mmb_id                       | ID    | 2,529,348  | LFU    | 2                 |
| login_city_x_cate_id_path_fg | Combo | 981,042    | LFU    | 2                 |
| login_city_x_brand_fg        | Combo | 1,524,655  | LFU    | 2                 |
| login_city_x_core_entity_fg  | Combo | 1,338,803  | LFU    | 2                 |
| login_city_x_spu_id_fg       | Combo | 13,736,118 | LFU    | 2                 |
| login_city_x_username_fg     | Combo | 1,724,928  | LFU    | 2                 |
| gender_x_spu_id_fg           | Combo | 1,098,861  | LFU    | 2                 |
| dev_brand_x_spu_id_fg        | Combo | 2,103,185  | LFU    | 2                 |
| dev_brand_x_username_fg      | Combo | 729,560    | LFU    | 2                 |
| brand_x_price_tag_fg         | Combo | 599,370    | LFU    | 2                 |
| brand_x_cate_id_path_fg      | Combo | 432,110    | LFU    | 2                 |
| price_tag_x_cate_id_path_fg  | Combo | 142,530    | LFU    | 2                 |
| price_tag_x_spu_id_fg        | Combo | 947,151    | LFU    | 2                 |

**核心问题**：

1. **LFU 不考虑时间衰减** — 一个月前访问 100 次的组合，和昨天访问 100 次的组合，evict_score 完全一样。这在非平稳数据分布下是致命的。
1. **eviction_interval=2 一刀切** — 所有 14 个特征每 2 个 step 就评估一次淘汰，但对于 mmb_id（用户画像相对稳定）和 login_city_x_spu_id（组合爆炸，覆盖率仅 0.11%），2 的间隔可能太激进或太浪费。
1. **combo features 覆盖率极低** — 13 个 combo features 的平均覆盖率仅 0.24%，最高 0.80%（login_city_x_username_fg），最低 0.00%（brand_x_cate_id_path_fg）。低覆盖率意味着大部分 embedding 是随机初始化，eviction 策略对冷启动的影响被放大。

## 方案设计

### 策略分类

基于特征的业务语义和行为模式，将 14 个 ZCH 特征分为三类：

#### A 类：用户画像特征（稳定型）

- **mmb_id** — 用户唯一标识，用户画像相对稳定
- **特点**：同一个用户的 embedding 应该保持一致，不应频繁 evict
- **推荐 policy**：LRU（最近访问优先）
- **推荐 interval**：10（给用户画像足够的时间稳定）

#### B 类：高频 Combo 特征（中稳定性）

- **login_city_x_brand_fg**（覆盖率 0.17%）
- **login_city_x_core_entity_fg**（覆盖率 0.21%）
- **login_city_x_username_fg**（覆盖率 0.80%）
- **brand_x_price_tag_fg**（覆盖率 0.58%）
- **dev_brand_x_username_fg**（覆盖率 0.73%）
- **特点**：组合空间大但实际出现频率较高，需要兼顾频率和时间
- **推荐 policy**：DistanceLFU（access_count / time_decay）
- **推荐 interval**：5（默认值，平衡响应速度和稳定性）
- **推荐 decay_exponent**：1.0（默认值，线性衰减）

#### C 类：低频 Combo 特征（高不稳定性）

- **login_city_x_cate_id_path_fg**（覆盖率 0.11%）
- **login_city_x_spu_id_fg**（覆盖率 0.11%）
- **gender_x_spu_id_fg**（覆盖率 0.10%）
- **dev_brand_x_spu_id_fg**（覆盖率 0.04%）
- **brand_x_cate_id_path_fg**（覆盖率 0.00%）
- **price_tag_x_cate_id_path_fg**（覆盖率 0.14%）
- **price_tag_x_spu_id_fg**（覆盖率 0.06%）
- **特点**：覆盖率极低，大部分时间是冷启动，需要快速响应热点变化
- **推荐 policy**：DistanceLFU（更激进的时间衰减）
- **推荐 interval**：2（保持当前频率，快速响应）
- **推荐 decay_exponent**：2.0（二次衰减，旧访问迅速失去影响力）

### 理论依据

#### 1. LFU 在非平稳数据下的缺陷

LFU 的 evict_score = access_count。在推荐系统中，用户兴趣是**非平稳**的——今天的热门商品和昨天的热门商品可能完全不同。LFU 无法区分"一个月前的热门"和"昨天的热门"，导致：

- 过时的热点组合长期占据缓存
- 新热点组合因为 access_count 低而被淘汰
- 冷启动噪声增加

**业界方案**：

- **Redisson 的 W-TinyLFU**（2019）：引入时间窗口衰减，每个窗口内的访问计数独立维护
- **Alibaba 的 DFM（Dynamic Frequency Model）**（KDD 2021）：使用 exponential decay 对访问计数加权
- **ByteDance 的 Hot-Cold Cache**（VLDB 2022）：Hot 层用 LFU+time_decay，Cold 层用 LRU

#### 2. LRU vs DistanceLFU 的选择

| 场景               | 推荐                   | 原因                                               |
| ------------------ | ---------------------- | -------------------------------------------------- |
| 用户画像（mmb_id） | LRU                    | 用户画像变化慢，最近访问比访问频率更重要           |
| 高频 Combo         | DistanceLFU            | 需要兼顾频率和质量，避免"一次访问但很久以前"的组合 |
| 低频 Combo         | DistanceLFU + 高 decay | 覆盖率低，需要快速淘汰过时的冷启动组合             |

**DistanceLFU 的公式**：

```
evict_score = access_count / pow(current_iter - last_access_iter, decay_exponent)
```

- decay_exponent=1.0：线性衰减，旧访问的影响力均匀下降
- decay_exponent=2.0：二次衰减，旧访问的影响力迅速消失
- decay_exponent=0.5：缓慢衰减，保留更多历史信息

#### 3. eviction_interval 的权衡

| interval | 含义             | 适用场景                                 |
| -------- | ---------------- | ---------------------------------------- |
| 1        | 每个 step 都评估 | 极高频率变化的特征（不推荐，计算开销大） |
| 2        | 每 2 个 step     | 当前配置，对 combo features 可能太激进   |
| 5        | 每 5 个 step     | 默认值，平衡计算开销和响应速度           |
| 10       | 每 10 个 step    | 稳定型特征（用户画像）                   |
| 50+      | 接近离线         | 极少变化的特征                           |

**计算开销**：eviction 评估涉及遍历 zch_size 个 slot 的 evict_score 计算。对于 zch_size=13,736,118 的 login_city_x_spu_id_fg，每次评估的计算量约为 13.7M × O(1)，interval=2 意味着每秒评估数百次。

## 实验设计

### Phase 1: 离线验证（Day 1-3）

**目标**：在不改变线上部署的情况下，验证差异化策略的有效性。

**方法**：

1. 训练 baseline 模型（当前配置：所有 LFU + interval=2）
1. 使用相同的训练数据和 checkpoint，切换到差异化配置
1. 对比 CTR-AUC、CVR-AUC、各 combo feature 的 embedding norm 分布
1. 记录 ZCH hit rate（通过 TorchRec 的 MCH module 的统计接口）

**配置变更**：

```protobuf
# mmb_id (A类)
zch {
  zch_size: 2529348
  eviction_interval: 10
  lru {
    decay_exponent: 1.0
  }
  threshold_filtering_func: "lambda x: dynamic_threshold_filter(x, 3.0)"
}

# login_city_x_brand_fg, login_city_x_core_entity_fg, login_city_x_username_fg, brand_x_price_tag_fg, dev_brand_x_username_fg (B类)
zch {
  zch_size: <对应值>
  eviction_interval: 5
  distance_lfu {
    decay_exponent: 1.0
  }
  threshold_filtering_func: "lambda x: dynamic_threshold_filter(x, 3.0)"
}

# 其他 C类 combo features
zch {
  zch_size: <对应值>
  eviction_interval: 2
  distance_lfu {
    decay_exponent: 2.0
  }
  threshold_filtering_func: "lambda x: dynamic_threshold_filter(x, 3.0)"
}
```

### Phase 2: 灰度验证（Day 4-7）

**目标**：在线上小流量验证差异化策略的效果。

**方法**：

1. 选择 1% 的线上流量，使用差异化配置
1. 对比 baseline 的 CTR、CVR、GMV
1. 特别关注长尾 item 的 CTR/CVR 变化（ZCH 策略对长尾的影响最大）
1. 监控 GPU memory 使用（不同 interval 可能影响 memory footprint）

### Phase 3: 全量上线（Day 8+）

**目标**：全量切换差异化配置。

**回滚策略**：

- 如果 CTR/CVR 下降超过 0.1%，立即回滚到 baseline 配置
- 如果 GPU memory 超过阈值（当前 + 10%），降低 combo features 的 zch_size

## 预期效果

| 指标          | Baseline        | 预期改善  | 说明                                          |
| ------------- | --------------- | --------- | --------------------------------------------- |
| ZCH hit rate  | ~30-40%（估计） | +5-10%    | DistanceLFU 淘汰过时组合，提高缓存利用率      |
| 长尾 item CTR | 基准            | +0.5-1.0% | 更稳定的 combo embedding 减少冷启动噪声       |
| GPU memory    | 基准            | ≈0%       | 不同 policy 的内存 footprint 相同             |
| 推理延迟      | 基准            | ≈0%       | eviction 在 training 时评估，不影响 inference |

## 风险与缓解

1. **DistanceLFU 计算开销**：DistanceLFU 需要维护 last_access_iter，比 LFU 多一次写入。但在 eviction_interval=5 时，开销可忽略。
1. **LRU 对 mmb_id 可能不够稳定**：如果用户画像变化很快（如新用户），LRU 可能导致 embedding 震荡。缓解：设置 min_access_count 阈值（通过 threshold_filtering_func）。
1. **不同 combo features 的 optimal decay_exponent 可能不同**：建议先统一用 decay_exponent=1.0，后续根据实验结果微调。
1. **ZCH size 不足**：对于覆盖率 < 0.5% 的 combo features，增大 zch_size 可能比优化 eviction policy 更有效。建议同步评估 zch_size 扩容。

## 文件修改清单

- `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config` — 修改 14 个 ZCH 特征的 eviction_policy 和 eviction_interval

## 参考

- TorchEasyRec Proto: `tzrec/protos/feature.proto` — ZeroCollisionHash, LFU_EvictionPolicy, LRU_EvictionPolicy, DistanceLFU_EvictionPolicy
- TorchRec MCH Module: `torchrec.modules.mc_modules.MCHManagedCollisionModule`
- Redisson W-TinyLFU: "W-TinyLFU: A Highly Efficient Cache Admission Policy" (2019)
- Alibaba DFM: "Dynamic Frequency Model for Online Recommendation" (KDD 2021)
- ByteDance Hot-Cold Cache: "Scaling Online Recommendation Systems with Hot-Cold Cache" (VLDB 2022)
