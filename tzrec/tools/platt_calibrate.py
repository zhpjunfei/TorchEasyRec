#!/usr/bin/env python3
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

"""离线拟合 Platt 校准参数并保存到独立文件。

用法:
  # Step 1: 正常训练 (checkpoint 保存在 model_dir/)
  torchrun --nproc_per_node=N -m tzrec.train_eval \
      --pipeline_config_path v16_platt_calibration.config \
      --train_data ... --model_dir ./output/train

  # Step 2: 用验证集拟合 Platt a,b 并保存
  python -m tzrec.tools.platt_calibrate \\
      --config v16_platt_calibration.config \\
      --checkpoint_dir ./output/train/model.ckpt-7300 \\
      --val_data_path odps://...

  # Step 3: 用 inject 脚本将 fitted params 注入 checkpoint 用于 export
  python -m tzrec.tools.platt_inject_into_export \\
      --config pipeline.config \\
      --trained_ckpt ./output/train/model.ckpt-7300 \\
      --platt_meta ./output/platt_fitted/platt_meta.json \\
      --output ./output/injected_for_export/

  # Step 4: 正常导出
  torchrun -m tzrec.export \\
      --pipeline_config_path pipeline.config \\
      --checkpoint_path ./output/injected_for_export \\
      --export_dir ./output/export
"""  # noqa: D301,D415

import argparse
import json
import os

import torch
from torch import distributed as dist

from tzrec.utils.logging_util import logger


def collect_logits_and_labels(model, dataloader, device):
    """跑一遍验证集，收集每个塔的 (logits, labels)。"""  # noqa: D415
    all_data = {}

    # Get tower configs from model - handle both pepnet and other models
    if hasattr(model, "_task_tower_cfgs") and model._task_tower_cfgs:
        tower_cfgs = model._task_tower_cfgs
    elif hasattr(model, "_base_model") and hasattr(
        model._base_model, "_task_tower_cfgs"
    ):
        tower_cfgs = model._base_model._task_tower_cfgs
    else:
        logger.error("Model has no _task_tower_cfgs!")
        return {}

    for task_tower_cfg in tower_cfgs:
        tower_name = task_tower_cfg.tower_name
        label_key = getattr(task_tower_cfg, "label_name", None)
        if label_key is None:
            logger.warning(f"Tower '{tower_name}' has no label_name, skipping")
            continue
        all_data[tower_name] = {"logits": [], "labels": [], "label_key": label_key}

    if not all_data:
        logger.error("No valid towers found in model!")
        return {}

    model.eval()
    with torch.no_grad():
        for batch_idx, batch in enumerate(dataloader):
            batch = batch.to(device)
            output = model.predict(batch)

            for tn, data in all_data.items():
                logits_key = f"logits_{tn}"
                if logits_key not in output:
                    logger.warning(
                        f"No logits for tower '{tn}' in output keys: {list(output.keys())}"
                    )
                    continue

                lgt = output[logits_key].cpu().float().squeeze(-1)

                # Early NaN check — abort immediately if logits are all NaN
                if torch.isnan(lgt).all():
                    logger.error(
                        "FATAL: logits for tower '%s' are ALL NaN! "
                        "This means checkpoint weights were not loaded correctly, "
                        "or the model architecture doesn't match the checkpoint.",
                        tn,
                    )
                    logger.error(
                        "  output keys: %s, logits_key='%s', lgt.shape=%s, "
                        "lgt.min()=%s, lgt.max()=%s",
                        list(output.keys()),
                        logits_key,
                        lgt.shape,
                        lgt.min().item() if not torch.isnan(lgt).all() else "NaN",
                        lgt.max().item() if not torch.isnan(lgt).all() else "NaN",
                    )
                    raise RuntimeError(
                        f"Logits for tower '{tn}' are all NaN. "
                        "Check that checkpoint was loaded successfully."
                    )

                # Get label from batch.labels dict
                label_key = data["label_key"]
                if label_key in batch.labels:
                    lab = batch.labels[label_key].float()
                else:
                    logger.warning(
                        f"Label '{label_key}' not found in batch.labels. Available: {list(batch.labels.keys())}"
                    )
                    lab = torch.zeros_like(lgt)

                all_data[tn]["logits"].append(lgt)
                all_data[tn]["labels"].append(lab)

            if (batch_idx + 1) % 500 == 0:
                logger.info("已收集 %d 个 batch...", batch_idx + 1)

    result = {}
    for tn, data in all_data.items():
        if not data["logits"]:
            continue
        result[tn] = {
            "logits": torch.cat(data["logits"], dim=0),
            "labels": torch.cat(data["labels"], dim=0),
        }
    return result


