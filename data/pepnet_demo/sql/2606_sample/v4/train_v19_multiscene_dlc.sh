#!/usr/bin/env bash
# v19: 多场景融合训练 - DLC 提交脚本
set -e
set -o pipefail

dlc submit pytorchjob \
    --name=home_flow_2608_multiscene_v19_train \
    --command='set -e
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.19-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps \
            --force-reinstall
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
        --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
        -m tzrec.train_eval \
        --pipeline_config_path /mnt/data/deploy/home_flow_2608_v19/home_flow_2608_v19_multiscene.config \
        --train_input_path odps://mmb_sage/tables/home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1/dt=${train_ymd} \
        --eval_input_path odps://mmb_sage/tables/home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1/dt=${train_ymd} \
        --model_dir /mnt/data/deploy/home_flow_2608_v19/model/${train_ymd}

        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
        --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
        -m tzrec.export \
        --pipeline_config_path /mnt/data/deploy/home_flow_2608_v19/model/${train_ymd}/pipeline.config \
        --export_dir /mnt/data/deploy/home_flow_2608_v19/model/${train_ymd}/export/final' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=1 \
    --job_max_running_time_minutes=43200 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn6e-c12g1.12xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true
