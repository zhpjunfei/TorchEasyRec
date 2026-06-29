# Copyright (c) 2024-2025, Alibaba Group;
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from typing import Any, Dict, List, Optional

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from tzrec.modules.mlp import MLP
from tzrec.protos.seq_encoder_pb2 import SeqEncoderConfig
from tzrec.utils import config_util
from tzrec.utils.fx_util import fx_arange
from tzrec.utils.load_class import get_register_class_meta

torch.fx.wrap(fx_arange)


_SEQ_ENCODER_CLASS_MAP = {}
_meta_cls = get_register_class_meta(_SEQ_ENCODER_CLASS_MAP)


@torch.fx.wrap
def _attention_mask(
    sequence: torch.Tensor, num_heads: int, sequence_length: torch.Tensor
) -> torch.Tensor:
    batch_size, max_seq_length, _ = sequence.size()
    mask = (
        torch.arange(max_seq_length, device=sequence_length.device)
        .unsqueeze(0)
        .expand(batch_size, max_seq_length)
    )
    mask = (mask < sequence_length.unsqueeze(1)).int()
    mask = ~(torch.multiply(mask.unsqueeze(2), mask.unsqueeze(1)).type(torch.bool))
    mask = mask.repeat_interleave(repeats=num_heads, dim=0)
    return mask


class SequenceEncoder(nn.Module, metaclass=_meta_cls):
    """Base module of sequence encoder."""

    def __init__(self, input: str) -> None:
        super().__init__()
        self._input = input

    def input(self) -> str:
        """Get sequence encoder input group name."""
        return self._input

    def output_dim(self) -> int:
        """Output dimension of the module."""
        raise NotImplementedError


