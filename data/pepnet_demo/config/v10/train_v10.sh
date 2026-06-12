#!/usr/bin/env bash
# 训练 v10 实验: baseline vs title_vector (4GPU, ~2h each)
set -e
set -o pipefail

export ODPS_CONFIG_FILE_PATH="${ODPS_CONFIG_FILE_PATH:-/Users/zhangjunfei/.odps_conf}"
export PYTHONPATH="/Users/zhangjunfei/mmb/TorchEasyRec:${PYTHONPATH}"

CONFIG_DIR="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/config/v10"
# TODO: 确认 v1c pipeline 的训练/验证表名
# v7 用的 v3: home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_{train,val}
# v8/v9 v1c: 请填写实际表名
TRAIN_PATH="odps://TODO_V1C_TRAIN_TABLE/dt=*"
EVAL_PATH="odps://TODO_V1C_VAL_TABLE/dt=${BIZDATE:-20260611}"
MODEL_BASE="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/experiments"
LOG_BASE="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/log"

MASTER_PORT=32555

run() {
  local EXPERIMENT=$1
  local MODEL_DIR="${MODEL_BASE}/v10_${EXPERIMENT}"
  local LOG_FILE="${LOG_BASE}/v10_${EXPERIMENT}.log"
  local CONFIG="${CONFIG_DIR}/home_flow_2604_v10_${EXPERIMENT}.config"
  echo "================================================================"
  echo "启动 ${EXPERIMENT}    $(date '+%F %T')"
  echo "config: ${CONFIG}"
  echo "model_dir: ${MODEL_DIR}"
  echo "log: ${LOG_FILE}"
  echo "================================================================"
  rm -rf "${MODEL_DIR}"
  mkdir -p "${MODEL_DIR}" "${LOG_BASE}"
  torchrun \
    --master_addr=localhost --master_port=${MASTER_PORT} \
    --nnodes=1 --nproc-per-node=4 --node_rank=0 \
    -m tzrec.train_eval \
    --pipeline_config_path "${CONFIG}" \
    --train_input_path "${TRAIN_PATH}" \
    --eval_input_path "${EVAL_PATH}" \
    --model_dir "${MODEL_DIR}" \
    2>&1 | tee "${LOG_FILE}"
  echo "${EXPERIMENT} 完成    $(date '+%F %T')"
}

run baseline
run title_vector

echo "================================================================"
echo "全部完成    $(date '+%F %T')"
echo "查看结果:  grep 'auc_cvr' ${LOG_BASE}/v10_*.log | grep -E 'auc_cvr'"
echo "================================================================"
