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

import math
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F
from torch import nn

from tzrec.datasets.utils import Batch
from tzrec.features.feature import BaseFeature
from tzrec.models.multi_task_rank import MultiTaskRank
from tzrec.modules.afp.afp_net import AFPModule
from tzrec.modules.calibration import (
    compute_soft_ece,
    create_temperature_scalers,
)
from tzrec.modules.cdot import CDOT
from tzrec.modules.extraction_net import ExtractionNet
from tzrec.modules.interaction import CrossV2
from tzrec.modules.lhuc_net import LHUC_EPNet, LHUC_PPNet
from tzrec.protos.model_pb2 import ModelConfig
from tzrec.protos.models import multi_task_rank_pb2
from tzrec.utils.config_util import config_to_kwargs


@torch.fx.wrap
def _extract_bias_fn(
    feature_tensors: List[torch.Tensor],
) -> Tuple[torch.Tensor, torch.Tensor]:
    bias_vec_list = []
    for ft in feature_tensors:
        bias_vec_list.append(ft[:, 0:1])
    bias_vec = torch.cat(bias_vec_list, dim=1)
    bias_sum = bias_vec.sum(dim=1, keepdim=True)
    return bias_vec, bias_sum


@torch.fx.wrap
def _extract_cdot_fn(
    feature_tensors: List[torch.Tensor], cdot_input_dim: int
) -> torch.Tensor:
    slots = []
    for ft in feature_tensors:
        if ft.size(1) >= cdot_input_dim:
            slots.append(ft[:, :cdot_input_dim])
        else:
            pad = torch.zeros(
                ft.size(0),
                cdot_input_dim - ft.size(1),
                device=ft.device,
            )
            slots.append(torch.cat([ft, pad], dim=1))
    return torch.stack(slots, dim=1)


