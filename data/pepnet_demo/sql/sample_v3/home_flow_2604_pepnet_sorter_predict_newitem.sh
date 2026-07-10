# ==========================================
# 新老帖子预估分数分布对比 (DLC predict)
# Usage:
#   bash path/to/this_script.sh <train_ymd> <pipeline_config_path>
#
# Example:
#   bash path/to/this_script.sh 20260628 \
#     /mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_nsmpl/20260628/pipeline.config
# ==========================================

set -e


INPUT_TABLE="mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v3_val"
OUTPUT_TABLE="${INPUT_TABLE}_pred_score_check"

INPUT_PATH="odps://${INPUT_TABLE}/dt=${train_ymd}"
OUTPUT_PATH="odps://${OUTPUT_TABLE}/dt=${train_ymd}"

dlc submit pytorchjob \
    --name=home_flow_2604_pepnet_sorter_predict_newitem \
    --command='set -e
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.16-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps \
            --force-reinstall
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
        --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
        -m tzrec.predict \
        --pipeline_config_path '/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_search_smpl/${train_ymd}/pipeline.config' \
        --predict_input_path '"${INPUT_PATH}"' \
        --predict_output_path '"${OUTPUT_PATH}"' \
        --reserved_columns "isnewitem_fg" \
        --output_columns "probs_ctr,probs_cvr"
        echo "=== Predict done. Output table: '${OUTPUT_TABLE}' dt='${train_ymd}' ==="' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=8 \
    --job_max_running_time_minutes=1440 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn7i-c32g1.32xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true
