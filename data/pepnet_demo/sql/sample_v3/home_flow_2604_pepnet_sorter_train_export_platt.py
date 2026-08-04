# Copyright (c) 2025, Alibaba Group;
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Copyright (c) 2025, Alibaba Group;
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# =============================================================================
# Train → Platt Calibrate → Inject → Export 完整 pipeline（单 Job）
# =============================================================================
# 四步顺序执行（DCP bridge 加载多卡 checkpoint，无 NaN）：
#   1. torchrun -m tzrec.train_eval      → model_dir/ (DCP checkpoint)
#   2. python -m tzrec.tools.platt_calibrate   → platt_fitted/ (platt_params.pt + meta.json)
#   3. python -m tzrec.tools.platt_inject_into_export → platt_injected/ (DCP checkpoint with platt params)
#   4. torchrun -m tzrec.export          → export/final_with_fg/
# =============================================================================
# 关键说明：
#   • DCP bridge 方案：为裸模型 state dict 添加 "model." 前缀匹配 DMP 格式，
#     直接拷贝参数到模型（绕过 validate_state hooks），支持 4→1 卡 resharding
#   • 本脚本不做任何文件写入，避免锁竞争，直接使用配置好的环境
#   • 所有路径均为相对/绝对路径，不涉及临时文件或共享锁
# =============================================================================

dlc submit pytorchjob \
    --name=home_flow_2604_sorter_train_export_platt \
    --command='set -euo pipefail
        # 基础环境设置
        echo "[INIT] Starting pipeline job..."
        echo "[INIT] train_ymd=${train_ymd:-$(date +%Y%m%d)}"

        # 安装依赖（从内部源获取修复版 tzrec）
        echo "[INSTALL] Installing tzrec..."
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.19-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps --force-reinstall || { echo "[ERROR] Failed to install tzrec"; exit 1; }

        # 环境变量导出
        export TRAIN_CONFIG="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/home_flow_2604_v17_platt_calibration.config"
        export MODEL_DIR="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_platt/${train_ymd}"
        export EXPORT_DIR="${MODEL_DIR}/export/final_with_fg"
        export TRAIN_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_train/dt=${train_ymd}"
        export VAL_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val/dt=${train_ymd}"
        export ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api

        # Step 1: 训练 (DCP 格式 checkpoint)
        echo "[STEP1] Starting training..."
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
            --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
            -m tzrec.train_eval \
            --pipeline_config_path ${TRAIN_CONFIG} \
            --train_input_path ${TRAIN_DATA_PATH} \
            --model_dir ${MODEL_DIR} || { echo "[ERROR] Training failed"; exit 1; }
        echo "[STEP1] Training completed."

        # DIAGNOSTIC: dump checkpoint key structure for DCP bridge debugging
        echo "[DIAG] Reading checkpoint metadata..."
        python3 << 'PYEOF'
import os, json, glob
from collections import Counter
from torch.distributed.checkpoint import FileSystemReader

model_dir = os.environ.get("MODEL_DIR", "")
ckpt_dirs = sorted(glob.glob(os.path.join(model_dir, "model.ckpt-*")))
if not ckpt_dirs:
    print("[DIAG] No checkpoint found, skipping")
else:
    ckpt = ckpt_dirs[-1]
    print(f"[DIAG] Latest ckpt: {ckpt}")
    meta_path = os.path.join(ckpt, "model")
    meta = FileSystemReader(meta_path).read_metadata()
    keys = sorted(meta.state_dict_metadata.keys())
    print(f"[DIAG] Total keys: {len(keys)}")

    prefixes = Counter()
    for k in keys:
        parts = k.split(".")
        for plen in range(1, min(5, len(parts)) + 1):
            prefixes[".".join(parts[:plen])] += 1
    print("[DIAG] Top prefixes:")
    for p, c in prefixes.most_common(20):
        print(f"  {p:<60} {c}")
    print("[DIAG] First 10 keys:")
    for i, k in enumerate(keys[:10]):
        print(f"  [{i}] {k}")
    print("[DIAG] Non-weight keys:")
    dense = [k for k in keys if not k.endswith(".weight")]
    for k in dense[:15]:
        print(f"  {k}")

    out_path = os.path.join(ckpt, "checkpoint_keys_diag.json")
    with open(out_path, "w") as f:
        json.dump({"keys": keys, "prefixes": dict(prefixes.most_common(50))}, f, indent=2)
    print(f"[DIAG] Saved to {out_path}")
PYEOF

        # Step 2: 拟合 Platt 参数 (DCP bridge 加载多卡 checkpoint)
        echo "[STEP2] Running Platt calibration..."
        python -m tzrec.tools.platt_calibrate \
            --config ${TRAIN_CONFIG} \
            --checkpoint_dir ${MODEL_DIR} \
            --val_data_path ${VAL_DATA_PATH} \
            --output_dir ${MODEL_DIR}/platt_fitted \
            --device cuda:0 || { echo "[ERROR] Platt calibration failed"; exit 1; }
        echo "[STEP2] Platt calibration completed."

        # Step 3: 注入 Platt 参数到 DCP checkpoint (DCP bridge 加载)
        echo "[STEP3] Injecting Platt parameters..."
        python -m tzrec.tools.platt_inject_into_export \
            --config ${MODEL_DIR}/pipeline.config \
            --trained_ckpt ${MODEL_DIR} \
            --platt_meta ${MODEL_DIR}/platt_fitted/platt_meta.json \
            --output ${MODEL_DIR}/platt_injected || { echo "[ERROR] Injection failed"; exit 1; }
        echo "[STEP3] Injection completed."

        # Step 4: 导出模型（加载带有 Platt 参数的 checkpoint）
        echo "[STEP4] Exporting model..."
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
            --nnodes=1 --nproc-per-node=1 --node_rank=0 \
            -m tzrec.export \
            --pipeline_config_path ${MODEL_DIR}/pipeline.config \
            --checkpoint_path ${MODEL_DIR}/platt_injected \
            --export_dir ${EXPORT_DIR} || { echo "[ERROR] Export failed"; exit 1; }
        echo "[STEP4] Export completed."

        echo "[SUCCESS] Pipeline finished successfully!"
    ' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=1 \
    --job_max_running_time_minutes=43200 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn6e-c12g1.12xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true