class DINEncoder(SequenceEncoder):
    """DIN sequence encoder.

    Args:
        sequence_dim (int): sequence tensor channel dimension.
        query_dim (int): query tensor channel dimension.
        input(str): input feature group name.
        attn_mlp (dict): target attention MLP module parameters.
        max_seq_length (int): maximum sequence length.
        time_gate_dim (int): if > 0, the last ``time_gate_dim`` dims of seq_emb
            are time features used for multiplicative time gating.
    """

    def __init__(
        self,
        sequence_dim: int,
        query_dim: int,
        input: str,
        attn_mlp: Dict[str, Any],
        max_seq_length: int = 0,
        time_gate_dim: int = 0,
        **kwargs: Optional[Dict[str, Any]],
    ) -> None:
        super().__init__(input)
        self._query_dim = query_dim
        self._sequence_dim = sequence_dim
        self._time_gate_dim = time_gate_dim
        self._content_seq_dim = sequence_dim - time_gate_dim
        if self._query_dim > self._content_seq_dim:
            self.query_proj = nn.Linear(self._query_dim, self._content_seq_dim)
        self.mlp = MLP(in_features=self._content_seq_dim * 4, dim=3, **attn_mlp)
        self.linear = nn.Linear(self.mlp.hidden_units[-1], 1)
        if time_gate_dim > 0:
            self.time_gate_linear = nn.Linear(time_gate_dim, 1)
        self._query_name = f"{input}.query"
        self._sequence_name = f"{input}.sequence"
        self._sequence_length_name = f"{input}.sequence_length"
        self._max_seq_length = max_seq_length

    def output_dim(self) -> int:
        """Output dimension of the module."""
        return self._content_seq_dim

    def forward(self, sequence_embedded: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Forward the module."""
        query = sequence_embedded[self._query_name]
        sequence = sequence_embedded[self._sequence_name]
        sequence_length = sequence_embedded[self._sequence_length_name]
        if self._max_seq_length > 0:
            sequence_length = torch.clamp_max(sequence_length, self._max_seq_length)
            sequence = sequence[:, : self._max_seq_length, :]
        max_seq_length = sequence.size(1)
        sequence_mask = fx_arange(
            max_seq_length, device=sequence_length.device
        ).unsqueeze(0) < sequence_length.unsqueeze(1)

        if self._time_gate_dim > 0:
            ts_emb = sequence[:, :, -self._time_gate_dim :]
            content_seq = sequence[:, :, : -self._time_gate_dim]
            gate = torch.sigmoid(self.time_gate_linear(ts_emb))
        else:
            content_seq = sequence
            gate = None

        if hasattr(self, "query_proj"):
            query = self.query_proj(query)
        elif self._query_dim < self._content_seq_dim:
            query = F.pad(query, (0, self._content_seq_dim - self._query_dim))
        queries = query.unsqueeze(1).expand(-1, max_seq_length, -1)

        attn_input = torch.cat(
            [queries, content_seq, queries - content_seq, queries * content_seq],
            dim=-1,
        )
        attn_output = self.mlp(attn_input)
        attn_output = self.linear(attn_output)
        attn_output = attn_output.transpose(1, 2)

        padding = torch.ones_like(attn_output) * (-(2**31) + 1)
        scores = torch.where(sequence_mask.unsqueeze(1), attn_output, padding)

        if gate is not None:
            scores = scores * gate.transpose(1, 2)

        scores = F.softmax(scores, dim=-1)
        return torch.matmul(scores, content_seq).squeeze(1)


class SimpleAttention(SequenceEncoder):
    """Simple attention encoder."""

    def __init__(
        self,
        sequence_dim: int,
        query_dim: int,
        input: str,
        max_seq_length: int = 0,
        **kwargs: Optional[Dict[str, Any]],
    ) -> None:
        super().__init__(input)
        self._sequence_dim = sequence_dim
        self._query_dim = query_dim
        self._query_name = f"{input}.query"
        self._sequence_name = f"{input}.sequence"
        self._sequence_length_name = f"{input}.sequence_length"
        self._max_seq_length = max_seq_length

    def output_dim(self) -> int:
        """Output dimension of the module."""
        return self._sequence_dim

    def forward(self, sequence_embedded: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Forward the module."""
        query = sequence_embedded[self._query_name]
        sequence = sequence_embedded[self._sequence_name]
        sequence_length = sequence_embedded[self._sequence_length_name]
        if self._max_seq_length > 0:
            sequence_length = torch.clamp_max(sequence_length, self._max_seq_length)
            sequence = sequence[:, : self._max_seq_length, :]
        max_seq_length = sequence.size(1)
        sequence_mask = fx_arange(max_seq_length, sequence_length.device).unsqueeze(
            0
        ) < sequence_length.unsqueeze(1)

        attn_output = torch.matmul(sequence, query.unsqueeze(2)).squeeze(2)
        padding = torch.ones_like(attn_output) * (-(2**31) + 1)
        scores = torch.where(sequence_mask, attn_output, padding)
        scores = F.softmax(scores, dim=-1)
        return torch.matmul(scores.unsqueeze(1), sequence).squeeze(1)


class PoolingEncoder(SequenceEncoder):
    """Mean/Sum pooling sequence encoder.

    Args:
        sequence_dim (int): sequence tensor channel dimension.
        input (str): input feature group name.
        pooling_type (str): pooling type, sum or mean.
    """

    def __init__(
        self,
        sequence_dim: int,
        input: str,
        pooling_type: str = "mean",
        max_seq_length: int = 0,
        **kwargs: Optional[Dict[str, Any]],
    ) -> None:
        super().__init__(input)
        self._sequence_dim = sequence_dim
        self._pooling_type = pooling_type
        assert self._pooling_type in [
            "sum",
            "mean",
        ], "only sum|mean pooling type supported now."
        self._sequence_name = f"{input}.sequence"
        self._sequence_length_name = f"{input}.sequence_length"
        self._max_seq_length = max_seq_length

    def output_dim(self) -> int:
        """Output dimension of the module."""
        return self._sequence_dim

    def forward(self, sequence_embedded: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Forward the module."""
        sequence = sequence_embedded[self._sequence_name]
        if self._max_seq_length > 0:
            sequence = sequence[:, : self._max_seq_length, :]
        feature = torch.sum(sequence, dim=1)
        if self._pooling_type == "mean":
            sequence_length = sequence_embedded[self._sequence_length_name]
            if self._max_seq_length > 0:
                sequence_length = torch.clamp_max(sequence_length, self._max_seq_length)
            sequence_length = torch.clamp_min(sequence_length, 1)
            feature = feature / sequence_length.unsqueeze(1)
        return feature


class SelfAttentionEncoder(SequenceEncoder):
    """Mean/Sum pooling sequence encoder.

    Args:
        sequence_dim (int): sequence tensor channel dimension.
        input (str): input feature group name.
        pooling_type (str): pooling type, sum or mean.
        query_dim (int): query tensor channel dimension.
    """

    def __init__(
        self,
        sequence_dim: int,
        input: str,
        multihead_attn_dim: int,
        num_heads: int = 8,
        dropout: float = 0.0,
        max_seq_length: int = 0,
        **kwargs: Optional[Dict[str, Any]],
    ) -> None:
        super().__init__(input)
        self._sequence_dim = sequence_dim
        self._sequence_name = f"{input}.sequence"
        self._sequence_length_name = f"{input}.sequence_length"
        self._max_seq_length = max_seq_length
        self._num_heads = num_heads
        self._multihead_attn_dim = multihead_attn_dim

        self._head_dim = self._multihead_attn_dim // num_heads
        assert self._head_dim * num_heads == self._multihead_attn_dim, (
            "multihead_attn_dim must be divisible by num_heads"
        )

        self._query = nn.Linear(sequence_dim, self._multihead_attn_dim)
        self._key = nn.Linear(sequence_dim, self._multihead_attn_dim)
        self._value = nn.Linear(sequence_dim, self._multihead_attn_dim)
        self._multihead_attn = nn.MultiheadAttention(
            self._multihead_attn_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )

    def output_dim(self) -> int:
        """Output dimension of the module."""
        return self._multihead_attn_dim

    def forward(self, sequence_embedded: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Forward the module."""
        sequence = sequence_embedded[self._sequence_name]
        if self._max_seq_length > 0:
            sequence = sequence[:, : self._max_seq_length, :]

        Q = self._query(sequence)
        K = self._key(sequence)
        V = self._value(sequence)
        sequence_length = sequence_embedded[self._sequence_length_name]
        attn_mask = _attention_mask(
            sequence, self._num_heads, sequence_length
        )  # [B*num_heads, L, L]
        attn_output, attn_weights = self._multihead_attn(Q, K, V, attn_mask=attn_mask)
        attn_output = torch.nan_to_num(attn_output, nan=0.0)
        sequence_length = torch.clamp_min(sequence_length, 1)
        output = attn_output.sum(dim=1) / sequence_length.unsqueeze(1)
        return output


class MultiWindowDINEncoder(SequenceEncoder):
    """Multi Window DIN module.

    Args:
        sequence_dim (int): sequence tensor channel dimension.
        query_dim (int): query tensor channel dimension.
        input(str): input feature group name.
        windows_len (list): time windows len.
        attn_mlp (dict): target attention MLP module parameters.
    """

    def __init__(
        self,
        sequence_dim: int,
        query_dim: int,
        input: str,
        windows_len: List[int],
        attn_mlp: Dict[str, Any],
        **kwargs: Optional[Dict[str, Any]],
    ) -> None:
        super().__init__(input)
        self._query_dim = query_dim
        self._sequence_dim = sequence_dim
        self._windows_len = windows_len
        if self._query_dim > self._sequence_dim:
            raise ValueError("query_dim > sequence_dim not supported yet.")
        self.register_buffer("windows_len", torch.tensor(windows_len))
        self.register_buffer(
            "cumsum_windows_len", torch.tensor(np.cumsum([0] + list(windows_len)[:-1]))
        )
        self._sum_windows_len = sum(windows_len)
        self.mlp = MLP(in_features=sequence_dim * 3, dim=3, **attn_mlp)
        self.linear = nn.Linear(self.mlp.hidden_units[-1], 1)
        self.active = nn.PReLU()
        self._query_name = f"{input}.query"
        self._sequence_name = f"{input}.sequence"
        self._sequence_length_name = f"{input}.sequence_length"

    def output_dim(self) -> int:
        """Output dimension of the module."""
        return self._sequence_dim * (len(self._windows_len) + 1)

    def forward(self, sequence_embedded: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Forward the module."""
        query = sequence_embedded[self._query_name]
        sequence = sequence_embedded[self._sequence_name]
        sequence_length = sequence_embedded[self._sequence_length_name]
        max_seq_length = sequence.size(1)
        sequence_mask = fx_arange(
            max_seq_length, device=sequence_length.device
        ).unsqueeze(0) < sequence_length.unsqueeze(1)

        if self._query_dim < self._sequence_dim:
            query = F.pad(query, (0, self._sequence_dim - self._query_dim))
        queries = query.unsqueeze(1).expand(-1, max_seq_length, -1)  # [B, T, C]

        attn_input = torch.cat([sequence, queries * sequence, queries], dim=-1)
        attn_output = self.mlp(attn_input)
        attn_output = self.linear(attn_output)
        attn_output = self.active(attn_output)  # [B, T, 1]

        att_sequences = attn_output * sequence_mask.unsqueeze(2) * sequence

        pad = (0, 0, 0, self._sum_windows_len - max_seq_length)
        pad_att_sequences = F.pad(att_sequences, pad).transpose(0, 1)
        result = torch.segment_reduce(
            pad_att_sequences, reduce="sum", lengths=self.windows_len, axis=0
        ).transpose(0, 1)  # [B, L, C]

        segment_length = torch.min(
            sequence_length.unsqueeze(1) - self.cumsum_windows_len.unsqueeze(0),
            self.windows_len,
        )
        result = result / torch.max(
            segment_length, torch.ones_like(segment_length)
        ).unsqueeze(2)

        return torch.cat([result, query.unsqueeze(1)], dim=1).reshape(
            result.shape[0], -1
        )  # [B, (L+1)*C]


def create_seq_encoder(
    seq_encoder_config: SeqEncoderConfig, group_total_dim: Dict[str, int]
) -> SequenceEncoder:
    """Build seq encoder model..

    Args:
        seq_encoder_config:  a SeqEncoderConfig.group_total_dim.
        group_total_dim: a dict contain all seq group dim info.

    Return:
        model: a SequenceEncoder cls.
    """
    model_cls_name = config_util.which_msg(seq_encoder_config, "seq_module")
    # pyre-ignore [16]
    model_cls = SequenceEncoder.create_class(model_cls_name)
    seq_type = seq_encoder_config.WhichOneof("seq_module")
    seq_type_config = getattr(seq_encoder_config, seq_type)
    input_name = seq_type_config.input
    query_dim = group_total_dim[f"{input_name}.query"]
    sequence_dim = group_total_dim[f"{input_name}.sequence"]
    seq_config_dict = config_util.config_to_kwargs(seq_type_config)
    seq_config_dict["sequence_dim"] = sequence_dim
    seq_config_dict["query_dim"] = query_dim
    seq_encoder = model_cls(**seq_config_dict)
    return seq_encoder


class TransformerEncoder(SequenceEncoder):
    """Transformer-based target-aware sequence encoder.

    Architecture:
        s -> proj_in -> TransformerEncoder -> h
        q -> proj_in -> cross-attention(q, h) -> attended
        gate = sigmoid(MLP([q_proj, attended, q⊙attended])) -> [B,128]
        fused = attended*gate + mean(h)*(1-gate)
        output = LN(fused) -> proj_pooled -> [B,216]

    Two orthogonal attention mechanisms with distinct roles:
    - Self-attention (Transformer): pure intra-sequence dependency modeling.
      Target item is NOT injected into the sequence — no target leakage.
    - Cross-attention (dot-product q·h/√d): selects positions via query-key
      similarity — 0 learned parameters, no attention redundancy.

    Key design points:
    1. No target leakage: Transformer sees only s, not s+q.
    2. Shared proj_in: q_proj and h in same linear space for clean dot-product.
    3. Vector gate [B,128]: per-dim blend of attended and mean(h).
    4. Gate ignores mean(h): avoids double injection with the (1-g) fused path.
    5. LN on fused only: no extra residual that could wash the gating signal.

    Args:
        sequence_dim (int): sequence tensor channel dimension.
        query_dim (int): query tensor channel dimension.
        input (str): input feature group name.
        transformer_hidden (int): transformer hidden dimension.
        num_heads (int): number of attention heads in transformer.
        num_layers (int): number of transformer encoder layers.
        dropout (float): dropout rate for transformer layers.
        max_seq_length (int): maximum sequence length.
    """

    def __init__(
        self,
        sequence_dim: int,
        query_dim: int,
        input: str,
        transformer_hidden: int = 128,
        num_heads: int = 4,
        num_layers: int = 1,
        dropout: float = 0.0,
        max_seq_length: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(input)
        self._sequence_dim = sequence_dim
        self._query_dim = query_dim
        self._transformer_hidden = transformer_hidden
        self._num_heads = num_heads
        self._max_seq_length = max_seq_length

        assert query_dim == sequence_dim, (
            f"TransformerEncoder requires query_dim ({query_dim}) == "
            f"sequence_dim ({sequence_dim}) because proj_in is shared "
            "between sequence and query paths."
        )

        self._query_name = f"{input}.query"
        self._sequence_name = f"{input}.sequence"
        self._sequence_length_name = f"{input}.sequence_length"

        # Project sequence (sequence_dim) to transformer_hidden
        self._proj_in = nn.Linear(sequence_dim, transformer_hidden)
        self._dropout_in = nn.Dropout(dropout)

        # Transformer encoder layer
        if transformer_hidden % num_heads != 0:
            raise ValueError(
                f"transformer_hidden ({transformer_hidden}) must be "
                f"divisible by num_heads ({num_heads})"
            )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=transformer_hidden,
            nhead=num_heads,
            dim_feedforward=transformer_hidden * 4,
            dropout=dropout,
            batch_first=True,
            norm_first=False,
        )
        self._transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Cross-attention selection: q · h_i / √d
        # proj_in is shared between Transformer path and query scoring path,
        # ensuring q_proj and h live in the same linear space for clean dot-product.

        # Attention-aware gating: gate sees target-attention relation only
        self._gate_mlp = MLP(
            in_features=transformer_hidden * 3,
            hidden_units=[64],
            activation="nn.ReLU",
            dim=2,
        )
        self._gate_proj = nn.Linear(64, transformer_hidden)

        # Feature normalization for stable fusion output
        self._gate_ln = nn.LayerNorm(transformer_hidden)

        # Final projection from transformer_hidden to output dim
        self._proj_pooled = nn.Linear(transformer_hidden, sequence_dim)

    def output_dim(self) -> int:
        """Output dimension of the module."""
        return self._sequence_dim

    def forward(self, sequence_embedded: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Forward the module."""
        query = sequence_embedded[self._query_name]
        sequence = sequence_embedded[self._sequence_name]
        sequence_length = sequence_embedded[self._sequence_length_name]

        if self._max_seq_length > 0:
            sequence_length = torch.clamp_max(sequence_length, self._max_seq_length)
            sequence = sequence[:, : self._max_seq_length, :]

        max_seq_length = sequence.size(1)
        sequence_mask = fx_arange(
            max_seq_length, device=sequence_length.device
        ).unsqueeze(0) < sequence_length.unsqueeze(1)

        # ── Pure sequence encoding (no target leakage) ──
        h = self._proj_in(sequence)
        h = self._dropout_in(h)
        h = self._transformer(h, src_key_padding_mask=~sequence_mask)

        # ── Cross-attention selection: q · h_i / √d ──
        q_proj = self._proj_in(query).unsqueeze(1)
        scores = torch.matmul(q_proj, h.transpose(1, 2)) / (
            self._transformer_hidden**0.5
        )

        padding = torch.ones_like(scores) * (-(2**31) + 1)
        scores = torch.where(sequence_mask.unsqueeze(1), scores, padding)
        scores = F.softmax(scores, dim=-1)

        attended = torch.matmul(scores, h).squeeze(1)

        # ── Gated fusion ──
        q_proj_2d = self._proj_in(query)
        seq_mean = h.mean(dim=1)
        gate = torch.sigmoid(
            self._gate_proj(
                self._gate_mlp(
                    torch.cat([q_proj_2d, attended, q_proj_2d * attended], dim=-1)
                )
            )
        )
        fused = attended * gate + seq_mean * (1 - gate)
        output = self._gate_ln(fused)

        output = self._proj_pooled(output)
        return output
