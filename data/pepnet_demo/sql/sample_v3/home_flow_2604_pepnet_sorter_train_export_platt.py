#!/usr/bin/env bash
# =============================================================================
# Train + Platt Calibration + Export 完整 pipeline
# =============================================================================
# 
# 三步流程：
#   1. torchrun -m tzrec.train_eval ...  → model_dir/
#   2. python tools/platt_calibrate.py ... → platt_fitted/
#   3. torchrun -m tzrec.export ...       → export_dir/
#
# 注意：Step 1 和 Step 3 合并到一个 dlc submit 中（中间用 \; 分隔）
# Step 2 单独提交（只需要单卡 GPU，资源需求不同）
# =============================================================================

set -e

# --- 配置 ---
TRAIN_CONFIG="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/home_flow_2604_v16_platt_calibration.config"
MODEL_DIR="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_platt/${train_ymd}"
EXPORT_DIR="${MODEL_DIR}/export/final_with_fg"
TRAIN_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3/dt=${train_ymd}"
VAL_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val/dt=${train_ymd}"
BATCH_SIZE=4096

# =============================================================================
# Step 1+3: 训练 + 导出（合并到一个 Job，共享环境变量）
# =============================================================================
dlc submit pytorchjob \
    --name=home_flow_2604_sorter_train_export_platt \
    --command='set -e
        export TRAIN_CONFIG="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/home_flow_2604_v16_platt_calibration.config"
        export MODEL_DIR="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_platt/${train_ymd}"
        export TRAIN_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3/dt=${train_ymd}"
        export EXPORT_DIR="${MODEL_DIR}/export/final_with_fg"
        
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.19-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps --force-reinstall
        
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
            --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
            -m tzrec.train_eval \
            --pipeline_config_path ${TRAIN_CONFIG} \
            --train_input_path ${TRAIN_DATA_PATH} \
            --model_dir ${MODEL_DIR}
        
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
    --job_max_running_time_minutes=43200 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn6e-c12g1.12xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true


# =============================================================================
# Step 2: 拟合 Platt 参数（独立 Job，单卡 GPU 即可）
# =============================================================================
dlc submit pytorchjob \
    --name=home_flow_2604_platt_calibration \
    --command='set -e
        export TRAIN_CONFIG="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/home_flow_2604_v16_platt_calibration.config"
        export MODEL_DIR="/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_platt/${train_ymd}"
        export VAL_DATA_PATH="odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val/dt=${train_ymd}"
        export BATCH_SIZE=4096
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
