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

"""AFP module for APPNet-style parameter personalization.

AFP automatically learns which features should be used for:
  - DNN prediction (forward path)
  - PPNet gate generation (personalization path)

This replaces the manual domain-group specification in PEPNet's EPNet/PPNet
with a learnable, data-driven partitioning strategy.

Reference: APPNet (Liu et al., WSDM 2026)
"""

from enum import Enum
from typing import Dict, List, Optional

import torch
from torch import nn


class AFPMode(str, Enum):
    """AFP partitioning granularity modes."""

    FEATURE_WISE = "feature_wise"  # Per-feature-field partitioning
    BIT_WISE = "bit_wise"  # Per-embedding-bit partitioning


class AFPModule(nn.Module):
    """Automatic Feature Partitioning module.

    Learns to partition input features between DNN prediction path and
    PPNet gate path via differentiable soft selection (Gumbel-softmax).

    Architecture:
        Input features [B, total_dim]
            │
            ├── Feature-wise classifier: Linear(total_dim → hidden → 1)
            │       → sigmoid → partition_prob [B, num_features]
            │
            ├── Gate input = features * (1 - partition_prob)
            └── DNN input  = features * partition_prob

    The partition_prob is trained end-to-end with the main model.
    During inference, temperature → 0 for hard selection.

    Args:
        feature_dims: List of per-feature embedding dimensions.
        mode: Partitioning granularity.
        hidden_units: Hidden units for the classifier MLP.
        temperature: Gumbel-softmax temperature (annealed during training).
        min_temperature: Lower bound for temperature annealing.
        gate_temperature: Separate temperature for gate path (optional).
    """

    def __init__(
        self,
        feature_dims: List[int],
        mode: str = "feature_wise",
        hidden_units: List[int] = None,
        temperature: float = 1.0,
        min_temperature: float = 0.1,
        gate_temperature: float = None,
    ) -> None:
        super().__init__()
        self.feature_dims = feature_dims
        self.num_features = len(feature_dims)
        self.mode = AFPMode(mode)
        self.temperature = temperature
        self.min_temperature = min_temperature
        self.gate_temperature = gate_temperature or temperature
        self._total_dim = sum(feature_dims)

        # Build per-feature classifiers
        if self.mode == AFPMode.FEATURE_WISE:
            self._build_feature_wise(hidden_units)
        else:
            self._build_bit_wise(hidden_units)

        # Temperature annealing schedule
        self.register_buffer("_current_temp", torch.tensor(temperature))
        self.register_buffer(
            "_current_gate_temp", torch.tensor(gate_temperature or temperature)
        )

        # Deterministic RNG for reproducible Gumbel noise
        self._rng = torch.Generator()
        self._rng.seed()  # Initialize with a random seed from OS entropy

        # Pre-compute bit-to-feature mapping for BIT_WISE (avoids O(n^2) lookup)
        self._bit_to_feat = []
        for fi, dim_i in enumerate(self.feature_dims):
            self._bit_to_feat.extend([fi] * dim_i)
        self._bit_to_feat = torch.tensor(self._bit_to_feat, dtype=torch.long)

    def _build_feature_wise(self, hidden_units: List[int] = None) -> None:
        """Feature-wise AFP: one classifier per feature field."""
        if hidden_units is None:
            hidden_units = [64, 32]

        self.classifiers = nn.ModuleList()
        for dim in self.feature_dims:
            layers = []
            prev = dim
            for h in hidden_units:
                layers.append(nn.Linear(prev, h))
                layers.append(nn.ReLU())
                prev = h
            layers.append(nn.Linear(prev, 1))  # Binary: DNN vs Gate
            self.classifiers.append(nn.Sequential(*layers))

    def _build_bit_wise(self, hidden_units: List[int] = None) -> None:
        """Bit-wise AFP: one classifier per embedding dimension.

        Each embedding bit gets its own lightweight classifier (1 → hidden → 1).
        Per-bit probabilities are aggregated (mean) back to per-feature level
        to maintain the same [B, num_features] partition_prob shape as feature_wise.
        """
        if hidden_units is None:
            hidden_units = [128, 64]

        self.bit_classifiers = nn.ModuleList()
        self.bit_offsets = []
        offset = 0
        for dim in self.feature_dims:
            for _ in range(dim):
                layers = []
                prev = 1
                for h in hidden_units:
                    layers.append(nn.Linear(prev, h))
                    layers.append(nn.ReLU())
                    prev = h
                layers.append(nn.Linear(prev, 1))
                self.bit_classifiers.append(nn.Sequential(*layers))
            self.bit_offsets.append(offset)
            offset += dim

    def anneal_temperature(self, step: int, total_steps: int) -> None:
        """Linear temperature annealing from current_temp to min_temperature."""
        progress = min(step / max(total_steps, 1), 1.0)
        self._current_temp.fill_(
            self.min_temperature
            + (self.temperature - self.min_temperature) * (1.0 - progress)
        )
        if self.gate_temperature != self.temperature:
            self._current_gate_temp.fill_(
                self.min_temperature
                + (self.gate_temperature - self.min_temperature) * (1.0 - progress)
            )

    def set_rng_seed(self, seed: int) -> None:
        """Set the RNG seed for reproducible Gumbel noise.

        Call this before each training epoch to ensure deterministic
        noise across epochs (e.g., from the trainer's epoch seed).
        """
        self._rng.manual_seed(seed)

    def forward(
        self,
        features: torch.Tensor,
        features_splits: Optional[List[int]] = None,
        hard_selection: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """Forward pass for automatic feature partitioning.

        Args:
            features: Concatenated feature tensor [B, total_dim].
            features_splits: Cumulative split positions for per-feature extraction.
                             If None, computed from self.feature_dims.
            hard_selection: If True, use argmax (hard assignment) instead of
                           soft Gumbel-softmax. Useful for inference.

        Returns:
            dict with keys:
                - 'gate_input': Features routed to PPNet gate [B, gate_dim]
                - 'dnn_input':  Features routed to DNN prediction [B, dnn_dim]
                - 'partition_prob': Soft partition probabilities [B, num_features]
                - 'gate_mask': Binary gate mask [B, num_features] (hard only)
                - 'dnn_mask': Binary dnn mask [B, num_features] (hard only)
        """
        if features_splits is None:
            features_splits = list(
                torch.cumsum(torch.tensor([0] + self.feature_dims), dim=0).tolist()
            )[:-1]

        # Validate input tensor dimension matches feature_dims sum
        assert features.size(1) == self._total_dim, (
            f"AFP input dim {features.size(1)} does not match "
            f"expected {self._total_dim} (sum of feature_dims)"
        )

        if self.mode == AFPMode.FEATURE_WISE:
            partition_probs = []
            for i, classifier in enumerate(self.classifiers):
                feat_start = features_splits[i]
                feat_end = feat_start + self.feature_dims[i]
                feat = features[:, feat_start:feat_end]  # [B, dim_i]
                logit = classifier(feat)  # [B, 1]
                # Gumbel-softmax: add Gumbel(0,1) noise scaled by temperature
                if self.training:
                    noise = torch.rand_like(logit, generator=self._rng)
                    gumbel = -torch.log(-torch.log(noise) + 1e-10)
                    noisy_logit = (logit + gumbel) / max(
                        self._current_temp.item(), 1e-6
                    )
                    prob = torch.sigmoid(noisy_logit)
                else:
                    prob = torch.sigmoid(logit)
                partition_probs.append(prob)

            partition_probs = torch.cat(partition_probs, dim=1)  # [B, num_features]

        else:  # BIT_WISE
            # Per-bit partitioning: each embedding dimension gets its own classifier.
            # Each bit classifies its own scalar dimension directly.
            bit_probs = []
            for bit_idx, classifier in enumerate(self.bit_classifiers):
                feat_idx = self._bit_to_feat[bit_idx].item()
                feat_start = self.bit_offsets[feat_idx]
                bit_offset_in_feat = bit_idx - feat_start
                # Extract this single bit's dimension
                bit_start = feat_start + bit_offset_in_feat
                bit_val = features[:, bit_start : bit_start + 1]  # [B, 1]
                logit = classifier(bit_val)  # [B, 1]
                # Gumbel-softmax with temperature
                if self.training:
                    noise = torch.rand_like(logit, generator=self._rng)
                    gumbel = -torch.log(-torch.log(noise) + 1e-10)
                    noisy_logit = (logit + gumbel) / max(
                        self._current_temp.item(), 1e-6
                    )
                    prob = torch.sigmoid(noisy_logit)
                else:
                    prob = torch.sigmoid(logit)
                bit_probs.append(prob)

            partition_probs = torch.cat(bit_probs, dim=1)  # [B, total_bits]

            # Aggregate per-bit probs to per-feature probs (mean within each feature)
            aggregated_probs = []
            for fi in range(self.num_features):
                start = self.bit_offsets[fi]
                dim_i = self.feature_dims[fi]
                bit_slice = partition_probs[:, start : start + dim_i]
                aggregated_probs.append(bit_slice.mean(dim=1, keepdim=True))
            partition_probs = torch.cat(aggregated_probs, dim=1)  # [B, num_features]

        # Soft selection: partition_prob → DNN path, (1 - partition_prob) → Gate path
        gate_weights = 1.0 - partition_probs  # [B, num_features]
        dnn_weights = partition_probs  # [B, num_features]

        # Compute per-feature partitioned tensors
        gate_parts = []
        dnn_parts = []
        for i in range(self.num_features):
            feat_start = features_splits[i]
            feat_end = feat_start + self.feature_dims[i]
            feat = features[:, feat_start:feat_end]  # [B, dim_i]
            w_gate = gate_weights[:, i : i + 1]  # [B, 1]
            w_dnn = dnn_weights[:, i : i + 1]  # [B, 1]
            gate_parts.append(feat * w_gate)
            dnn_parts.append(feat * w_dnn)

        gate_input = torch.cat(gate_parts, dim=1)  # [B, total_dim]
        dnn_input = torch.cat(dnn_parts, dim=1)  # [B, total_dim]

        # Hard selection for inference
        if hard_selection:
            gate_mask = (partition_probs < 0.5).float()  # [B, num_features]
            dnn_mask = 1.0 - gate_mask
            gate_parts_hard = []
            dnn_parts_hard = []
            for i in range(self.num_features):
                feat_start = features_splits[i]
                feat_end = feat_start + self.feature_dims[i]
                feat = features[:, feat_start:feat_end]
                w_gate = gate_mask[:, i : i + 1].expand(-1, self.feature_dims[i])
                w_dnn = dnn_mask[:, i : i + 1].expand(-1, self.feature_dims[i])
                gate_parts_hard.append(feat * w_gate)
                dnn_parts_hard.append(feat * w_dnn)
            gate_input = torch.cat(gate_parts_hard, dim=1)
            dnn_input = torch.cat(dnn_parts_hard, dim=1)
        else:
            gate_mask = None
            dnn_mask = None

        return {
            "gate_input": gate_input,
            "dnn_input": dnn_input,
            "partition_prob": partition_probs,
            "gate_mask": gate_mask,
            "dnn_mask": dnn_mask,
        }

    @torch.no_grad()
    def get_partition_summary(self, partition_prob: torch.Tensor) -> Dict[str, float]:
        """Return partition statistics without gradient tracking."""
        dnn_ratio = partition_prob.mean().item()
        gate_ratio = (1.0 - partition_prob).mean().item()
        return {
            "dnn_partition_ratio": dnn_ratio,
            "gate_partition_ratio": gate_ratio,
            "num_features_routed_to_dnn": int((partition_prob > 0.5).sum().item()),
            "num_features_routed_to_gate": int((partition_prob <= 0.5).sum().item()),
        }

    def extra_repr(self) -> str:
        """Return string representation for printing."""
        return (
            f"mode={self.mode.value}, num_features={self.num_features}, "
            f"total_dim={self._total_dim}, "
            f"temp={self._current_temp.item():.3f}, "
            f"gate_temp={self._current_gate_temp.item():.3f}"
        )
