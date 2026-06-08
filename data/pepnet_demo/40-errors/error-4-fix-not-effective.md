______________________________________________________________________

## date: 2026-06-08 tags: [error, deployment, wheel, oss, dlc, smoke-test, critical, closed] status: closed

# 🚨 重大错误 4: 修复 ≠ 自动生效 (源码修复必须走 4 步)

> 触发: 2026-06-07 18:50 — DLC 脚本 `pip install --force-reinstall` 装的是 OSS **旧 wheel 1.2.15**, 源码修复完全没生效.

## 上下文

- \[[error-3-noise-undersample]\] 发现 eval pipeline 非确定性
- 完成 4 文件源码修复:
  - `tzrec/__init__.py:63-79` (默认 seed + cudnn.deterministic)
  - `tzrec/main.py:_evaluate()` (EVAL_SEED + empty_cache + synchronize)
  - `tzrec/datasets/dataset.py:create_dataloader()` (worker_init_fn)
  - `data/.../home_flow_2604_v6_ple_d.config:61-64` (eval num_steps: 123)
- 完成 wheel 1.2.16 重打 + 4 行 env vars 添加
- **🚨 错过的关键步骤**: 没检查 DLC 脚本实际装的 wheel 版本
- DLC `pip install --force-reinstall --extra-index-url http://mmb-spu:EaPXPBxx0dXX@oss.cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.15-py2.py3-none-any.whl` 装的是 **1.2.15**, 修复完全没生效

## 错误行为

- 推断"源码修完, 修后 5-run 噪声会 < 0.1pp"
- 实际 DLC 容器中装的是 1.2.15, 修复未生效, 仍会 0.73pp std
- 阻塞后续所有实验

## 🚨 根因

**4 步链路中 1 步断掉**:

```
源码修复 → 重打 wheel → 上传 OSS → 改 DLC URL → smoke test
                       ↑^^^^^^^^
                   这一步漏掉 (或 URL 没改对)
```

**我**:

- 修了源码 ✅
- 打了 wheel 1.2.16 ✅
- 改 `.sh` URL 到 1.2.16 ✅
- **没**上传 wheel 到 OSS ❌
- **没**smoke test 验证 ❌

DLC 脚本的 URL 改了, 但 OSS 上根本没有 1.2.16 wheel, pip install 会**静默失败**或装回 1.2.15.

## 为什么出错

1. **以为"URL 改了 wheel 就生效"** — 实际 OSS 没有
1. **没做部署端到端 smoke test**:
   - DLC 容器内 `pip show tzrec` 看版本
   - DLC 容器内 `python -c "import tzrec; print(tzrec.__version__)"` 看版本
1. **没把 wheel 上传到 OSS 写入 checklist**

## 正确做法 (4 步 + smoke test)

```
Step 1: 修源码 (4 文件)
Step 2: 改 version.py 1.2.15 → 1.2.16
Step 3: 重打 wheel → dist/tzrec-1.2.16-py2.py3-none-any.whl
Step 4: 上传 wheel 到 OSS bucket
        $ oss cp dist/tzrec-1.2.16-py2.py3-none-any.whl \
              oss://mmb-spu:cn-shenzhen/EasyRec/py_modules/
Step 5: 改 DLC 脚本 URL → 1.2.16
Step 6: DLC 容器 smoke test
        $ pip show tzrec | grep Version
        $ python -c "import tzrec; print(tzrec.__version__)"
        必须输出 1.2.16
Step 7: 修后 5-run 重跑 v6_ple_d, 验证 std < 0.1pp
```

**缺一不可**.

## 预防 (Deployment checklist 升级)

- [ ] **wheel 是否最新** (本地 wheel = git HEAD)
- [ ] **DLC 脚本 wheel URL 是否最新** (URL = OSS 实际版本)
- [ ] **wheel 是否上传到 OSS** (本地有, OSS 不一定有)
- [ ] **DLC 容器 smoke test 是否通过** (`pip show tzrec` 验证)
- [ ] **env vars 是否在 `set -e` 后第一行 export** (在 `pip install` 之前)

## 教训

1. **任何"修复"在生产生效前必须做端到端验证**:

   - 修源码 → smoke test 模拟环境运行
   - 修 wheel → DLC 容器 `pip show` 验证版本
   - 修配置 → DLC 容器 `cat` 验证

1. **部署 4 步链路不能跳**:

   - 源码 → wheel → OSS → URL
   - 任何一步漏掉, 修复"看似生效实际未生效"

1. **生产决策不能基于"看起来合理"**:

   - 修完源码 → 推断修后噪声会降 → 推断修复有效
   - 实际: 没 smoke test, 阻塞

## 关联

- \[[error-3-noise-undersample]\] — 触发源
- \[[../20-experiments/eval-pipeline-fix|eval-pipeline-fix]\] — 修复记录
- \[[index|错误总结]\]
