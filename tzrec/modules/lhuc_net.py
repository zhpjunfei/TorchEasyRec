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

import pydoc
from typing import List, Optional

import torch
from torch import nn


class LHUC_EPNet(nn.Module):
    """LHUC-based Embedding Personalization Network.

    Generates element-wise scaling factors for the deep features.
    Scale = tanh(x * 0.2) * 5.0 + 1.0

    TF equivalent: lhuc_ep_net in lhuc_net.py

    Args:
        lhuc_dim: dimension of LHUC input features
        output_dim: dimension to scale
        hidden_units: hidden units for the gate MLP
    """

    def __init__(
        self,
        lhuc_dim: int,
        output_dim: int,
        hidden_units: Optional[List[int]] = None,
    ) -> None:
        super().__init__()
        if hidden_units is None:
            hidden_units = [256]
        self._output_dim = output_dim

        units = list(hidden_units) + [output_dim]
        layers = []
        prev = lhuc_dim
        for h in units:
            layers.append(nn.Linear(prev, h))
            if h != output_dim:
                layers.append(nn.ReLU())
            prev = h
        self.gate = nn.Sequential(*layers)

    def output_dim(self) -> int:
        """Get output dimension."""
        return self._output_dim

    def forward(self, lhuc_input: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            lhuc_input: [B, lhuc_dim]

        Returns:
            scale: [B, output_dim] element-wise scaling factors
        """
        gate = self.gate(lhuc_input)
        scale = torch.tanh(gate * 0.2) * 5.0 + 1.0
        return scale


class LHUC_PPNet(nn.Module):
    """LHUC-based Parameter Personalization Network.

    Per-layer element-wise scaling with increasing scale factor per layer.
    Scale[idx] = tanh(x * 0.2) * (5.0 + idx) + 1.0

    Matches TF lhuc_pp_net in lhuc_net.py:
    - gate output dim = current layer INPUT dim (not target nn_dim)
    - scaling applied BEFORE Dense layer
    - gate dim changes each iteration to match current layer dim

    Args:
        input_dim: input dimension of the tower
        lhuc_dim: dimension of LHUC input features
        nn_dims: list of hidden unit sizes for each layer
        nn_activation: activation function for the tower layers
        lhuc_hidden_units: hidden units for LHUC gate MLP
    """

    def __init__(
        self,
        input_dim: int,
        lhuc_dim: int,
        nn_dims: List[int],
        nn_activation: str = "nn.ReLU",
        lhuc_hidden_units: Optional[List[int]] = None,
    ) -> None:
        super().__init__()
        if lhuc_hidden_units is None:
            lhuc_hidden_units = [256]
        self.nn_dims = nn_dims
        self.num_layers = len(nn_dims)

        self.tower_layers = nn.ModuleList()
        self.gate_mlps = nn.ModuleList()

        cur_dim = input_dim
        for idx, nn_dim in enumerate(nn_dims):
            gate_units = list(lhuc_hidden_units) + [cur_dim]
            gate_layers = []
            gprev = lhuc_dim
            for h in gate_units:
                gate_layers.append(nn.Linear(gprev, h))
                if h != cur_dim:
                    gate_layers.append(nn.ReLU())
                gprev = h
            self.gate_mlps.append(nn.Sequential(*gate_layers))

            self.tower_layers.append(nn.Linear(cur_dim, nn_dim))
            cur_dim = nn_dim

        act_str = nn_activation.strip()
        if act_str:
            act_parts = act_str.strip(")").split("(", 1)
            act_cls_path = act_parts[0]
            if act_cls_path.startswith("nn."):
                act_cls_path = "torch." + act_cls_path
            act_cls = pydoc.locate(act_cls_path)
            self.activation = act_cls() if act_cls else nn.Identity()
        else:
            self.activation = nn.Identity()

    def output_dim(self) -> int:
        """Get output dimension."""
        return self.nn_dims[-1]

    def forward(
        self, x: torch.Tensor, lhuc_inputs: torch.Tensor
    ) -> torch.Tensor:
        """Forward pass for LHUC PPNet.

        Matches TF order: scale → Dense → activation

        Args:
            x: input tensor [B, input_dim]
            lhuc_inputs: LHUC input tensor [B, lhuc_dim]

        Returns:
            output tensor [B, nn_dims[-1]]
        """
        for idx in range(self.num_layers):
            gate = self.gate_mlps[idx](lhuc_inputs)
            scale = torch.tanh(gate * 0.2) * (5.0 + idx) + 1.0

            x = x * scale
            x = self.tower_layers[idx](x)
            if idx < self.num_layers - 1:
                x = self.activation(x)
        return x
