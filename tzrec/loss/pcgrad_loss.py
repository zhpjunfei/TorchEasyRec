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

Memory-efficient: computes per-task gradients from the shared forward graph
using a single autograd.grad() call with detached task losses, then uses
a backward hook to patch gradients in-place (avoiding large intermediate
computation graph that would OOM on large models).

Key design decisions:
1. Per-task gradient extraction: detach other tasks' losses, call
   autograd.grad() on the remaining task. retain_graph=True only for
   penultimate task, freeing the graph on the last task.
2. Gradient patching via backward hook: create a leaf trigger tensor,
   register hook that writes projected gradients directly to p.grad.
   backward() on trigger is O(1) memory.
"""

from typing import TYPE_CHECKING, Dict, List, Tuple

import torch
import torch.nn as nn

if TYPE_CHECKING:
    from tzrec.datasets.utils import Batch


def _project_conflict(
    g_i: torch.Tensor,
    g_j: torch.Tensor,
    eps: float = 1e-8,
) -> torch.Tensor:
    """Project gradient g_i onto the normal plane of g_j.

    Args:
        g_i: task i's flattened gradient, shape (n_params,).
        g_j: task j's flattened gradient, shape (n_params,).
        eps: numerical stability constant for ||g_j||^2.

    Returns:
        Projected g_i, same shape.
    """
    dot_product = torch.dot(g_i, g_j)
    denom = torch.dot(g_j, g_j) + eps
    projected = g_i - (dot_product / denom) * g_j
    return projected


class PCGradLoss(nn.Module):
    """Strict PCGrad gradient surgery for multi-task learning.

    Uses a backward hook to patch gradients in-place, avoiding a large
    intermediate computation graph that would OOM on large models.

    Args:
        asymmetric: If True, only project the first task's gradient onto the
            second task's normal plane (CVR-priority mode). If False, project
            both ways (standard PCGrad).
    """

    def __init__(self, asymmetric: bool = True) -> None:
        super().__init__()
        self.asymmetric = asymmetric
        self._hook_handle = None

    def _patch_gradients(
        self,
        total_grad: torch.Tensor,
        params: List[nn.Parameter],
    ) -> None:
        """Overwrite .grad on each parameter with the PCGrad-projected gradient.

        Note: must directly assign p.grad (not check for None first), because
        on first call all p.grad are None — the hook replaces them entirely.
        """
        offset = 0
        for p in params:
            n = p.numel()
            p.grad = total_grad[offset : offset + n].reshape(p.shape).to(p.dtype)
            offset += n

    def _extract_task_gradients(
        self,
        losses: Dict[str, torch.Tensor],
        model: nn.Module,
    ) -> Tuple[torch.Tensor, List[nn.Parameter]]:
        """Extract per-task gradients from the shared forward graph.

        For each task i, detaches all other tasks' losses and calls
        autograd.grad() on the remaining task loss. Uses retain_graph=True
        only for the penultimate task, so the forward graph is freed after
        the last task's gradient is extracted.

        Peak memory: O(forward_graph) — the graph is held for (N-1) tasks
        then freed on the last task. For N=2, this means the graph is held
        only during task 0's gradient computation, then freed during task 1.

        Args:
            losses: dict mapping task name -> loss tensor.
            model: the PyTorch model.

        Returns:
            grads: stacked tensor of shape (n_tasks, n_params).
            params: list of model parameters.
        """
        params = [p for p in model.parameters() if p.requires_grad]
        if not params:
            raise ValueError("No trainable parameters found in model")

        n_tasks = len(losses)
        n_params = sum(p.numel() for p in params)
        grads = torch.zeros(
            n_tasks, n_params, device=params[0].device, dtype=params[0].dtype
        )
        loss_items = list(losses.items())

        for i in range(n_tasks):
            # Build combined loss with only task i active (others detached)
            parts = []
            for j, (_name, loss_val) in enumerate(loss_items):
                if j == i:
                    val = torch.sum(loss_val, dim=0) if loss_val.dim() > 0 else loss_val
                else:
                    val = (
                        torch.sum(loss_val.detach(), dim=0)
                        if loss_val.dim() > 0
                        else loss_val.detach()
                    )
                parts.append(val)

            combined = sum(parts)

            raw_grads = torch.autograd.grad(
                combined,
                params,
                retain_graph=(i < n_tasks - 1),
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

    def forward(
        self,
        losses: Dict[str, torch.Tensor],
        model: nn.Module,
        batch: "Batch" = None,
    ) -> torch.Tensor:
        """Compute PCGrad-modified total loss.

        Args:
            losses: dict of per-task loss tensors. Keys order determines
                task priority: first task is the "priority" task (CVR).
            model: the model whose parameters receive modified gradients.
            batch: unused (kept for API compatibility with old signature).

        Returns:
            total_loss: a scalar tensor whose backward() triggers the hook
                that patches projected gradients onto each parameter.
        """
        grads, params = self._extract_task_gradients(losses, model)
        n_tasks = grads.size(0)
        eps = 1e-8

        projected = grads.clone()

        for i in range(n_tasks):
            for j in range(n_tasks):
                if i == j:
                    continue
                dot_ij = torch.dot(grads[i], grads[j])
                if dot_ij < 0:
                    projected[i] = _project_conflict(projected[i], grads[j], eps)
                    if not self.asymmetric:
                        dot_ji = torch.dot(grads[j], grads[i])
                        if dot_ji < 0:
                            projected[j] = _project_conflict(
                                projected[j], grads[i], eps
                            )

        total_grad = projected.sum(dim=0)

        # Leaf tensor with requires_grad=True; backward() is O(1) memory.
        trigger = torch.zeros(
            1,
            device=total_grad.device,
            dtype=total_grad.dtype,
            requires_grad=True,
        )

        if self._hook_handle is not None:
            self._hook_handle.remove()

        def _patch_and_clear(grad, tg=total_grad, ps=params):
            self._patch_gradients(tg, ps)
            return None

        self._hook_handle = trigger.register_hook(_patch_and_clear)
        return trigger
