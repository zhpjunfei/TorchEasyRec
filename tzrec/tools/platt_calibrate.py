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
                        f"No logits for tower '{tn}' "
                        f"in output keys: {list(output.keys())}"
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
                        f"Label '{label_key}' not found "
                        f"in batch.labels. Available: "
                        f"{list(batch.labels.keys())}"
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
        with torch.no_grad():
            lgt_sorted = logits.sort().values
            logger.info(
                "  logit 分布: min=%+.4f, p1=%+.4f, p10=%+.4f, p50=%+.4f, "
                "p90=%+.4f, p99=%+.4f, max=%+.4f, mean=%+.4f, std=%.4f",
                lgt_sorted[0].item(),
                lgt_sorted[int(len(lgt_sorted) * 0.01)].item(),
                lgt_sorted[int(len(lgt_sorted) * 0.10)].item(),
                lgt_sorted[int(len(lgt_sorted) * 0.50)].item(),
                lgt_sorted[int(len(lgt_sorted) * 0.90)].item(),
                lgt_sorted[int(len(lgt_sorted) * 0.99)].item(),
                lgt_sorted[-1].item(),
                logits.mean().item(),
                logits.std().item(),
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

    import os

    rank = int(os.environ.get("RANK", 0))

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
    from tzrec.utils.checkpoint_util import latest_checkpoint
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

        # Single-process mode: load full model on cuda:0
        device = torch.device(args.device)
        logger.info("Platt calib single-process: device=%s", device)
        model = model.to_empty(device=device)

        logger.info("Loading trained checkpoint...")
        ckpt_path, step = latest_checkpoint(latest_ckpt)
        logger.info("Restoring from %s (step %d)", ckpt_path, step)

        # DIAGNOSTIC: Check state_dict keys before and after restore
        pre_sample = {k: v.shape for k, v in list(model.state_dict().items())[:3]}
        logger.info("Pre-restore sample keys: %s", pre_sample)

        # DCP bridge: load multi-GPU DCP checkpoint on single GPU.
        # Step 1: read checkpoint metadata to determine actual key format
        from torch.distributed.checkpoint import FileSystemReader
        from torch.distributed.checkpoint import load as dcp_load

        from tzrec.utils.checkpoint_util import PartialLoadPlanner

        model_ckpt_path = os.path.join(ckpt_path, "model")
        logger.info("DCP bridge: loading from %s", model_ckpt_path)

        ckpt_metadata = FileSystemReader(model_ckpt_path).read_metadata()
        ckpt_keys = set(ckpt_metadata.state_dict_metadata.keys())
        logger.info("Checkpoint metadata: %d keys total", len(ckpt_keys))

        logger.info("Sample checkpoint keys (first 5):")
        for i, k in enumerate(sorted(ckpt_keys)[:5]):
            logger.info("  CKPT[%d] %s", i, k)
        logger.info("Sample checkpoint keys (last 5):")
        all_ckpt_sorted = sorted(ckpt_keys)
        for i, k in enumerate(all_ckpt_sorted[-5:]):
            logger.info("  CKPT[-%d] %s", 5 - i, k)

        # Step 2: for each bare model key, find matching checkpoint key
        bare_sd_template = model.state_dict()
        bridge_sd = {}
        ckpt_to_bare = {}  # checkpoint_key -> bare_key
        bare_to_ckpt = {}  # bare_key -> checkpoint_key

        for bare_key, template_tensor in bare_sd_template.items():
            for ckpt_key in (
                bare_key,
                f"model.{bare_key}",
                f"_dmp_wrapped_module.module.{bare_key}",
                f"_dmp_wrapped_module.module.model.{bare_key}",
                f"_dmp_wrapped_module.{bare_key}",
                f"module.{bare_key}",
            ):
                if ckpt_key in ckpt_keys:
                    bridge_sd[ckpt_key] = torch.zeros_like(template_tensor)
                    ckpt_to_bare[ckpt_key] = bare_key
                    bare_to_ckpt[bare_key] = ckpt_key
                    break
            else:
                logger.warning(
                    "No checkpoint key matched for bare param [%s]", bare_key
                )

        logger.info(
            "Bridge: matched %d / %d bare params to checkpoint keys",
            len(bare_to_ckpt),
            len(bare_sd_template),
        )

        # Step 3: DCP load into bridge state dict
        dcp_load(bridge_sd, checkpoint_id=model_ckpt_path, planner=PartialLoadPlanner())

        # Step 4: build bare_sd from bridge, then use model.load_state_dict()
        # (AutoDisEmbedding custom _load_from_state_dict handles per-feature slices)
        bare_sd = {}
        for ckpt_key, loaded_tensor in bridge_sd.items():
            bare_key = ckpt_to_bare[ckpt_key]
            bare_sd[bare_key] = loaded_tensor

        mc_modules = []
        for name, module in model.named_modules():
            if hasattr(module, "_output_segments_tensor") and hasattr(
                module, "validate_state"
            ):
                mc_modules.append((name, module))
        original_validate_states = {}
        for mod_name, mod in mc_modules:
            original_validate_states[mod_name] = mod.validate_state
            mod.validate_state = lambda *args, **kwargs: None

        try:
            load_result = model.load_state_dict(bare_sd, strict=False)
            if load_result.missing_keys:
                logger.warning("Missing keys: %d", len(load_result.missing_keys))
            if load_result.unexpected_keys:
                logger.warning("Unexpected keys: %d", len(load_result.unexpected_keys))
        finally:
            for mod_name, mod in mc_modules:
                if mod_name in original_validate_states:
                    mod.validate_state = original_validate_states[mod_name]

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
                f"  {meta_count} tensors are on META "
                f"device — checkpoint may not be loaded yet"
            )
        nan_tensors = [
            (n, p)
            for n, p in model.named_parameters()
            if p.device.type != "meta" and torch.isnan(p).any()
        ]
        logger.info(f"NaN elements: {nan_params} across {len(nan_tensors)} tensors")
        for n, p in nan_tensors:
            logger.info(
                "  NaN PARAM: %s  shape=%s  num_nan=%d",
                n,
                p.shape,
                int(torch.isnan(p).sum().item()),
            )

        # Also check buffers for NaN (norm buffers like running_mean/var)
        nan_bufs = [
            (n, b)
            for n, b in model.named_buffers()
            if b.device.type != "meta" and torch.isnan(b).any()
        ]
        for n, b in nan_bufs:
            logger.info(
                "  NaN BUFFER: %s  shape=%s  num_nan=%d",
                n,
                b.shape,
                int(torch.isnan(b).sum().item()),
            )

        logger.info(f"Near-zero tensors (abs max < 1e-7): {zero_params}")

        # Log a few sample loaded tensors (prioritize NaN ones)
        nan_logged = set()
        checked = 0
        for name, param in model.named_parameters():
            if param.device.type == "meta":
                continue
            if name in nan_logged:
                continue
            if torch.isnan(param).any():
                nan_logged.add(name)
            p_min = param.min().item() if param.numel() > 0 else 0.0
            p_max = param.max().item() if param.numel() > 0 else 0.0
            p_mean = param.mean().item() if param.numel() > 0 else 0.0
            logger.info(
                f"  {name}: shape={param.shape}, device={param.device}, "
                f"min={p_min:.6f}, max={p_max:.6f}, mean={p_mean:.6f}, "
                f"has_nan={torch.isnan(param).any().item()}"
            )
            checked += 1
            if checked >= 10:
                break

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
                        f"has_nan={torch.isnan(v).any().item()}, "
                        f"has_inf={torch.isinf(v).any().item()}"
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
                logger.info(
                    f"Rank {rank}: skipping logits collection (only rank 0 collects)"
                )
                cal_data = {}
            else:
                total = (
                    sum(d["logits"].size(0) for d in cal_data.values())
                    if cal_data
                    else 0
                )
                logger.info(
                    f"Rank 0 collected {total} total samples "
                    f"across {len(cal_data)} towers"
                )

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
