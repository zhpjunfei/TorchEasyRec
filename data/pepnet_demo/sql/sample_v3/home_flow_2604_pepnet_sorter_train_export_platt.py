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

# =============================================================================
# Train → Platt Calibrate → Inject → Export 完整 pipeline（单 Job）
# =============================================================================
# 四步顺序执行：
#   1. torchrun -m tzrec.train_eval      → model_dir/ (DCP checkpoint)
#   2. python -m tzrec.tools.platt_calibrate   → platt_fitted/ (platt_params.pt + meta.json)
#   3. python -m tzrec.tools.platt_inject_into_export → platt_injected/ (DCP checkpoint with platt params)
#   4. torchrun -m tzrec.export          → export/final_with_fg/
# =============================================================================

dlc submit pytorchjob \
    --name=home_flow_2604_sorter_train_export_platt \
    --command='set -e
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.19-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps --force-reinstall

        export TRAIN_CONFIG="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/home_flow_2604_v16_platt_calibration.config"
        export MODEL_DIR="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_platt/${train_ymd}"
        export EXPORT_DIR="${MODEL_DIR}/export/final_with_fg"
        export TRAIN_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_train/dt=${train_ymd}"
        export VAL_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val/dt=${train_ymd}"

        # Step 1: 训练
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
            --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
            -m tzrec.train_eval \
            --pipeline_config_path ${TRAIN_CONFIG} \
            --train_input_path ${TRAIN_DATA_PATH} \
            --model_dir ${MODEL_DIR}

        # Step 2: 拟合 Platt 参数 (用多GPU运行，保持DCP checkpoint兼容)
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$((MASTER_PORT + 1)) \
            --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
            -m tzrec.tools.platt_calibrate \
            --config ${TRAIN_CONFIG} \
            --checkpoint_dir ${MODEL_DIR} \
            --val_data_path ${VAL_DATA_PATH} \
            --output_dir ${MODEL_DIR}/platt_fitted

        # Step 3: 注入 Platt 参数到 DCP checkpoint (多GPU保持兼容性)
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$((MASTER_PORT + 2)) \
            --nnodes=1 --nproc-per-node=$NPROC_PER_NODE --node_rank=0 \
            -m tzrec.tools.platt_inject_into_export \
            --config ${MODEL_DIR}/pipeline.config \
            --trained_ckpt ${MODEL_DIR} \
            --platt_meta ${MODEL_DIR}/platt_fitted/platt_meta.json \
            --output ${MODEL_DIR}/platt_injected

        # Step 4: 导出模型（加载带有 Platt 参数的 checkpoint）
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
            --nnodes=1 --nproc-per-node=1 --node_rank=0 \
            -m tzrec.export \
            --pipeline_config_path ${MODEL_DIR}/pipeline.config \
            --checkpoint_path ${MODEL_DIR}/platt_injected \
            --export_dir ${EXPORT_DIR}' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=1 \
    --job_max_running_time_minutes=43200 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn6e-c12g1.12xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true