class PEPNetDCNPLE(MultiTaskRank):
    """PEPNet + DCNv2 + PLE (ExtractionNet) fusion architecture.

    Architecture:
    - PEPNet frontend: DCNv2, CDOT, Bias, Component LN, EPNet(LHUC)
    - PLE middle: ExtractionNet layers with CGC routing
    - LHUC_PPNet towers: per-task personalization + final linear
    - CVR logit-level addition with CTR logits
    """

    def __init__(
        self,
        model_config: ModelConfig,
        features: List[BaseFeature],
        labels: List[str],
        sample_weights: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_config, features, labels, sample_weights, **kwargs)
        assert model_config.WhichOneof("model") == "pepnet_dcn_ple", (
            "invalid model config: %s" % self._model_config.WhichOneof("model")
        )
        assert isinstance(self._model_config, multi_task_rank_pb2.PEPNetDCNPLE)

        self.init_input()

        self._main_group_name = self._model_config.main_group_name
        self._lhuc_group_name = self._model_config.lhuc_group_name
        self._cdot_group_name = self._model_config.cdot_group_name
        self._bias_group_name = self._model_config.bias_group_name

        if not self.embedding_group.has_group(self._main_group_name):
            raise ValueError(f"main feature group [{self._main_group_name}] not found.")
        self._main_feature_dims = self.embedding_group.group_feature_dims(
            self._main_group_name
        )
        self._main_group_dim = sum(self._main_feature_dims.values())
        self._main_feature_dim_list = list(self._main_feature_dims.values())

        # --- CDOT ---
        if self.embedding_group.has_group(self._cdot_group_name):
            cdot_cfg = (
                self._model_config.cdot if self._model_config.HasField("cdot") else None
            )
            cdot_input_dim = cdot_cfg.input_dim if cdot_cfg else 16
            cdot_output_dim = cdot_cfg.output_dim if cdot_cfg else 4
            cdot_mid_dim = cdot_cfg.mid_dim if cdot_cfg else 32
            compress_hidden_units = (
                list(cdot_cfg.compress_hidden_units) if cdot_cfg else [512, 374]
            )
            cdot_feature_dims = self.embedding_group.group_feature_dims(
                self._cdot_group_name
            )
            self.cdot = CDOT(
                num_slots=len(cdot_feature_dims),
                input_dim=cdot_input_dim,
                output_dim=cdot_output_dim,
                mid_dim=cdot_mid_dim,
                compress_hidden_units=compress_hidden_units,
            )
            self._cdot_concat_dim = self.cdot.output_dim() * 2
            self._cdot_input_dim = cdot_input_dim
            self._cdot_output_dim = cdot_output_dim
        else:
            self.cdot = None
            self._cdot_concat_dim = 0
            self._cdot_input_dim = 0
            self._cdot_output_dim = 0

        # --- DCNv2 ---
        if self._model_config.HasField("dcnv2"):
            dcnv2_cfg = self._model_config.dcnv2
            self.cross_net = CrossV2(
                input_dim=self._main_group_dim,
                cross_num=dcnv2_cfg.cross_num,
                low_rank=dcnv2_cfg.low_rank,
            )
        else:
            self.cross_net = None

        # --- Bias ---
        if self.embedding_group.has_group(self._bias_group_name):
            self._bias_feature_dims = self.embedding_group.group_feature_dims(
                self._bias_group_name
            )
            self._num_bias_features = len(self._bias_feature_dims)
        else:
            self._bias_feature_dims = {}
            self._num_bias_features = 0

        # --- Tag Sequence Group (small expert for pooled behavior sequences) ---
        self._tag_seq_group_name = "tag_seq_group"
        if self.embedding_group.has_group(self._tag_seq_group_name):
            tag_seq_dims = self.embedding_group.group_total_dim(
                self._tag_seq_group_name
            )
            self._tag_seq_mlp = nn.Sequential(
                nn.Linear(tag_seq_dims, 128),
                nn.ReLU(),
                nn.Linear(128, 64),
            )
            self._tag_seq_output_dim = 64
        else:
            self._tag_seq_mlp = None
            self._tag_seq_output_dim = 0

        # --- Concat dimensions ---
        self._cross_concat_dim = (
            self._main_group_dim if self.cross_net is not None else 0
        )
        deep_concat_dim = (
            self._main_group_dim
            + self._cross_concat_dim
            + self._cdot_concat_dim
            + self._num_bias_features
            + self._tag_seq_output_dim
        )

        # --- Component LayerNorm ---
        self.component_ln = nn.ModuleDict()
        self.component_ln["main"] = nn.LayerNorm(self._main_group_dim)
        if self.cross_net is not None:
            self.component_ln["cross"] = nn.LayerNorm(self._main_group_dim)
        if self.cdot is not None:
            self.component_ln["allint_out"] = nn.LayerNorm(self.cdot.output_dim())
            if self._num_bias_features > 0:
                self.component_ln["bias"] = nn.LayerNorm(self._num_bias_features)
            self.component_ln["allint_mid"] = nn.LayerNorm(self.cdot.output_dim())
        elif self._num_bias_features > 0:
            self.component_ln["bias"] = nn.LayerNorm(self._num_bias_features)

        if self._tag_seq_output_dim > 0:
            self.component_ln["tag_seq"] = nn.LayerNorm(self._tag_seq_output_dim)

        # --- CVR Shortcut (linear bypass for conversion history features) ---
        self._cvr_shortcut_group_name = "cvr_shortcut"
        if self.embedding_group.has_group(self._cvr_shortcut_group_name):
            cvr_shortcut_dim = self.embedding_group.group_total_dim(
                self._cvr_shortcut_group_name
            )
            self._cvr_shortcut_mlp = nn.Sequential(
                nn.Linear(cvr_shortcut_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 1),
            )
        else:
            self._cvr_shortcut_mlp = None

        # --- EPNet (LHUC) ---
        if self.embedding_group.has_group(self._lhuc_group_name):
            self._lhuc_group_dim = self.embedding_group.group_total_dim(
                self._lhuc_group_name
            )
            epnet_hidden = (
                self._model_config.epnet_hidden_unit
                if self._model_config.HasField("epnet_hidden_unit")
                else 256
            )
            self.epnet = LHUC_EPNet(
                lhuc_dim=self._lhuc_group_dim,
                output_dim=deep_concat_dim,
                hidden_units=[epnet_hidden],
            )
        else:
            self._lhuc_group_dim = 0
            self.epnet = None
        # --- AFP (Automatic Feature Partitioning) ---
        self._afp_enabled = self._model_config.afp_enabled
        if self._afp_enabled and self.embedding_group.has_group(self._lhuc_group_name):
            self._afp_mode = (
                self._model_config.afp_mode
                if self._model_config.afp_mode
                else "feature_wise"
            )
            self._afp_hidden_units = (
                list(self._model_config.afp_hidden_units)
                if self._model_config.afp_hidden_units
                else [64, 32]
            )
            self._afp_temperature = (
                self._model_config.afp_temperature
                if self._model_config.HasField("afp_temperature")
                else 1.0
            )
            self._afp_min_temperature = (
                self._model_config.afp_min_temperature
                if self._model_config.HasField("afp_min_temperature")
                else 0.1
            )
            self._afp_gate_temperature = (
                self._model_config.afp_gate_temperature
                if self._model_config.HasField("afp_gate_temperature")
                else 0.0
            )
            # Build feature dims list for AFP (order matches lhuc group)
            self._afp_feature_dims = list(
                self.embedding_group.group_feature_dims(self._lhuc_group_name).values()
            )
            self.afp_module = AFPModule(
                feature_dims=self._afp_feature_dims,
                mode=self._afp_mode,
                hidden_units=self._afp_hidden_units,
                temperature=self._afp_temperature,
                min_temperature=self._afp_min_temperature,
                gate_temperature=self._afp_gate_temperature,
            )
        else:
            self.afp_module = None

        # --- PLE ExtractionNet layers ---
        self._extraction_nets = nn.ModuleList()
        in_extraction_networks = [deep_concat_dim] * len(self._task_tower_cfgs)
        in_shared_expert = deep_concat_dim
        for i, extraction_network_cfg in enumerate(
            self._model_config.extraction_networks
        ):
            if i == len(self._model_config.extraction_networks) - 1:
                final_flag = True
            else:
                final_flag = False
            extraction_network_cfg = config_to_kwargs(extraction_network_cfg)
            extraction = ExtractionNet(
                in_extraction_networks,
                in_shared_expert,
                final_flag=final_flag,
                **extraction_network_cfg,
            )
            self._extraction_nets.append(extraction)
            output_dims = extraction.output_dim()
            in_extraction_networks = output_dims[:-1]
            in_shared_expert = output_dims[-1]

        # --- Task towers (LHUC_PPNet + final) ---
        last_output_dims = self._extraction_nets[-1].output_dim()
        task_output_dims = last_output_dims[:-1]
        self._task_towers = nn.ModuleList()
        self._tower_final = nn.ModuleDict()
        self._ctr_tower_name = None

        ppnet_activation = (
            self._model_config.ppnet_activation
            if self._model_config.HasField("ppnet_activation")
            else "nn.ReLU"
        )
        ppnet_lhuc_hidden = (
            [self._model_config.ppnet_hidden_units[0]]
            if self._model_config.ppnet_hidden_units
            else [256]
        )

        self._tower_hidden_dims = {}
        for tower_idx, tower_cfg in enumerate(self._task_tower_cfgs):
            tower_kwargs = config_to_kwargs(tower_cfg)
            mlp_cfg = tower_kwargs.get("mlp", {"hidden_units": [256, 128, 64]})
            hidden_units = list(mlp_cfg.get("hidden_units", [256, 128, 64]))
            dropout_ratio = mlp_cfg.get("dropout_ratio", [0.0])
            if isinstance(dropout_ratio, (list, tuple)):
                dropout_ratio = float(dropout_ratio[0]) if dropout_ratio else 0.0
            else:
                dropout_ratio = float(dropout_ratio)
            self._task_towers.append(
                LHUC_PPNet(
                    input_dim=task_output_dims[tower_idx],
                    lhuc_dim=self._lhuc_group_dim,
                    nn_dims=hidden_units,
                    nn_activation=ppnet_activation,
                    lhuc_hidden_units=ppnet_lhuc_hidden,
                    dropout_ratio=dropout_ratio,
                )
            )
            tower_name = tower_cfg.tower_name
            if tower_name == "ctr":
                self._ctr_tower_name = tower_name
            self._tower_hidden_dims[tower_name] = (
                hidden_units[-1] if hidden_units else task_output_dims[tower_idx]
            )

        for tower_cfg in self._task_tower_cfgs:
            tower_name = tower_cfg.tower_name
            self._tower_final[tower_name] = nn.Linear(
                self._tower_hidden_dims[tower_name], tower_cfg.num_class
            )

        self._cvr_tower_names = [
            n for n in self._tower_hidden_dims if n != self._ctr_tower_name
        ]

        # --- CVR Direct Highway (bypass EPNet→PLE→PPNet) ---
        # Mode ADD: residual to tower_hidden, uses same final Linear as tower
        self._cvr_direct_group_name = "cvr_direct"
        if self.embedding_group.has_group(self._cvr_direct_group_name):
            cvr_direct_dim = self.embedding_group.group_total_dim(
                self._cvr_direct_group_name
            )
            cvr_direct_target_dim = None
            for n, d in self._tower_hidden_dims.items():
                if n != self._ctr_tower_name:
                    cvr_direct_target_dim = d
                    break
            if cvr_direct_target_dim is not None:
                self._cvr_direct_proj = nn.Linear(cvr_direct_dim, cvr_direct_target_dim)
            else:
                self._cvr_direct_proj = None
        else:
            self._cvr_direct_proj = None

        # Mode CONCAT: separate projection + final head, logit-level addition
        self._cvr_direct_concat_group_name = "cvr_direct_concat"
        if self.embedding_group.has_group(self._cvr_direct_concat_group_name):
            cvr_direct_concat_dim = self.embedding_group.group_total_dim(
                self._cvr_direct_concat_group_name
            )
            self._cvr_direct_concat_proj = nn.Sequential(
                nn.Linear(cvr_direct_concat_dim, 64), nn.ReLU()
            )
            self._cvr_direct_concat_final = nn.ModuleDict()
            for tower_name in self._cvr_tower_names:
                self._cvr_direct_concat_final[tower_name] = nn.Linear(64, 1)
        else:
            self._cvr_direct_concat_proj = None
            self._cvr_direct_concat_final = nn.ModuleDict()

        self._cvr_add_ctr_logits = self._model_config.cvr_add_ctr_logits
        self._isolate_cvr_gradient = self._base_model_config.isolate_cvr_gradient

        # --- Contrastive Learning ---
        self._contrastive_loss_weight = 0.1
        self._contrastive_loss_enabled = self._model_config.contrastive_loss_enabled
        self._contrastive_logq_theta = 0.01
        self._contrastive_metrics = {}

        # alignment mode: "column" (Phase 1a), "bidirectional" (Phase 2),
        # "row" (reserved)
        self._contrastive_alignment_mode = (
            self._model_config.contrastive_alignment_mode
            if self._contrastive_loss_enabled
            else "column"
        )

        self._contrastive_din_output_dim = None
        group_seq_encoders = getattr(
            self.embedding_group, "_group_name_to_seq_encoders", {}
        )
        if "all" in group_seq_encoders:
            for seq_encoder in group_seq_encoders["all"]:
                if seq_encoder.input() == "click_50_seq":
                    self._contrastive_din_output_dim = seq_encoder.output_dim()
                    break
        if self._contrastive_din_output_dim:
            self.contrastive_behavior_proj = nn.Linear(
                self._contrastive_din_output_dim, 128
            )
        else:
            self.contrastive_behavior_proj = None
        self.default_behavior = nn.Parameter(torch.zeros(128))

        self._title_vector_idx = None
        self._title_vector_dim = None
        # title_vector is now in a separate "contrastive" feature group
        # to prevent it from leaking into the PEPNet tower
        cg = getattr(self.embedding_group, "_group_feature_dims", {})
        if "contrastive" in cg and "title_vector" in cg["contrastive"]:
            self._title_vector_dim = cg["contrastive"]["title_vector"]

        self._item_id_num_emb = None
        for f in self._features:
            if f.name == "item_id" and hasattr(f, "num_embeddings"):
                self._item_id_num_emb = f.num_embeddings
                break
        if self._item_id_num_emb:
            self.register_buffer(
                "_log_q",
                torch.full([self._item_id_num_emb], -math.log(self._item_id_num_emb)),
            )
        else:
            self.register_buffer("_log_q", None)

        # --- Phase 2: residual title adapter (only in bidirectional/row modes) ---
        if self._contrastive_alignment_mode in ("bidirectional", "row"):
            self.contrastive_title_adapter = nn.Sequential(
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Linear(64, 128),
            )
            nn.init.zeros_(self.contrastive_title_adapter[2].weight)
            nn.init.zeros_(self.contrastive_title_adapter[2].bias)
        else:
            self.contrastive_title_adapter = None

        # --- Temperature Calibration (CaliCausalRank-inspired) ---
        self._use_calibration = self._base_model_config.use_calibration
        self._calibration_loss_weight = (
            self._base_model_config.calibration_loss_weight
            if self._base_model_config.HasField("calibration_loss_weight")
            else 0.0
        )
        # TODO: _calibration_target_ece 预留用于 target-ECE 正则化
        # 当前实现使用 ECE 绝对值作为损失，target_ece 可在未来用于
        # 构建 (ece - target)^2 形式的正则化项
        self._calibration_target_ece = (
            self._base_model_config.calibration_target_ece
            if self._base_model_config.HasField("calibration_target_ece")
            else 0.05
        )

        # Per-task calibration: model-level + task-level override
        self._task_calib_enabled = (
            self._model_config.task_calibration_enabled
            if self._use_calibration
            else False
        )
        self._initial_temperature = (
            self._model_config.initial_temperature
            if self._model_config.HasField("initial_temperature")
            else 1.0
        )
        self._freeze_temperature = self._model_config.freeze_temperature

        if self._task_calib_enabled:
            num_tasks = len(self._task_tower_cfgs)
            self._temperature_scalers = create_temperature_scalers(
                num_tasks=num_tasks,
                initial_temp=self._initial_temperature,
                freeze=self._freeze_temperature,
            )
            # Map tower_name -> scaler index
            self._tower_to_scaler_idx = {
                cfg.tower_name: idx for idx, cfg in enumerate(self._task_tower_cfgs)
            }
        else:
            self._temperature_scalers = None
            self._tower_to_scaler_idx = {}
        self._calibration_metrics = {}

    def _extract_bias(
        self, feature_tensors: List[torch.Tensor]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        return _extract_bias_fn(feature_tensors)

    def _extract_cdot(self, feature_tensors: List[torch.Tensor]) -> torch.Tensor:
        return _extract_cdot_fn(feature_tensors, self._cdot_input_dim)

    def predict(self, batch: Batch) -> Dict[str, torch.Tensor]:
        """Forward the model."""
        grouped_features = self.build_input(batch)

        main_features = grouped_features[self._main_group_name]
        main_feature_tensors = torch.split(
            main_features, self._main_feature_dim_list, dim=1
        )

        # --- Bias ---
        bias_vec = torch.empty(0)
        if self._num_bias_features > 0:
            if self._bias_group_name == self._main_group_name:
                bias_feature_tensors = main_feature_tensors
            else:
                bias_features = grouped_features[self._bias_group_name]
                bias_feature_dim_list = list(
                    self.embedding_group.group_feature_dims(
                        self._bias_group_name
                    ).values()
                )
                bias_feature_tensors = torch.split(
                    bias_features, bias_feature_dim_list, dim=1
                )
            bias_vec, bias_sum = self._extract_bias(bias_feature_tensors)
        else:
            bias_sum = torch.zeros(
                main_features.size(0), 1, device=main_features.device
            )

        # --- DCNv2 ---
        if self.cross_net is not None:
            cross_output = self.cross_net(main_features)

        # --- CDOT ---
        if self.cdot is not None:
            if self._cdot_group_name == self._main_group_name:
                cdot_feature_tensors = main_feature_tensors
            else:
                cdot_features = grouped_features[self._cdot_group_name]
                cdot_feature_dim_list = list(
                    self.embedding_group.group_feature_dims(
                        self._cdot_group_name
                    ).values()
                )
                cdot_feature_tensors = torch.split(
                    cdot_features, cdot_feature_dim_list, dim=1
                )
            cdot_input = self._extract_cdot(cdot_feature_tensors)
            allint_out, allint_mid_out = self.cdot(cdot_input)

        # --- Tag Sequence Group (small expert) ---
        if self._tag_seq_mlp is not None:
            tag_seq_out = self._tag_seq_mlp(grouped_features[self._tag_seq_group_name])

        # --- CVR Shortcut ---
        if self._cvr_shortcut_mlp is not None:
            cvr_shortcut_logit = self._cvr_shortcut_mlp(
                grouped_features[self._cvr_shortcut_group_name]
            )

        # --- Concat ---
        concat_parts = []
        concat_parts.append(self.component_ln["main"](main_features))
        if self.cross_net is not None:
            concat_parts.append(self.component_ln["cross"](cross_output))
        if self.cdot is not None:
            concat_parts.append(self.component_ln["allint_out"](allint_out))
            if self._num_bias_features > 0:
                concat_parts.append(self.component_ln["bias"](bias_vec))
            concat_parts.append(self.component_ln["allint_mid"](allint_mid_out))
        elif self._num_bias_features > 0:
            concat_parts.append(self.component_ln["bias"](bias_vec))
        if self._tag_seq_output_dim > 0:
            concat_parts.append(self.component_ln["tag_seq"](tag_seq_out))
        deep_input = torch.cat(concat_parts, dim=1)

        # --- AFP partitioning (before EPNet) ---
        gate_input_for_ppnet = None
        if self._afp_enabled and self.afp_module is not None:
            lhuc_features = grouped_features[self._lhuc_group_name]
            afp_result = self.afp_module(lhuc_features, hard_selection=False)
            gate_input_for_ppnet = afp_result["gate_input"]
            dnn_input_for_epnet = afp_result["dnn_input"]
        else:
            dnn_input_for_epnet = None  # will use raw lhuc_features below

        # --- EPNet (LHUC) personalization with AFP partitioning ---
        if self.epnet is not None:
            if self._afp_enabled and gate_input_for_ppnet is not None:
                ep_scale = self.epnet(dnn_input_for_epnet)
            else:
                lhuc_features = grouped_features[self._lhuc_group_name]
                ep_scale = self.epnet(lhuc_features)
            deep_input = deep_input * ep_scale

        # Ensure gate_input_for_ppnet falls back to lhuc_features when AFP is disabled
        if gate_input_for_ppnet is None:
            gate_input_for_ppnet = grouped_features[self._lhuc_group_name]

        # --- PLE ExtractionNet layers ---
        extraction_network_fea = [deep_input] * len(self._task_tower_cfgs)
        shared_expert_fea = deep_input
        for extraction_net in self._extraction_nets:
            extraction_network_fea, shared_expert_fea = extraction_net(
                extraction_network_fea, shared_expert_fea
            )

        # --- LHUC_PPNet towers ---
        lhuc_input = gate_input_for_ppnet
        tower_hidden = {}
        for i, task_tower_cfg in enumerate(self._task_tower_cfgs):
            tower_name = task_tower_cfg.tower_name
            fea = extraction_network_fea[i]
            if self._isolate_cvr_gradient and tower_name != self._ctr_tower_name:
                fea = fea.detach()
            tower_hidden[tower_name] = self._task_towers[i](fea, lhuc_input)

        # --- CVR Direct Highway ---
        # (residual to tower hidden, bypassing EPNet→PLE→PPNet)
        if self._cvr_direct_proj is not None:
            direct_hidden = self._cvr_direct_proj(
                grouped_features[self._cvr_direct_group_name]
            )
            for tower_name in self._cvr_tower_names:
                tower_hidden[tower_name] = tower_hidden[tower_name] + direct_hidden

        # --- Final logits with cvr_add_ctr_logits ---
        tower_outputs = {}
        ctr_logits_val = None
        for task_tower_cfg in self._task_tower_cfgs:
            tower_name = task_tower_cfg.tower_name
            tower_output = self._tower_final[tower_name](tower_hidden[tower_name])

            if ctr_logits_val is not None and self._cvr_add_ctr_logits:
                tower_output = tower_output + ctr_logits_val
            else:
                tower_output = tower_output + bias_sum

            tower_outputs[tower_name] = tower_output

            if tower_name == self._ctr_tower_name:
                ctr_logits_val = tower_output

        # --- CVR Shortcut addition (non-CTR towers only) ---
        if self._cvr_shortcut_mlp is not None:
            for tower_name in tower_outputs:
                if tower_name != self._ctr_tower_name:
                    tower_outputs[tower_name] = (
                        tower_outputs[tower_name] + cvr_shortcut_logit
                    )

        # --- CVR Direct Highway CONCAT mode ---
        # (separate head, logit-level addition)
        if self._cvr_direct_concat_proj is not None:
            direct_concat_hidden = self._cvr_direct_concat_proj(
                grouped_features[self._cvr_direct_concat_group_name]
            )
            for tower_name in self._cvr_tower_names:
                tower_outputs[tower_name] = tower_outputs[
                    tower_name
                ] + self._cvr_direct_concat_final[tower_name](direct_concat_hidden)

        # --- Temperature Calibration (apply to tower outputs) ---
        if self._task_calib_enabled and self._temperature_scalers is not None:
            for tower_name, tower_output in tower_outputs.items():
                if tower_name in self._tower_to_scaler_idx:
                    scaler = self._temperature_scalers[
                        self._tower_to_scaler_idx[tower_name]
                    ]
                    tower_outputs[tower_name] = scaler(tower_output)

        predictions = self._multi_task_output_to_prediction(tower_outputs)

        # Expose calibration metrics for logging (training only)
        if self.training and self._temperature_scalers is not None:
            temps = []
            for tower_name in self._tower_to_scaler_idx:
                idx = self._tower_to_scaler_idx[tower_name]
                t = self._temperature_scalers[idx].get_temperature()
                temps.append(f"{tower_name}={t.item():.4f}")
            predictions["_calibration_temps"] = "; ".join(temps)

        if (
            self.training
            and self._contrastive_loss_enabled
            and self.contrastive_behavior_proj is not None
        ):
            behavior_emb = grouped_features.get("all__seq_output__click_50_seq")
            if behavior_emb is not None and self._title_vector_dim is not None:
                v = self.contrastive_behavior_proj(behavior_emb)
                # Get title_vector from the "contrastive" feature group
                # (not from the main "all" group, to prevent PEPNet from using it)
                tv_group = grouped_features.get("contrastive")
                if tv_group is None:
                    return predictions
                t_raw = tv_group[:, : self._title_vector_dim]
                seq_len = grouped_features["click_50_seq.sequence_length"]
                v = torch.where(
                    (seq_len > 0).unsqueeze(1),
                    v,
                    self.default_behavior.unsqueeze(0).expand_as(v),
                )
                if self._contrastive_alignment_mode in ("bidirectional", "row"):
                    t = t_raw + self.contrastive_title_adapter(t_raw)
                else:
                    t = t_raw
                predictions["_ctr_behavior"] = v
                predictions["_ctr_title"] = t
                predictions["_ctr_seq_len"] = seq_len

        return predictions

    def anneal_temperature(self, step: int, total_steps: int) -> None:
        """Anneal AFP temperature during training. Call from trainer loop."""
        if self._afp_enabled and self.afp_module is not None:
            self.afp_module.anneal_temperature(step, total_steps)

    def loss(
        self, predictions: Dict[str, torch.Tensor], batch: Batch
    ) -> Dict[str, torch.Tensor]:
        """Compute contrastive loss in addition to base task losses."""
        losses = super().loss(predictions, batch)

        # --- Calibration Loss (CaliCausalRank-inspired) ---
        if (
            self._task_calib_enabled
            and self._temperature_scalers is not None
            and self._calibration_loss_weight > 0
        ):
            calib_losses = []
            calib_temps = []
            for task_tower_cfg in self._task_tower_cfgs:
                tower_name = task_tower_cfg.tower_name
                if tower_name not in self._tower_to_scaler_idx:
                    continue
                scaler = self._temperature_scalers[
                    self._tower_to_scaler_idx[tower_name]
                ]
                temp = scaler.get_temperature()
                calib_temps.append(f"{tower_name}:{temp.item():.4f}")
                # Get probs and labels for this task
                probs_key = f"probs_{tower_name}"
                label_key = task_tower_cfg.label_name
                if probs_key not in predictions or label_key not in batch.labels:
                    continue
                task_probs = predictions[probs_key]
                task_labels = batch.labels[label_key]
                task_weight = None
                if task_tower_cfg.HasField("sample_weight_name"):
                    sw_name = task_tower_cfg.sample_weight_name
                    if sw_name in batch.sample_weights:
                        task_weight = batch.sample_weights[sw_name]
                ece = compute_soft_ece(task_probs, task_labels, task_weight)
                calib_losses.append(ece)

            if calib_losses:
                total_calib_loss = sum(calib_losses) / len(calib_losses)
                losses["calibration_loss"] = (
                    total_calib_loss * self._calibration_loss_weight
                )
                self._calibration_metrics["calib_loss"] = total_calib_loss.item()
                self._calibration_metrics["temperatures"] = "; ".join(calib_temps)

        if self._contrastive_loss_enabled and "_ctr_behavior" in predictions:
            v = predictions["_ctr_behavior"]
            if isinstance(v, torch.fx.Proxy):
                return losses
            t = predictions["_ctr_title"]
            seq_len = predictions["_ctr_seq_len"]
            B = v.size(0)

            if self._log_q is not None:
                kjt = batch.sparse_features.get("__BASE__")
                if kjt is not None and "item_id_emb" in kjt.keys():
                    item_ids = kjt["item_id_emb"].values().long()
                    freq = torch.bincount(
                        item_ids, minlength=self._item_id_num_emb
                    ).float()
                    batch_freq = freq / freq.sum()
                    self._log_q.mul_(1 - self._contrastive_logq_theta).add_(
                        self._contrastive_logq_theta, torch.log(batch_freq + 1e-8)
                    )

            v = F.normalize(v, dim=-1)
            t = F.normalize(t, dim=-1)

            # ── Mode-specific contrastive loss ──
            if self._contrastive_alignment_mode == "column":
                # Phase 1a: single-side column alignment (existing behavior)
                K = min(150, B - 1)
                raw_sim = torch.mm(v, t.t())

                # v2t: per-seq_len τ + LogQ + HardNegative
                tau = (0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())).unsqueeze(1)
                sim_v2t = raw_sim / tau
                sim_c = sim_v2t.clone()
                if (
                    self._log_q is not None
                    and kjt is not None
                    and "item_id_emb" in kjt.keys()
                ):
                    logq = self._log_q[item_ids].to(sim_v2t.device)
                    sim_c = sim_c - logq.unsqueeze(0)

                _, topk = torch.topk(sim_c, K + 1, dim=-1)
                hard_mask = torch.zeros_like(sim_c, dtype=torch.bool)
                hard_mask[torch.arange(B, device=v.device).unsqueeze(1), topk] = True
                hard_mask[
                    torch.arange(B, device=v.device), torch.arange(B, device=v.device)
                ] = True
                loss_v2t = -sim_c.diag() + torch.logsumexp(
                    sim_c.masked_fill(~hard_mask, -float("inf")), dim=-1
                )

                # t2v: fixed τ + HardNegative (column direction, no LogQ)
                sim_t2v = raw_sim / 0.07
                _, topk_t2v = torch.topk(sim_t2v, K + 1, dim=0)
                hard_mask_t2v = torch.zeros_like(sim_t2v, dtype=torch.bool)
                hard_mask_t2v[
                    topk_t2v,
                    torch.arange(B, device=v.device).unsqueeze(0).expand(K + 1, -1),
                ] = True
                hard_mask_t2v[
                    torch.arange(B, device=v.device), torch.arange(B, device=v.device)
                ] = True
                loss_t2v = -sim_t2v.diag() + torch.logsumexp(
                    sim_t2v.masked_fill(~hard_mask_t2v, -float("inf")), dim=0
                )

                loss_contrast = (loss_v2t + loss_t2v) / 2

                with torch.no_grad():
                    align = (v * t).sum(-1).mean().item()
                    neg_mask = ~hard_mask & ~torch.eye(
                        B, dtype=torch.bool, device=v.device
                    )
                    uniformity = (
                        sim_v2t[neg_mask].exp().mean().log().item()
                        if neg_mask.sum() > B
                        else 0.0
                    )
                    self._contrastive_metrics.update(
                        {"ctr_align": align, "ctr_uniform": uniformity}
                    )

            elif self._contrastive_alignment_mode == "bidirectional":
                # Phase 2: bidirectional row+column alignment
                # (residual adapter + detach)
                K = min(50, B - 1)
                tau_v2t = (0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())).unsqueeze(1)
                tau_t2v = (0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())).unsqueeze(0)

                # v2t: title anchors, behavior queries → only behavior_proj gets grad
                sim_v2t = torch.mm(v, t.detach().t()) / tau_v2t
                sim_c = sim_v2t.clone()
                if (
                    self._log_q is not None
                    and kjt is not None
                    and "item_id_emb" in kjt.keys()
                ):
                    logq = self._log_q[item_ids].to(sim_v2t.device)
                    sim_c = sim_c - logq.unsqueeze(0)

                _, topk = torch.topk(sim_c, K + 1, dim=-1)
                hard_mask = torch.zeros_like(sim_c, dtype=torch.bool)
                hard_mask[torch.arange(B, device=v.device).unsqueeze(1), topk] = True
                hard_mask[
                    torch.arange(B, device=v.device), torch.arange(B, device=v.device)
                ] = True
                loss_v2t = -sim_c.diag() + torch.logsumexp(
                    sim_c.masked_fill(~hard_mask, -float("inf")), dim=-1
                )

                # t2v: behavior anchors, title queries → only title_adapter gets grad
                sim_t2v = torch.mm(v.detach(), t.t()) / tau_t2v
                _, topk_t2v = torch.topk(sim_t2v, K + 1, dim=0)
                hard_mask_t2v = torch.zeros_like(sim_t2v, dtype=torch.bool)
                hard_mask_t2v[
                    topk_t2v,
                    torch.arange(B, device=v.device).unsqueeze(0).expand(K + 1, -1),
                ] = True
                hard_mask_t2v[
                    torch.arange(B, device=v.device), torch.arange(B, device=v.device)
                ] = True
                loss_t2v = -sim_t2v.diag() + torch.logsumexp(
                    sim_t2v.masked_fill(~hard_mask_t2v, -float("inf")), dim=0
                )

                loss_contrast = (loss_v2t + loss_t2v) / 2

                with torch.no_grad():
                    align = (v * t).sum(-1).mean().item()
                    neg_mask = ~hard_mask & ~torch.eye(
                        B, dtype=torch.bool, device=v.device
                    )
                    uniformity = (
                        sim_v2t[neg_mask].exp().mean().log().item()
                        if neg_mask.sum() > B
                        else 0.0
                    )
                    self._contrastive_metrics.update(
                        {"ctr_align": align, "ctr_uniform": uniformity}
                    )

            else:
                # "row" mode: reserved stub
                loss_contrast = v.new_zeros(B)
                loss_v2t = v.new_zeros(B)
                loss_t2v = v.new_zeros(B)

            mask = (seq_len >= 0).float()
            if mask.sum() > 0:
                losses["contrastive_loss"] = (
                    (loss_contrast * mask).sum()
                    / mask.sum()
                    * self._contrastive_loss_weight
                )
                losses["contrastive_v2t_loss"] = (
                    (loss_v2t * mask).sum() / mask.sum() * self._contrastive_loss_weight
                )
                losses["contrastive_t2v_loss"] = (
                    (loss_t2v * mask).sum() / mask.sum() * self._contrastive_loss_weight
                )

        return losses
