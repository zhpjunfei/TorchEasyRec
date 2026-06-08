dlc submit pytorchjob \
    --name=home_flow_2604_v6_ple_d \
    --command='set -e
        # 新增：注入 PyODPS 网络容错环境变量
        export ODPS_TUNNEL_TIMEOUT=600
        export ODPS_REST_TIMEOUT=600
        export ODPS_TUNNEL_CONNECTION_POOL_SIZE=100
        export TUNNEL_READ_RETRY_TIMES=5
        # 新增：eval pipeline 非确定性修复 (P0, 2026-06-07)
        # 锁定 torch / numpy seed, 开启 cudnn deterministic, 关闭 TF32
        # tzrec/__init__.py 默认值=42, 但显式设更稳
        export TORCH_MANUAL_SEED=42
        export NUMPY_MANUAL_SEED=42
        export USE_DETERMINISTIC_ALGORITHMS=1
        # 每次 eval 入口重置 seed, 防止 1m22s 窗口内累积漂移
        export EVAL_SEED=42
        pip install https://mmb-spu.oss-cn-shenzhen.aliyuncs.com/EasyRec/py_modules/tzrec-1.2.16-py2.py3-none-any.whl \
            --extra-index-url=https://download.pytorch.org/whl/cu129 \
            --no-deps \
            --force-reinstall
        ODPS_ENDPOINT=http://service.cn-shenzhen-vpc.maxcompute.aliyun-inc.com/api \
        torchrun --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
        --nnodes=$WORLD_SIZE --nproc-per-node=$NPROC_PER_NODE --node_rank=$RANK \
        -m tzrec.train_eval \
        --pipeline_config_path /mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/home_flow_2604_v6_ple_d.config \
        --train_input_path odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight_train/dt=${train_ymd} \
        --eval_input_path odps://mmb_sage/tables/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_smpl_weight_val/dt=${train_ymd} \
        --model_dir /mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_debug/20260527_home_flow_2604_v6_ple_d_dup3
        ' \
    --data_sources=d-3ft3uqf5r6jixzfp2f \
    --workspace_id=252434 \
    --priority=1 \
    --job_max_running_time_minutes=43200 \
    --workers=1 \
    --worker_image=dsw-registry-vpc.cn-shenzhen.cr.aliyuncs.com/pai/torcheasyrec:1.2.0-pytorch2.11.0-gpu-py311-cu126-ubuntu22.04 \
    --worker_spec=ecs.gn7i-c32g1.16xlarge \
    --enable_credential=true \
    --disable_ecs_stock_check=true \
    --driver=535.161.08
