#!/usr/bin/env bash
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
# Train + Platt Calibration + Export 完整 pipeline
# =============================================================================
#
# 对比你现有的 train_export.py（两步）：
#   1. torchrun -m tzrec.train_eval ...  → model_dir/
#   2. torchrun -m tzrec.export ...       → export_dir/
#
# 新增第三步（Platt 校准），形成三步流程：
#   1. torchrun -m tzrec.train_eval ...  → model_dir/
#   2. python tools/platt_calibrate.py ... → platt_fitted/  (嵌入 fitted a,b)
#   3. torchrun -m tzrec.export ...       → export_dir/    (自动加载 platt)
#
# =============================================================================

set -e

# --- 配置 ---
TRAIN_CONFIG="data/pepnet_demo/config/v16/home_flow_2604_v16_platt_calibration.config"
MODEL_DIR="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_platt/${train_ymd}"
EXPORT_DIR="${MODEL_DIR}/export/final_with_fg"
VAL_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3/dt=${val_ymd}"
BATCH_SIZE=4096
N_PROCS=8

# =============================================================================
# Step 1: 训练 (与现有完全相同)
# =============================================================================
dlc submit pytorchjob \
    --name=home_flow_2604_sorter_train \
    --command='set -e
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.19-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps --force-reinstall

        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
            --nnodes=$WORLD_SIZE --nproc-per-node=$NPROCS_PER_NODE --node_rank=$RANK \
            -m tzrec.train_eval \
            --pipeline_config_path ${TRAIN_CONFIG} \
            --train_input_path odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3/dt=${train_ymd} \
            --model_dir ${MODEL_DIR}' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=1 \
    --job_max_running_time_minutes=43200 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn6e-c12g1.12xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true


# =============================================================================
# Step 2: 拟合 Platt 参数（单卡 GPU 即可，不需要多卡）
# =============================================================================
dlc submit pytorchjob \
    --name=home_flow_2604_platt_calibration \
    --command='set -e
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.19-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps --force-reinstall

        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        python tools/platt_calibrate.py \
            --config ${TRAIN_CONFIG} \
            --checkpoint_dir ${MODEL_DIR} \
            --val_data_path ${VAL_DATA_PATH} \
            --batch_size ${BATCH_SIZE} \
            --device cuda:0 \
            --output_dir ${MODEL_DIR}/platt_fitted' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=1 \
    --job_max_running_time_minutes=120 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn6e-c12g1.12xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true


# =============================================================================
# Step 3: 导出（带 Platt 参数）
# =============================================================================
dlc submit pytorchjob \
    --name=home_flow_2604_sorter_export_platt \
    --command='set -e
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.19-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps --force-reinstall

        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
            --nnodes=1 --nproc-per-node=1 --node_rank=0 \
            -m tzrec.export \
            --pipeline_config_path ${MODEL_DIR}/pipeline.config \
            --checkpoint_path ${MODEL_DIR}/platt_fitted \
            --export_dir ${EXPORT_DIR}' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=1 \
    --job_max_running_time_minutes=720 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn6e-c12g1.12xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true
