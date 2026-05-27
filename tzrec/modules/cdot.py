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

from typing import List, Tuple

import torch
from torch import nn


class CDOT(nn.Module):
    """Compress Dynamic feature cOllaborative Transformation (CDOT).

    Generates dynamic compress weights from all feature slots and produces
    feature interaction via tensor product transformation.

    Matches the TF implementation:
    - sub_compress: single linear weight [num_slots, mid_dim] applied to transposed input
    - compress_mlp: MLP on sub_compress output only (not concat with raw flatten)
    - separate learnable compress_bias

    Args:
        num_slots: number of feature slots
        input_dim: per-slot feature dimension
        output_dim: per-slot output dimension
        mid_dim: compressed mid dimension
        compress_hidden_units: hidden units for compress weight MLP
    """

    def __init__(
        self,
        num_slots: int,
        input_dim: int = 16,
        output_dim: int = 4,
        mid_dim: int = 32,
        compress_hidden_units: List[int] = (512, 374),
    ) -> None:
        super().__init__()
        self.num_slots = num_slots
        self.input_dim = input_dim
        self._output_dim = output_dim
        self.mid_dim = mid_dim

        self.sub_compress_weight = nn.Parameter(
            torch.empty(num_slots, mid_dim)
        )
        nn.init.xavier_uniform_(self.sub_compress_weight)

        compress_layers = []
        prev = input_dim * mid_dim
        for h in compress_hidden_units:
            compress_layers.append(nn.Linear(prev, h))
            compress_layers.append(nn.ReLU())
            prev = h
        compress_layers.append(nn.Linear(prev, num_slots * output_dim))
        self.compress_mlp = nn.Sequential(*compress_layers)

        self.compress_bias = nn.Parameter(
            torch.zeros(1, input_dim, output_dim)
        )

    def output_dim(self) -> int:
        """Output dimension: num_slots * output_dim (both allint_out and allint_mid_out)."""
        return self.num_slots * self._output_dim

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass for CDOT.

        Args:
            x: input tensor [B, num_slots, input_dim]

        Returns:
            allint_out: [B, num_slots * output_dim] — transformed features
            allint_mid_out: [B, num_slots * output_dim] — compress weights
        """
        batch_size = x.shape[0]

        transposed = x.transpose(1, 2)

        sub_input = transposed.reshape(
            batch_size * self.input_dim, self.num_slots
        )
        sub_output = torch.mm(sub_input, self.sub_compress_weight)
        sub_flat = sub_output.reshape(
            batch_size, self.input_dim * self.mid_dim
        )

        compress_wt_flat = self.compress_mlp(sub_flat)
        compress_wt = compress_wt_flat.reshape(
            batch_size, self.num_slots, self._output_dim
        )

        transformed = (
            torch.bmm(transposed, compress_wt) + self.compress_bias
        )

        allint_out = torch.bmm(x, transformed)

        allint_out_flat = allint_out.reshape(batch_size, -1)

        return allint_out_flat, compress_wt_flat