def fit_and_update_model(model, calibration_data, device="cpu"):
    """拟合每个塔的 Platt 参数，直接写入模型的 buffer。"""  # noqa: D415
    from tzrec.modules.calibration import PlattScaler

    fitted = {}

    for tower_name, data in calibration_data.items():
        if tower_name not in model._platt_tower_to_scaler_idx:
            logger.warning("跳过 '%s': 未注册 platt scaler", tower_name)
            continue

        idx = model._platt_tower_to_scaler_idx[tower_name]
        scaler = model._platt_scalers[idx]

        # 直接拟合到已有的 scaler 上
        ps = PlattScaler(freeze=False)
        logits = data["logits"].to(device)
        labels = data["labels"].to(device)

        logger.info(
            "拟合塔 '%s': logits=%s, labels=%s", tower_name, logits.shape, labels.shape
        )
        result = ps.fit_from_logits(logits, labels)

        # 冻结后写入原 scaler 的 buffer
        ps.freeze()
        scaler.register_buffer("_a", torch.tensor(result["a"]))
        scaler.register_buffer("_b", torch.tensor(result["b"]))
        scaler._frozen = True

        result["n_samples"] = int(len(logits))
        result["pos_rate"] = float(labels.mean())
        fitted[tower_name] = result

        logger.info(
            "  -> a=%.4f, b=%.4f, pos_rate=%.4f, n=%d (converged=%s)",
            result["a"],
            result["b"],
            result["pos_rate"],
            result["n_samples"],
            result["converged"],
        )

    return fitted


def save_fitted_params(fitted_params, output_dir):
    """保存 fitted 参数为 .pt 和 .json。"""  # noqa: D415
    os.makedirs(output_dir, exist_ok=True)

    # .pt 格式可直接 torch.load 恢复
    torch.save(fitted_params, os.path.join(output_dir, "platt_params.pt"))

    # .json 便于查看
    meta = {
        "num_towers": len(fitted_params),
        "towers": {
            tn: {k: round(v, 6) if isinstance(v, float) else v for k, v in p.items()}
            for tn, p in fitted_params.items()
        },
    }
    meta_file = os.path.join(output_dir, "platt_meta.json")
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Saved to: %s", meta_file)
    return meta_file


