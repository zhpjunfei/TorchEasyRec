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

dlc submit pytorchjob \
    --name=home_flow_2604_pepnet_sorter_train_export_nsmpl \
    --command='set -e
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.16-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps \
            --force-reinstall
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
        --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
        -m tzrec.train_eval \
        --pipeline_config_path /mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/home_flow_2604_v11_title_vector.config \
        --train_input_path odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3/dt=${train_ymd} \
        --model_dir /mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_nsmpl/${train_ymd}

        INPUT_TILE=2 \
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
        --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
        -m tzrec.export \
        --pipeline_config_path /mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_nsmpl/${train_ymd}/pipeline.config \
        --export_dir /mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_nsmpl/${train_ymd}/export/final_with_fg' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=1 \
    --job_max_running_time_minutes=43200 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn7i-c32g1.32xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true
