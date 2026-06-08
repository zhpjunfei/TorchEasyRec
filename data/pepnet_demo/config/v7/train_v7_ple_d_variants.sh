#!/usr/bin/env bash
# 训练 v7_ple_d 的 4 个变种 (2×A10, 每跑 ~1.5h, 总计 6h sequential)
# v7 baseline: v7_ple = v6_ple (CVR 0.7878)
# v7 d 参考:  v7_ple_d = v6_ple_d (CVR 0.7922)
set -e
set -o pipefail

export ODPS_CONFIG_FILE_PATH="${ODPS_CONFIG_FILE_PATH:-/Users/zhangjunfei/.odps_conf}"
export PYTHONPATH="/Users/zhangjunfei/mmb/TorchEasyRec:${PYTHONPATH}"

CONFIG_DIR="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/config/v7"
TRAIN_TABLE="home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_train"
VAL_TABLE="home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_val"
TRAIN_PATH="odps://${TRAIN_TABLE}/dt=*"
EVAL_PATH="odps://${VAL_TABLE}/dt=${BIZDATE:-20260602}"
MODEL_BASE="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/experiments"
LOG_BASE="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/log"

MASTER_PORT=32555

run() {
  local VARIANT=$1
  local MODEL_DIR="${MODEL_BASE}/v7_${VARIANT}"
  local LOG_FILE="${LOG_BASE}/v7_${VARIANT}.log"
  local CONFIG="${CONFIG_DIR}/home_flow_2604_v7_ple_${VARIANT}.config"
  echo "================================================================"
  echo "启动 ${VARIANT}    $(date '+%F %T')"
  echo "config: ${CONFIG}"
  echo "model_dir: ${MODEL_DIR}"
  echo "log: ${LOG_FILE}"
  echo "================================================================"
  rm -rf "${MODEL_DIR}"
  mkdir -p "${MODEL_DIR}" "${LOG_BASE}"
  torchrun \
    --master_addr=localhost --master_port=${MASTER_PORT} \
    --nnodes=1 --nproc-per-node=2 --node_rank=0 \
    -m tzrec.train_eval \
    --pipeline_config_path "${CONFIG}" \
    --train_input_path "${TRAIN_PATH}" \
    --eval_input_path "${EVAL_PATH}" \
    --model_dir "${MODEL_DIR}" \
    2>&1 | tee "${LOG_FILE}"
  echo "${VARIANT} 完成    $(date '+%F %T')"
}

# 顺序: 控制实验优先 (dpage) → embed 变种 (d16, d32) → pub_hours 单特征 (ph)
run dpage
run d16
run d32
run ph

echo "================================================================"
echo "4 个变种全部完成    $(date '+%F %T')"
echo "查看最终结果:  grep 'auc_cvr' ${LOG_BASE}/v7_ple_*.log | grep -E 'auc_cvr'"
echo "================================================================"
