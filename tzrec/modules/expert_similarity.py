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

"""Expert similarity monitoring utilities for multi-task learning.

Provides functionality to compute and monitor pairwise cosine similarity
between experts in mixture-of-experts architectures (MMoE, PLE, DBMTL).

Usage:
    # Create a monitor
    monitor = create_expert_sim_monitor("mmoe", summary_writer=None)

    # Register it on an MMoE module
    mmoe_module.register_expert_sim_callback(monitor.callback, global_step=0)

    # During training, periodically call:
    similarities = mmoe_module.compute_and_log_expert_sim(global_step)
"""

from typing import Dict, Optional

import torch
from torch import nn
from torch.utils.tensorboard import SummaryWriter


def compute_pairwise_cosine_similarity(
    stacked_outputs: torch.Tensor,
    eps: float = 1e-8,
) -> torch.Tensor:
    """Compute pairwise cosine similarity between experts.

    Args:
        stacked_outputs: Stacked expert outputs [num_experts, batch, features]
                         or [num_experts, features].
        eps: Numerical stability constant for normalization.

    Returns:
        Similarity matrix of shape [num_experts, num_experts] with diagonal=1.0.
        - ~1.0: Experts are nearly identical (possible collapse)
        - ~0.0: Experts are uncorrelated
        - < 0:  Experts are anti-correlated

    Example:
        >>> # After stacking expert outputs: [4, 32, 256]
        >>> sims = compute_pairwise_cosine_similarity(expert_feas)
        >>> # sims shape: [4, 4], sims[i,j] = cosine_sim(expert_i, expert_j)
    """
    # Average over batch dimension to get per-expert representation
    if stacked_outputs.dim() == 3:
        expert_avg = stacked_outputs.mean(dim=1)  # [num_experts, features]
    else:
        expert_avg = stacked_outputs  # [num_experts, features]

    # Normalize for cosine similarity
    norms = expert_avg.norm(p=2, dim=1, keepdim=True).clamp(min=eps)
    normalized = expert_avg / norms

    # Pairwise cosine similarity: [n, d] @ [d, n] = [n, n]
    sim_matrix = normalized @ normalized.t()
    return sim_matrix


class ExpertSimMonitor:
    """Monitors pairwise expert similarity over training.

    Attributes:
        prefix: Prefix for TensorBoard log keys.
        on_step: Log interval in steps.
        enabled: Whether monitoring is active.
        summary_writer: TensorBoard writer (set externally before training).
    """

    def __init__(
        self,
        prefix: str = "expert_sim",
        on_step: int = 100,
        enabled: bool = True,
    ) -> None:
        self.prefix = prefix
        self.on_step = on_step
        self.enabled = enabled
        self._last_expert_output: Optional[torch.Tensor] = None
        self._last_step: int = -1
        self.summary_writer: Optional[SummaryWriter] = None

    def _callback_impl(
        self,
        expert_feas: torch.Tensor,
        step: int,
    ) -> None:
        """Internal callback invoked by MMoE.forward().

        Args:
            expert_feas: Stacked expert outputs [num_experts, batch, features].
            step: Current training step.
        """
        if not self.enabled:
            return
        if step != self._last_step and step % self.on_step == 0:
            try:
                sim_matrix = compute_pairwise_cosine_similarity(expert_feas.detach())
                num_experts = sim_matrix.size(0)
                diag = sim_matrix.diag()
                off_diag = sim_matrix - diag

                if self.summary_writer:
                    self.summary_writer.add_scalar(
                        f"{self.prefix}/max_pairwise", off_diag.abs().max().item(), step
                    )
                    self.summary_writer.add_scalar(
                        f"{self.prefix}/avg_pairwise",
                        off_diag.sum().item() / (num_experts * (num_experts - 1)),
                        step,
                    )
                    self.summary_writer.add_scalar(
                        f"{self.prefix}/diag_std", diag.std().item(), step
                    )

                    # Individual pairs (only for <= 10 experts)
                    if num_experts <= 10:
                        for i in range(num_experts):
                            for j in range(i + 1, num_experts):
                                self.summary_writer.add_scalar(
                                    f"{self.prefix}/pair_e{i}_vs_e{j}",
                                    sim_matrix[i, j].item(),
                                    step,
                                )
            except Exception:
                # Fail gracefully - don't break training
                pass
            self._last_step = step

    def callback(
        self,
        expert_feas: torch.Tensor,
        step: int,
    ) -> None:
        """Callable registered with MMoE for expert similarity monitoring."""
        self._callback_impl(expert_feas, step)


def register_expert_sim(
    mmoe_module: nn.Module,
    monitor: ExpertSimMonitor,
    expert_key: str = "mmoe",
) -> None:
    """Register an ExpertSimMonitor on an MMoE module.

    Args:
        mmoe_module: The MMoE instance (or subclass) to monitor.
        monitor: An ExpertSimMonitor instance with summary_writer set.
        expert_key: Key name for storing last expert output in the module.
    """
    if hasattr(mmoe_module, "register_expert_sim_callback"):
        mmoe_module.register_expert_sim_callback(monitor.callback)
    elif hasattr(mmoe_module, "_expert_sim_callback"):
        # Already configured
        pass
    else:
        raise ValueError(
            f"Module '{type(mmoe_module).__name__}' does not support "
            "expert similarity monitoring. Is it an MMoE subclass?"
        )

    # Also set up compute method
    mmoe_module.register_expert_sim_monitor = monitor
    mmoe_module._expert_sim_key = expert_key


def compute_expert_similarity_from_stacked(
    stacked: torch.Tensor,
    prefix: str = "expert_sim",
    step: int = 0,
    summary_writer: Optional[SummaryWriter] = None,
) -> Optional[Dict[str, float]]:
    """Compute and optionally log expert similarity from stacked outputs.

    This is a convenience function for use outside the MMoE forward pass,
    e.g., for monitoring gradient-based expert similarity.

    Args:
        stacked: Expert outputs [num_experts, batch, features] or
                [num_experts, features].
        prefix: Key prefix for logged metrics.
        step: Training step for TensorBoard.
        summary_writer: Optional TensorBoard writer.

    Returns:
        Dict of metric_name -> value, or None if computation failed.
    """
    try:
        sim = compute_pairwise_cosine_similarity(stacked)
        num_experts = sim.size(0)
        diag = sim.diag()
        off_diag = sim - diag.diag()

        metrics = {
            f"{prefix}/max_pairwise": off_diag.abs().max().item(),
            f"{prefix}/avg_pairwise": off_diag.sum().item()
            / max(1, num_experts * (num_experts - 1)),
            f"{prefix}/diag_std": diag.std().item(),
        }

        if summary_writer:
            for k, v in metrics.items():
                summary_writer.add_scalar(k, v, step)

        return metrics
    except Exception:
        return None
