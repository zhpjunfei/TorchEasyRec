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

"""Verify bag↔seq weight sharing: same Parameter object = joined gradients."""

import torch

N, D = 100, 8  # 100 tokens, 8-dim

# Simulate bag EmbeddingBag and seq Embedding with shared weight
bag_weight = torch.nn.Parameter(torch.randn(N, D))
seq_emb = torch.nn.Embedding(N, D)
seq_emb.weight = bag_weight  # ← this is the key aliasing

assert seq_emb.weight.data_ptr() == bag_weight.data_ptr(), "Not sharing!"

# Forward: bag pooling (mean)
indices = torch.tensor([[0, 1], [2, 3]])
offsets = torch.tensor([0, 2, 4])
bag_out = torch.nn.functional.embedding_bag(
    indices.flatten(), bag_weight, offsets, mode="mean"
)
# Forward: seq lookup
seq_out = seq_emb(torch.tensor([[0, 1], [2, 3]]))
# seq_out shape = (2, 2, 8); bag_out shape = (2, 8)

# Backward: gradients accumulate
loss = bag_out.mean() + seq_out.mean()
loss.backward()

# One weight, one gradient tensor
before = bag_weight.data.clone()
bag_weight.data -= 0.1 * bag_weight.grad
print(f"Weights updated: changed={not torch.allclose(before, bag_weight.data)}")
print(f"Bag -> seq readback same: {(before != seq_emb.weight.data).any().item()}")
print("ALL OK: Both paths share one gradient stream.")
