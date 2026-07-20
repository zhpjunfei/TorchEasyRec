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

Memory-efficient implementation: extracts per-task gradients via autograd.grad()
on each task's individual loss, then uses a backward hook to patch gradients
in-place (avoiding the large flat_params tensor that would OOM on large models).

Key design decisions:
1. Per-task gradient extraction: call autograd.grad() on each task's individual
   loss separately (NOT a combined loss). This avoids introducing extra nodes
   into the forward graph that would increase memory consumption.
2. retain_graph=True for ALL tasks: keeps the forward graph alive between
   gradient extractions. This strategy (matching f1e41ba / 7.19) avoids potential
   CUDA memory allocator fragmentation issues that can occur with retain_graph=False.
3. Gradient patching via backward hook: create a leaf trigger tensor, register
   a hook that writes projected gradients directly to p.grad. backward() on
   trigger is O(1) memory, avoiding the large flat_params tensor.
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
        """Extract per-task gradients via autograd.grad() on shared graph.

        For each task i, calls autograd.grad(loss_i, params) directly on the
        individual task's loss. Uses retain_graph=True for all tasks to keep
        the forward graph alive between gradient extractions.

        autograd.grad() does NOT consume the computation graph (unlike
        backward()), so multiple calls on the same graph are safe.

        Peak memory: O(forward_graph) — the graph is held for all N tasks
        via retain_graph=True, matching the proven working strategy from f1e41ba.

        IMPORTANT: Each task's loss is passed to autograd.grad() individually.
        DO NOT combine multiple task losses into a single tensor before calling
        autograd.grad(), as this introduces extra add nodes into the forward graph
        that can cause OOM on memory-constrained GPUs.

        Args:
            losses: dict mapping task name -> loss tensor.
            model: the model.

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

        for i, (_name, loss_val) in enumerate(losses.items()):
            # Ensure we get a scalar for autograd — sum over all dimensions
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
