#!/usr/bin/env bash
# v19: 多场景融合建模实验
# - 基线: 仅 is_home_scene=1 样本
# - 新增: bijia/haojia/trend 场景辅助任务
# - 目标: 通过多场景行为信号提升搜索推荐 CTR
set -e
set -o pipefail

export ODPS_CONFIG_FILE_PATH="${ODPS_CONFIG_FILE_PATH:-/Users/zhangjunfei/.odps_conf}"
export PYTHONPATH="/Users/zhangjunfei/mmb/TorchEasyRec:${PYTHONPATH}"
export ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api

CONFIG_DIR="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/config/v19"
TRAIN_PATH="odps://mmb_sage/tables/home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1/dt=\${train_ymd}"
VAL_PATH="odps://mmb_sage/tables/home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1/dt=\${train_ymd}"
MODEL_BASE="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/experiments/v19_multiscene"
LOG_BASE="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/log"

MASTER_PORT=32555
TRAIN_CONFIG="${CONFIG_DIR}/home_flow_2608_v19_multiscene.config"

echo "================================================================"
echo "启动 v19 多场景融合实验    $(date '+%F %T')"
echo "config: ${TRAIN_CONFIG}"
echo "train: ${TRAIN_PATH}"
echo "eval: ${VAL_PATH}"
echo "model_dir: ${MODEL_BASE}"
echo "log: ${LOG_BASE}/v19_multiscene.log"
echo "================================================================"

rm -rf "${MODEL_BASE}"
mkdir -p "${MODEL_BASE}" "${LOG_BASE}"

torchrun \
  --master_addr=localhost --master_port=${MASTER_PORT} \
  --nnodes=1 --nproc-per-node=4 --node_rank=0 \
  -m tzrec.train_eval \
  --pipeline_config_path "${TRAIN_CONFIG}" \
  --train_input_path "${TRAIN_PATH}" \
  --eval_input_path "${VAL_PATH}" \
  --model_dir "${MODEL_BASE}" \
  2>&1 | tee "${LOG_BASE}/v19_multiscene.log"

echo "v19 多场景融合实验完成    $(date '+%F %T')"
echo "查看结果: grep 'auc' ${LOG_BASE}/v19_multiscene.log"
