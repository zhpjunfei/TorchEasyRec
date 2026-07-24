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
  python tools/platt_calibrate.py \\
      --config v16_platt_calibration.config \\
      --checkpoint_dir ./output/train/ \\
      --val_data_path <val_odps> \\
      --output_dir ./output/platt_fitted/

  # Step 3: 注入 Platt params 到 DCP checkpoint
  python tools/platt_inject_into_export.py \\
      --config ./output/train/pipeline.config \\
      --trained_ckpt ./output/train/model.ckpt-{step}/ \\
      --platt_meta ./output/platt_fitted/platt_meta.json \\
      --output ./output/injected_for_export/

  # Step 4: 导出模型（自动加载带有 Platt 参数的 checkpoint）
  torchrun --nproc_per_node=1 -m tzrec.export \\
      --pipeline_config_path ./output/train/pipeline.config \\
      --checkpoint_path ./output/injected_for_export/ \\
      --export_dir ./output/export/final_with_fg/
"""

import argparse
import json
import logging
import os
import shutil

import torch

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
)


def main():
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
    logging.info("Loaded meta: %d towers", len(tower_params))
    for tn, p in tower_params.items():
        logging.info("  %s: a=%.6f, b=%.6f", tn, p["a"], p["b"])

    # === 2. Create model + load trained weights ===
    from tzrec.main import _create_features, init_model, parse_model_configs

    model_config, train_config, export_config = parse_model_configs(args.config)
    features = _create_features(
        list(model_config.feature_configs), train_config.data_config
    )
    model, _ = init_model(model_config, train_config, export_config)

    if not hasattr(model, "_platt_scalers"):
        logging.error(
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

    logging.info("Loading trained checkpoint from: %s", ckpt_source)

    dcp_load_success = False
    try:
        from tzrec.utils.checkpoint_util import latest_checkpoint, restore_model

        ckpt_path, step = latest_checkpoint(ckpt_source)
        logging.info("DCP checkpoint: %s (step %d)", ckpt_path, step)
        restore_model(ckpt_path, model)
        dcp_load_success = True
    except Exception as exc:
        logging.warning("DCP restore failed (%s), trying torch.save fallback", exc)

    if not dcp_load_success:
        pt_files = ["model.pt", "model.pkl", "state_dict.pt"]
        found_pt = None
        for fname in pt_files:
            pt_files_list = os.path.join(ckpt_source, fname)
            if os.path.exists(pt_files_list):
                found_pt = pt_files_list
                break
        if found_pt:
            sd = torch.load(found_pt, map_location="cpu")
            model.load_state_dict(sd, strict=False)
            logging.info("Loaded from: %s", found_pt)
        else:
            raise FileNotFoundError(
                f"No checkpoint found at {args.trained_ckpt}. "
                "Expected DCP structure (meta + plan + model/) or .pt/.pkl file."
            )

    # === 3. Inject Platt params into model buffers ===
    logging.info("Injecting fitted Platt parameters...")
    for tower_name, params in tower_params.items():
        if tower_name not in model._platt_tower_to_scaler_idx:
            logging.warning("Tower '%s' not in platt index — skipping", tower_name)
            continue
        idx = model._platt_tower_to_scaler_idx[tower_name]
        scaler = model._platt_scalers[idx]

        # register_buffer replaces existing buffer values in-place
        scaler.register_buffer("_a", torch.tensor(params["a"]))
        scaler.register_buffer("_b", torch.tensor(params["b"]))
        scaler._frozen = True
        logging.info(
            "Injected %s: a=%.6f, b=%.6f", tower_name, params["a"], params["b"]
        )

    # === 4. Re-save patched state_dict as DCP format ===
    from torch.distributed.checkpoint import save as dcp_save

    patched_sd = model.state_dict()
    os.makedirs(args.output, exist_ok=True)
    dcp_model_file = os.path.join(args.output, "model")
    dcp_save(patched_sd, checkpoint_id=dcp_model_file)
    logging.info("Saved patched DCP checkpoint to: %s", args.output)

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

    logging.info("=" * 60)
    logging.info("Platt injection complete!")
    logging.info("  Patched DCP checkpoint: %s", args.output)
    logging.info("  Next: tzrec.export --checkpoint_path=%s", args.output)
    logging.info("=" * 60)


if __name__ == "__main__":
    main()
