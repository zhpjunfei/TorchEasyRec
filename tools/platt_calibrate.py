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
  python tools/platt_calibrate.py \\
      --config v16_platt_calibration.config \\
      --checkpoint_dir ./output/train/model.ckpt-7300 \\
      --val_data_path odps://...

  # Step 3: 用 inject 脚本将 fitted params 注入 checkpoint 用于 export
  python tools/platt_inject_into_export.py \\
      --config pipeline.config \\
      --trained_ckpt ./output/train/model.ckpt-7300 \\
      --platt_meta ./output/platt_fitted/platt_meta.json \\
      --output ./output/injected_for_export/

  # Step 4: 正常导出
  torchrun -m tzrec.export \\
      --pipeline_config_path pipeline.config \\
      --checkpoint_path ./output/injected_for_export \\
      --export_dir ./output/export
"""

import argparse
import json
import logging
import os

import torch

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO
)


def collect_logits_and_labels(model, dataloader, device):
    """跑一遍验证集，收集每个塔的 (logits, labels)。"""
    all_data = {}
    for task_tower_cfg in model._task_tower_cfgs:
        tower_name = task_tower_cfg.tower_name
        label_key = task_tower_cfg.label_name
        all_data[tower_name] = {"logits": [], "labels": [], "label_key": label_key}

    model.eval()
    with torch.no_grad():
        for batch_idx, batch in enumerate(dataloader):
            batch = batch.to(device)
            output = model.predict(batch)

            for cfg in model._task_tower_cfgs:
                tn = cfg.tower_name
                logits_key = f"logits_{tn}"
                if logits_key in output and tn in all_data:
                    lgt = output[logits_key].cpu().float().squeeze(-1)
                    lab = batch.labels.get(cfg.label_key, torch.zeros_like(lgt)).float()
                    all_data[tn]["logits"].append(lgt)
                    all_data[tn]["labels"].append(lab)

            if (batch_idx + 1) % 500 == 0:
                logging.info("已收集 %d 个 batch...", batch_idx + 1)

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
    """拟合每个塔的 Platt 参数，直接写入模型的 buffer。"""
    from tzrec.modules.calibration import PlattScaler

    fitted = {}

    for tower_name, data in calibration_data.items():
        if tower_name not in model._platt_tower_to_scaler_idx:
            logging.warning("跳过 '%s': 未注册 platt scaler", tower_name)
            continue

        idx = model._platt_tower_to_scaler_idx[tower_name]
        scaler = model._platt_scalers[idx]

        # 直接拟合到已有的 scaler 上
        ps = PlattScaler(freeze=False)
        logits = data["logits"].to(device)
        labels = data["labels"].to(device)

        logging.info(
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

        logging.info(
            "  -> a=%.4f, b=%.4f, pos_rate=%.4f, n=%d (converged=%s)",
            result["a"],
            result["b"],
            result["pos_rate"],
            result["n_samples"],
            result["converged"],
        )

    return fitted


def save_fitted_params(fitted_params, output_dir):
    """保存 fitted 参数为 .pt 和 .json。"""
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
    logging.info("Saved to: %s", meta_file)
    return meta_file


def main():
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

    from tzrec.datasets.utils import DatasetFactory
    from tzrec.main import _create_features, init_model, parse_model_configs
    from tzrec.utils.checkpoint_util import latest_checkpoint, restore_model

    # Load config
    model_config, train_config, export_config = parse_model_configs(args.config)
    logging.info("Config loaded: %s", args.config)

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
    logging.info("Using checkpoint: %s", latest_ckpt)

    # Build validation dataset & dataloader
    dataset_factory = DatasetFactory.init_from_model_config(model_config, train_config)

    # Override validation input path
    val_input_backup = None
    if train_config.HasField("data_config"):
        if hasattr(train_config.data_config, "val_input_path"):
            val_input_backup = train_config.data_config.val_input_path
            train_config.data_config.val_input_path = args.val_data_path

    try:
        val_dataset = dataset_factory.build("eval")
        dataloader = torch.utils.data.DataLoader(
            val_dataset,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            shuffle=False,
            pin_memory=True,
        )

        # Create model
        features = _create_features(
            list(model_config.feature_configs), train_config.data_config
        )
        model, _ = init_model(model_config, train_config, export_config)
        device = torch.device(args.device)
        model = model.to(device)

        # Load trained checkpoint weights
        logging.info("Loading trained checkpoint...")
        ckpt_path, step = latest_checkpoint(latest_ckpt)
        logging.info("Restoring from %s (step %d)", ckpt_path, step)
        restore_model(ckpt_path, model)

        # Verify platt scalers exist
        if not hasattr(model, "_platt_scalers") or model._platt_scalers is None:
            logging.error(
                "Platt calib not enabled! Config must have "
                "platt_calibration_enabled: true"
            )
            return

        # Run inference on validation set
        logging.info("Running inference on validation data...")
        cal_data = collect_logits_and_labels(model, dataloader, device)
        for tn, d in cal_data.items():
            logging.info(
                "  %s: logits=%s, labels=%s", tn, d["logits"].shape, d["labels"].shape
            )

        # Fit Platt scalers and update model buffers
        logging.info("Fitting Platt parameters...")
        fitted = fit_and_update_model(model, cal_data, device)

        if not fitted:
            logging.error("No towers fitted!")
            return

        # Save fitted params
        meta_file = save_fitted_params(fitted, output_dir)

        logging.info("=" * 60)
        logging.info("Platt calibration complete!")
        logging.info("  Fitted %d tower(s):", len(fitted))
        for tn, p in fitted.items():
            logging.info("    %-6s: a=%.4f, b=%.4f", tn, p["a"], p["b"])
        logging.info("  Meta saved to: %s", meta_file)
        logging.info("  Next: run platt_inject_into_export.py with this meta")
        logging.info("=" * 60)

    finally:
        # Restore original data path
        if val_input_backup is not None:
            train_config.data_config.val_input_path = val_input_backup


if __name__ == "__main__":
    main()