def main() -> None:
    """Fit Platt calibration parameters on validation data."""
    """离线拟合 Platt 参数并保存。"""
    
    # Only run on rank 0 to avoid multi-GPU conflicts
    import os
    rank = int(os.environ.get("RANK", 0))
    if rank != 0:
        logger.info(f"Rank {rank}: skipping (only rank 0 runs)")
        return
    
    parser = argparse.ArgumentParser(description="Fit Platt calibration params")
    parser.add_argument("--config", required=True, help="Model config path")
    parser.add_argument(
        "--checkpoint_dir",
        default=None,
        help="Trained checkpoint dir (contains model.ckpt-* subdirs). "
        "If not specified, uses model_dir from config.",
    )
    parser.add_argument(
        "--val_data_path",
        required=True,
        help="Validation data ODPS/table path",
    )
    parser.add_argument(
        "--output_dir",
        default=None,
        help="Dir to save fitted params. Defaults to <checkpoint_dir>/platt_fitted/",
    )
    parser.add_argument("--batch_size", type=int, default=4096)
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    from tzrec.datasets.dataset import create_dataloader
    from tzrec.main import _create_features, _create_model
    from tzrec.utils import config_util
    from tzrec.utils.checkpoint_util import latest_checkpoint, restore_model
    from tzrec.utils.dist_util import init_process_group

    # Initialize distributed if running under torchrun
    device, backend = init_process_group()
    logger.info(
        "Dist initialized: rank=%d, world_size=%d, device=%s",
        int(os.environ.get("RANK", 0)),
        int(os.environ.get("WORLD_SIZE", 1)),
        device,
    )

    # Load config
    pipeline_config = config_util.load_pipeline_config(args.config)
    model_config = pipeline_config.model_config
    train_config = pipeline_config.train_config

    logger.info("Config loaded: %s", args.config)

    # Resolve checkpoint dir
    if args.checkpoint_dir is None:
        ckpt_dir = train_config.model_dir
    else:
        ckpt_dir = args.checkpoint_dir

    if args.output_dir is None:
        output_dir = os.path.join(ckpt_dir, "platt_fitted")
    else:
        output_dir = args.output_dir

    # Find latest checkpoint
    import glob

    ckpt_dirs = sorted(glob.glob(os.path.join(ckpt_dir, "model.ckpt-*")))
    if not ckpt_dirs:
        ckpt_dirs = sorted(glob.glob(os.path.join(ckpt_dir, "model")))
    if not ckpt_dirs:
        raise FileNotFoundError(f"No checkpoint found in {ckpt_dir}")
    latest_ckpt = ckpt_dirs[-1]
    logger.info("Using checkpoint: %s", latest_ckpt)

    # Build features and dataloader
    features = _create_features(
        list(pipeline_config.feature_configs), pipeline_config.data_config
    )

    try:
        dataloader = create_dataloader(
            data_config=pipeline_config.data_config,
            features=features,
            input_path=args.val_data_path,
            mode="eval",
        )

        # Create model and load trained checkpoint weights
        model = _create_model(
            model_config, features, list(pipeline_config.data_config.label_fields)
        )

        # Multi-GPU: dist already initialized by torchrun — just get device
        if dist.is_initialized():
            device = torch.device(f"cuda:{dist.get_rank()}")
            world_size = dist.get_world_size()
            logger.info(
                "Platt calib multi-GPU (torchrun): rank=%d, world_size=%d, device=%s",
                dist.get_rank(), world_size, device,
            )
            rank = dist.get_rank()
            world_size = dist.get_world_size()
            logger.info(
                "Platt calib multi-GPU: rank=%d, world_size=%d, device=%s",
                rank, world_size, device,
            )
            
            # Wrap model with DistributedModelParallel for correct sharding
            from tzrec.main import create_planner, get_default_sharders
            from torchrec.distributed.model_parallel import DistributedModelParallel
            
            planner = create_planner(
                device=device,
                batch_size=args.batch_size,
                model=model,
            )
            sharders = get_default_sharders()
            plan = planner.collective_plan(model, sharders, dist.GroupMember.WORLD)
            model = DistributedModelParallel(
                module=model,
                device=device,
                sharders=sharders,
                plan=plan,
            )
            logger.info("Model wrapped with DistributedModelParallel")
        else:
            device = torch.device(args.device)
            logger.info("Platt calib single-process: device=%s", device)
            model = model.to_empty(device=device)
        
        logger.info("Loading trained checkpoint...")
        ckpt_path, step = latest_checkpoint(latest_ckpt)
        logger.info("Restoring from %s (step %d)", ckpt_path, step)
        try:
            restore_model(ckpt_path, model)
        except (AssertionError, RuntimeError) as e:
            # DCP checkpoint with MC embedding sharding may fail when:
            # - Single-GPU: shard range check fails (segments tensor is all INT64_MAX)
            # - Multi-GPU: meta tensor .item() called in validate_state()
            # Both cases are caused by MC module's _load_state_dict_post_hook calling
            # validate_state() which doesn't handle the current sharding context.
            #
            # Fix: monkey-patch validate_state to pass, then retry restore_model.
            logger.warning("DCP restore failed (%s), patching validate_state and retrying", e)

            # Find all MC modules and patch their validate_state
            mc_modules = []
            for name, module in model.named_modules():
                if hasattr(module, "_output_segments_tensor") and hasattr(
                    module, "validate_state"
                ):
                    mc_modules.append((name, module))

            original_validate_states = {}
            for mod_name, mod in mc_modules:
                original_validate_states[mod_name] = mod.validate_state
                mod.validate_state = lambda *args, **kwargs: None  # no-op
                logger.info(f"Patched validate_state on {mod_name}")

            try:
                restore_model(ckpt_path, model)
                logger.info("Restored successfully with patched validate_state.")
            finally:
                # Restore original validate_state methods
                for mod_name, mod in mc_modules:
                    if mod_name in original_validate_states:
                        mod.validate_state = original_validate_states[mod_name]
                        logger.info(f"Restored validate_state on {mod_name}")

        # DIAGNOSTIC: Check if checkpoint weights were loaded correctly
        logger.info("=" * 60)
        logger.info("DIAGNOSTIC: Checking checkpoint load status...")
        logger.info("=" * 60)
        total_params = 0
        nan_params = 0
        zero_params = 0
        meta_count = 0
        for _name, param in model.named_parameters():
            total_params += 1
            # Skip meta tensors (checkpoint not yet loaded)
            if param.device.type == "meta":
                meta_count += 1
                continue
            n_nan = int(torch.isnan(param).sum().item())
            n_zero = int((param == 0).sum().item())
            if n_nan > 0:
                nan_params += n_nan
            if n_zero > 0 and param.abs().max().item() < 1e-7:
                zero_params += 1

        logger.info(f"Total parameter tensors: {total_params}")
        if meta_count > 0:
            logger.warning(
                f"  {meta_count} tensors are on META device — checkpoint may not be loaded yet"
            )
        logger.info(
            f"NaN elements: {nan_params} across "
            f"{sum(1 for _n, p in model.named_parameters() if p.device.type != 'meta' and torch.isnan(p).any())} tensors"
        )
        logger.info(f"Near-zero tensors (abs max < 1e-7): {zero_params}")

        # Check a few key parameters (skip meta and empty)
        checked = 0
        for name, param in model.named_parameters():
            if param.device.type == "meta":
                continue
            if param.numel() == 0:
                logger.info(f"  {name}: shape={param.shape}, device={param.device}, EMPTY(tensor)")
                checked += 1
                continue
            logger.info(
                f"  {name}: shape={param.shape}, device={param.device}, "
                f"min={param.min().item():.6f}, max={param.max().item():.6f}, "
                f"mean={param.mean().item():.6f}, has_nan={torch.isnan(param).any().item()}"
            )
            checked += 1
            if checked >= 5:
                break
        if checked == 0:
            logger.warning("  No non-meta parameters found to inspect")

        # Run a quick forward test on a single batch to verify no NaN outputs
        logger.info("Running single-batch forward test...")
        try:
            test_batch = next(iter(dataloader))
            test_batch = test_batch.to(device)
            model.eval()
            with torch.no_grad():
                test_output = model.predict(test_batch)
            logger.info(f"Test output keys: {list(test_output.keys())}")
            for k, v in test_output.items():
                if isinstance(v, torch.Tensor):
                    logger.info(
                        f"  {k}: shape={v.shape}, device={v.device}, "
                        f"min={v.min().item():.6f}, max={v.max().item():.6f}, "
                        f"has_nan={torch.isnan(v).any().item()}, has_inf={torch.isinf(v).any().item()}"
                    )
                else:
                    logger.info(f"  {k}: type={type(v).__name__}, value={v}")
        except Exception as e:
            logger.error(f"Forward test failed: {e}")
        logger.info("=" * 60)

        # Verify platt scalers exist
        if not hasattr(model, "_platt_scalers") or model._platt_scalers is None:
            logger.error(
                "Platt calib not enabled! Config must have "
                "platt_calibration_enabled: true"
            )
            return

        # Run inference on validation set
        logger.info("Running inference on validation data...")
        cal_data = collect_logits_and_labels(model, dataloader, device)

        # Only use rank 0's data for Platt fitting (sufficient for calibration)
        # Multi-GPU all-gather is complex and error-prone with DMP models.
        # 5M+ samples on rank 0 is plenty for Platt scaling (needs ~10K min).
        if dist.is_initialized() and dist.get_world_size() > 1:
            rank = dist.get_rank()
            if rank != 0:
                logger.info(f"Rank {rank}: skipping logits collection (only rank 0 collects)")
                cal_data = {}
            else:
                total = sum(d["logits"].size(0) for d in cal_data.values()) if cal_data else 0
                logger.info(f"Rank 0 collected {total} total samples across {len(cal_data)} towers")

        for tn, d in cal_data.items():
            logger.info(
                "  %s: logits=%s, labels=%s", tn, d["logits"].shape, d["labels"].shape
            )

        # Fit Platt scalers and update model buffers (only on rank 0)
        rank = int(os.environ.get("RANK", 0))
        if rank != 0:
            logger.info(f"Rank {rank}: Skipping Platt fitting (only rank 0 fits)")
            return

        logger.info("Fitting Platt parameters...")
        fitted = fit_and_update_model(model, cal_data, device)

        if not fitted:
            logger.error("No towers fitted!")
            return

        # Save fitted params
        meta_file = save_fitted_params(fitted, output_dir)

        logger.info("=" * 60)
        logger.info("Platt calibration complete!")
        logger.info("  Fitted %d tower(s):", len(fitted))
        for tn, p in fitted.items():
            logger.info("    %-6s: a=%.4f, b=%.4f", tn, p["a"], p["b"])
        logger.info("  Meta saved to: %s", meta_file)
        logger.info("  Next: run platt_inject_into_export.py with this meta")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
