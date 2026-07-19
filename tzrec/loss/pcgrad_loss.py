# Copyright (c) 2024, Alibaba Group;
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Strict PCGrad gradient surgery for multi-task learning.

Based on "Gradient Surgery for Multi-Task Learning" (Yu et al., NeurIPS 2020).

Unlike the previous approximation (which modulated loss weights), this
implementation performs true gradient projection: conflicting gradients are
projected onto each other's normal planes before summation.
"""

from typing import Dict, List, Tuple

import torch
import torch.nn as nn


def _flatten_grads(
    losses: Dict[str, torch.Tensor],
    model: nn.Module,
) -> Tuple[torch.Tensor, List[nn.Parameter]]:
    """Compute per-task flattened gradient vectors.

    Args:
        losses: dict mapping task name -> loss tensor (scalar or per-sample).
        model: the PyTorch model.

    Returns:
        grads: stacked tensor of shape (n_tasks, n_params).
        params: list of model parameters (for unflattening later).
    """
    params = [p for p in model.parameters() if p.requires_grad]
    if not params:
        raise ValueError("No trainable parameters found in model")
    n_tasks = len(losses)
    n_params = sum(p.numel() for p in params)
    grads = torch.zeros(
        n_tasks, n_params, device=params[0].device, dtype=params[0].dtype
    )

    for i, (_name, loss_val) in enumerate(losses.items()):
        # Ensure we get a scalar for autograd
        if loss_val.dim() == 0:
            grad_scalar = loss_val
        else:
            grad_scalar = torch.sum(loss_val)

        raw_grads = torch.autograd.grad(
            grad_scalar,
            params,
            retain_graph=True,
            allow_unused=True,
            create_graph=False,
        )
        flat = []
        for g, p in zip(raw_grads, params):
            if g is not None:
                flat.append(g.reshape(-1))
            else:
                flat.append(torch.zeros(p.numel(), device=p.device, dtype=p.dtype))
        grads[i] = torch.cat(flat)

    return grads, params


def _project_conflict(
    g_i: torch.Tensor,
    g_j: torch.Tensor,
    eps: float = 1e-8,
) -> torch.Tensor:
    """Project gradient g_i onto the normal plane of g_j.

    Removes the component of g_i that opposes g_j (conflicting direction).

    Args:
        g_i: task i's flattened gradient, shape (n_params,).
        g_j: task j's flattened gradient, shape (n_params,).
        eps: numerical stability constant for ||g_j||².

    Returns:
        Projected g_i, same shape.
    """
    dot_product = torch.dot(g_i, g_j)
    denom = torch.dot(g_j, g_j) + eps
    # proj_{g_j}(g_i) = (g_i · g_j) / ||g_j||² * g_j
    projected = g_i - (dot_product / denom) * g_j
    return projected


class PCGradLoss(nn.Module):
    """Strict PCGrad gradient surgery for multi-task learning.

    Performs true gradient projection (not loss-weighting approximation).
    For each pair of tasks with conflicting gradients (negative dot product),
    projects the conflicting gradient onto the normal plane of the other.

    Supports two modes:
      - symmetric (default): both gradients get projected
      - asymmetric (cvr_priority): only CTR projects onto CVR; CVR stays pure

    Args:
        asymmetric: If True, only project the first task's gradient onto the
            second task's normal plane (CVR-priority mode). If False, project
            both ways (standard PCGrad).
    """

    def __init__(self, asymmetric: bool = True) -> None:
        super().__init__()
        self.asymmetric = asymmetric

    def forward(
        self, losses: Dict[str, torch.Tensor], model: nn.Module
    ) -> torch.Tensor:
        """Compute PCGrad-modified total loss.

        Args:
            losses: dict of per-task loss tensors. Keys order determines
                task priority: first task is the "priority" task (CVR).
            model: the model whose parameters receive modified gradients.

        Returns:
            total_loss: a scalar tensor whose backward() produces the
                PCGrad-projected gradient.
        """
        grads, params = _flatten_grads(losses, model)
        n_tasks = grads.size(0)
        eps = 1e-8

        # Start with a copy of all raw gradients
        projected = grads.clone()

        for i in range(n_tasks):
            for j in range(n_tasks):
                if i == j:
                    continue
                # Only project g_i if it conflicts with g_j
                dot_ij = torch.dot(grads[i], grads[j])
                if dot_ij < 0:
                    projected[i] = _project_conflict(projected[i], grads[j], eps)
                    if not self.asymmetric:
                        # Symmetric: also project g_j
                        dot_ji = torch.dot(grads[j], grads[i])
                        if dot_ji < 0:
                            projected[j] = _project_conflict(
                                projected[j], grads[i], eps
                            )

        # Sum all projected gradients
        total_grad = projected.sum(dim=0)  # shape (n_params,)

        # Reconstruct a loss whose backward yields total_grad.
        # Use the linear trick: total_loss = dot(total_grad, flat_params)
        # Its gradient w.r.t. params IS total_grad.
        flat_params_list = [p.reshape(-1) for p in params]
        flat_params = torch.cat(flat_params_list)
        total_loss = (total_grad * flat_params).sum()

        return total_loss
