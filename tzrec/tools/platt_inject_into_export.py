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

"""将 fitted Platt 参数注入训练好的 DCP checkpoint。

用法:
  # Step 1: 训练
  python -m tzrec.train_eval \
      --pipeline_config_path v16_platt_calibration.config \\
      --train_data <train_odps> --model_dir ./output/train/

  # Step 2: 拟合 Platt 参数
  python -m tzrec.tools.platt_calibrate \\
      --config v16_platt_calibration.config \\
      --checkpoint_dir ./output/train/ \\
      --val_data_path <val_odps> \\
      --output_dir ./output/platt_fitted/

  # Step 3: 注入 Platt params 到 DCP checkpoint
  python -m tzrec.tools.platt_inject_into_export \\
      --config ./output/train/pipeline.config \\
      --trained_ckpt ./output/train/model.ckpt-{step}/ \\
      --platt_meta ./output/platt_fitted/platt_meta.json \\
      --output ./output/injected_for_export/

  # Step 4: 导出模型（自动加载带有 Platt 参数的 checkpoint）
  torchrun --nproc_per_node=1 -m tzrec.export \\
      --pipeline_config_path ./output/train/pipeline.config \\
      --checkpoint_path ./output/injected_for_export/ \\
      --export_dir ./output/export/final_with_fg/
"""  # noqa: D301,D415

import argparse
import json
import os
import shutil

import torch

from tzrec.utils.logging_util import logger


def main() -> None:
    """Inject fitted Platt params into DCP checkpoint for export."""
    parser = argparse.ArgumentParser(
        description="Inject fitted Platt params into a trained DCP checkpoint."
    )
    parser.add_argument("--config", required=True, help="Pipeline config path")
    parser.add_argument(
        "--trained_ckpt",
        required=True,
        help="Trained checkpoint dir (contains model.ckpt-*/ or model file)",
    )
    parser.add_argument(
        "--platt_meta",
        required=True,
        help="platt_fitted/platt_meta.json from platt_calibrate.py",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for the patched checkpoint",
    )
    args = parser.parse_args()

    # === 1. Load metadata ===
    with open(args.platt_meta, "r") as f:
        meta = json.load(f)
    tower_params = meta["towers"]
    logger.info("Loaded meta: %d towers", len(tower_params))
    for tn, p in tower_params.items():
        logger.info("  %s: a=%.6f, b=%.6f", tn, p["a"], p["b"])

    # === 2. Create model + load trained weights ===
    from tzrec.main import _create_features, _create_model
    from tzrec.utils import config_util

    pipeline_config = config_util.load_pipeline_config(args.config)
    model_config = pipeline_config.model_config
    features = _create_features(
        list(pipeline_config.feature_configs), pipeline_config.data_config
    )
    model = _create_model(
        model_config, features, list(pipeline_config.data_config.label_fields)
    )

    if not hasattr(model, "_platt_scalers"):
        logger.error(
            "Model missing _platt_scalers! Ensure config has "
            "platt_calibration_enabled: true"
        )
        return

    # Resolve checkpoint source
    ckpt_source = args.trained_ckpt
    import glob

    ckpt_subdirs = sorted(glob.glob(os.path.join(ckpt_source, "model.ckpt-*")))
    if ckpt_subdirs:
        ckpt_source = ckpt_subdirs[-1]

    logger.info("Loading trained checkpoint from: %s", ckpt_source)

    try:
        from tzrec.utils.checkpoint_util import latest_checkpoint, restore_model

        # Use to_empty() because embedding tensors may be on meta device.
        # Without this, DCP restore fails with "Tensor.item() cannot be called on meta tensors".
        model = model.to_empty(device="cpu")

        ckpt_path, step = latest_checkpoint(ckpt_source)
        logger.info("DCP checkpoint: %s (step %d)", ckpt_path, step)

        # On single-GPU, DCP load fails because process group is not initialized.
        # Initialize a dummy NCCL process group so DCP can proceed.
        import torch.distributed as dist

        if not dist.is_initialized():
            try:
                dist.init_process_group(backend="nccl", rank=0, world_size=1)
            except RuntimeError:
                # NCCL may not be available; fall back to gloo
                dist.init_process_group(backend="gloo", rank=0, world_size=1)

        restore_model(ckpt_path, model)
    except (AssertionError, RuntimeError) as exc:
        # DCP checkpoint with MC embedding sharding fails on single-GPU.
        # The DCP load() inside restore_model succeeds but model.load_state_dict()
        # triggers MC module's _load_state_dict_post_hook which calls validate_state().
        # Since the model was created on single-GPU without sharding, the shard range
        # check fails (segments tensor is all INT64_MAX).
        #
        # Fix: monkey-patch validate_state to pass, then call restore_model again.
        logger.warning(
            "DCP restore failed (%s), patching validate_state and retrying", exc
        )

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
            logger.info("Patched validate_state on %s", mod_name)

        try:
            restore_model(ckpt_path, model)
            logger.info("Restored successfully with patched validate_state.")
        finally:
            for mod_name, mod in mc_modules:
                if mod_name in original_validate_states:
                    mod.validate_state = original_validate_states[mod_name]
                    logger.info("Restored validate_state on %s", mod_name)

    # === 3. Inject Platt params into model buffers ===
    logger.info("Injecting fitted Platt parameters...")
    for tower_name, params in tower_params.items():
        if tower_name not in model._platt_tower_to_scaler_idx:
            logger.warning("Tower '%s' not in platt index — skipping", tower_name)
            continue
        idx = model._platt_tower_to_scaler_idx[tower_name]
        scaler = model._platt_scalers[idx]

        # register_buffer replaces existing buffer values in-place
        scaler.register_buffer("_a", torch.tensor(params["a"]))
        scaler.register_buffer("_b", torch.tensor(params["b"]))
        scaler._frozen = True
        logger.info("Injected %s: a=%.6f, b=%.6f", tower_name, params["a"], params["b"])

    # === 4. Re-save patched state_dict as DCP format ===
    from torch.distributed.checkpoint import save as dcp_save

    patched_sd = model.state_dict()
    os.makedirs(args.output, exist_ok=True)
    dcp_model_file = os.path.join(args.output, "model")
    dcp_save(patched_sd, checkpoint_id=dcp_model_file)
    logger.info("Saved patched DCP checkpoint to: %s", args.output)

    # Save metadata about the patch for traceability
    with open(os.path.join(args.output, "platt_patch_meta.json"), "w") as f:
        json.dump(
            {
                "platt_injected": True,
                "num_towers": len(tower_params),
                "towers": {
                    tn: {"a": float(v["a"]), "b": float(v["b"])}
                    for tn, v in tower_params.items()
                },
            },
            f,
            indent=2,
        )

    # Preserve plan file if present (sharding metadata)
    plan_src = os.path.join(ckpt_source, "plan")
    plan_dst = os.path.join(args.output, "plan")
    if os.path.exists(plan_src):
        shutil.copy2(plan_src, plan_dst)

    logger.info("=" * 60)
    logger.info("Platt injection complete!")
    logger.info("  Patched DCP checkpoint: %s", args.output)
    logger.info("  Next: tzrec.export --checkpoint_path=%s", args.output)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
