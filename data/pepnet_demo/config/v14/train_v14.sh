#!/usr/bin/env bash
# v14: CVR 正则化修复实验
#   修复 LHUC_PPNet 忽略 dropout_ratio 的 bug 后，测试 CVR tower 正则化组合
set -e
set -o pipefail

export ODPS_CONFIG_FILE_PATH="${ODPS_CONFIG_FILE_PATH:-/Users/zhangjunfei/.odps_conf}"
export PYTHONPATH="/Users/zhangjunfei/mmb/TorchEasyRec:${PYTHONPATH}"

# ==================== 先安装修复后的 wheel ====================
# pip install --force-reinstall '/Users/zhangjunfei/mmb/TorchEasyRec/dist/tzrec-1.2.19-py2.py3-none-any.whl'

CONFIG_DIR="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/config/v14"
#  TODO: 确认 v3 pipeline 的训练/验证表
# v7-v10 用的 v3: home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_{train,val}
TRAIN_PATH="odps://mmb_sage/tables/XXXX_train/dt=*"
EVAL_PATH="odps://mmb_sage/tables/XXXX_val/dt=${BIZDATE:-20260626}"
MODEL_BASE="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/experiments"
LOG_BASE="/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/log"

MASTER_PORT=32555

# A: [256,128] 容量缩减 + dropout=0.3
# B: [512,256,128] dropout=0.3（dropout on 原始架构）
# C: out_task_space_weight=0.01（采样偏差）
# D: [256,128] + dropout=0.3 + CVR wd=0.03（容量+dropout+wd）
EXPERIMENTS=("a" "b" "c" "d")

run() {
  local EXPERIMENT=$1
  local MODEL_DIR="${MODEL_BASE}/v14_${EXPERIMENT}"
  local LOG_FILE="${LOG_BASE}/v14_${EXPERIMENT}.log"
  local CONFIG="${CONFIG_DIR}/home_flow_2604_v14_config_${EXPERIMENT}.config"
  echo "================================================================"
  echo "启动 v14_${EXPERIMENT}    $(date '+%F %T')"
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
  echo "v14_${EXPERIMENT} 完成    $(date '+%F %T')"
}

# 全部 6 个实验
for exp in "${EXPERIMENTS[@]}"; do
  run "$exp"
done

echo "================================================================"
echo "全部完成    $(date '+%F %T')"
echo "查看结果:  grep 'auc_cvr' ${LOG_BASE}/v14_*.log | grep -E 'auc_cvr'"
echo "================================================================"
