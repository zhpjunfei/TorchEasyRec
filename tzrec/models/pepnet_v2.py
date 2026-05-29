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

from typing import Any, Dict, List, Optional, Tuple

import torch
from torch import nn

from tzrec.datasets.utils import Batch
from tzrec.features.feature import BaseFeature
from tzrec.models.multi_task_rank import MultiTaskRank
from tzrec.modules.cdot import CDOT
from tzrec.modules.interaction import CrossV2
from tzrec.modules.lhuc_net import LHUC_EPNet, LHUC_PPNet
from tzrec.protos.model_pb2 import ModelConfig
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


class PEPNet_v2(MultiTaskRank):
    """PEPNet_v2: Enhanced PEPNet with CDOT, Bias, LHUC-EPNet, LHUC-PPNet.

    Architecture improvements over PEPNet:
    - DCNv2 Cross Network: explicit feature crossing via CrossV2 on main features
    - CDOT: dynamic feature crossing via compressed transformation
    - Bias: per-feature 1-dim bias via first embedding element
    - Per-component LayerNorm before concatenation (matching TF)
    - LHUC-EPNet: tanh-based scaling (range [-4, 6]) for personalization
    - LHUC-PPNet: per-layer increasing tanh scale, scale-before-Dense (matching TF)
    - CVR logit-level addition with CTR logits
    - No hard domain splitting (soft personalization via LHUC)
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

        if self._model_config.HasField("dcnv2"):
            dcnv2_cfg = self._model_config.dcnv2
            self.cross_net = CrossV2(
                input_dim=self._main_group_dim,
                cross_num=dcnv2_cfg.cross_num,
                low_rank=dcnv2_cfg.low_rank,
            )
        else:
            self.cross_net = None

        if self.embedding_group.has_group(self._bias_group_name):
            self._bias_feature_dims = self.embedding_group.group_feature_dims(
                self._bias_group_name
            )
            self._num_bias_features = len(self._bias_feature_dims)
        else:
            self._bias_feature_dims = {}
            self._num_bias_features = 0

        self._cross_concat_dim = (
            self._main_group_dim if self.cross_net is not None else 0
        )
        deep_concat_dim = (
            self._main_group_dim
            + self._cross_concat_dim
            + self._cdot_concat_dim
            + self._num_bias_features
        )

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

        self._task_towers = nn.ModuleList()
        self._ctr_tower_name = None
        for tower_cfg in self._task_tower_cfgs:
            tower_kwargs = config_to_kwargs(tower_cfg)
            mlp_cfg = tower_kwargs.get("mlp", {"hidden_units": [512, 256, 128]})
            nn_dims = list(mlp_cfg.get("hidden_units", [512, 256, 128])) + [
                tower_cfg.num_class
            ]
            self._task_towers.append(
                LHUC_PPNet(
                    input_dim=deep_concat_dim,
                    lhuc_dim=self._lhuc_group_dim,
                    nn_dims=nn_dims,
                    nn_activation=ppnet_activation,
                    lhuc_hidden_units=ppnet_lhuc_hidden,
                )
            )
            tower_name = tower_cfg.tower_name
            if tower_name == "ctr":
                self._ctr_tower_name = tower_name

        self._cvr_add_ctr_logits = self._model_config.cvr_add_ctr_logits

    def _extract_bias(
        self, feature_tensors: List[torch.Tensor]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        return _extract_bias_fn(feature_tensors)

    def _extract_cdot(self, feature_tensors: List[torch.Tensor]) -> torch.Tensor:
        return _extract_cdot_fn(feature_tensors, self._cdot_input_dim)

    def predict(self, batch: Batch) -> Dict[str, torch.Tensor]:
        """Forward the model.

        Args:
            batch (Batch): input batch data.

        Return:
            predictions (dict): a dict of predicted result.
        """
        grouped_features = self.build_input(batch)

        main_features = grouped_features[self._main_group_name]

        main_feature_tensors = torch.split(
            main_features, self._main_feature_dim_list, dim=1
        )

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

        if self.cross_net is not None:
            cross_output = self.cross_net(main_features)

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
        deep_input = torch.cat(concat_parts, dim=1)

        if self.epnet is not None:
            lhuc_features = grouped_features[self._lhuc_group_name]
            ep_scale = self.epnet(lhuc_features)
            deep_input = deep_input * ep_scale

        tower_outputs = {}
        ctr_logits = None
        for i, task_tower_cfg in enumerate(self._task_tower_cfgs):
            tower_name = task_tower_cfg.tower_name
            tower_input = deep_input
            lhuc_input = lhuc_features if self.epnet is not None else deep_input
            tower_output = self._task_towers[i](tower_input, lhuc_input)

            if ctr_logits is not None and self._cvr_add_ctr_logits:
                tower_output = tower_output + ctr_logits
            else:
                tower_output = tower_output + bias_sum

            tower_outputs[tower_name] = tower_output

            if tower_name == self._ctr_tower_name:
                ctr_logits = tower_output

        return self._multi_task_output_to_prediction(tower_outputs)
