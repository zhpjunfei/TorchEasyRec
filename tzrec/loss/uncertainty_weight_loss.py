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
from typing import Dict, List

import torch


class UncertaintyWeightLoss(torch.nn.Module):
    """Uncertainty Weighting for multi-task learning.

    Based on "Multi-Task Learning Using Uncertainty to Weigh Losses
    for Scene Geometry and Semantics" (Kendall et al., CVPR 2018).

    Each task's loss is weighted by 1 / (2 * exp(log_var)),
    with a log_var regularization term to prevent degenerate solutions.
    """

    def __init__(self, num_tasks: int, init_log_vars: List[float] = None) -> None:
        super().__init__()
        if init_log_vars is None:
            init_log_vars = [0.0] * num_tasks
        self.log_vars = torch.nn.Parameter(torch.tensor(init_log_vars))

    def forward(self, losses: Dict[str, torch.Tensor]) -> torch.Tensor:
        """Compute uncertainty-weighted total loss.

        Args:
            losses (dict): a dict of per-task loss tensors (scalars).

        Returns:
            total_loss (Tensor): uncertainty-weighted sum of task losses.
        """
        total_loss = 0.0
        for i, (name, loss) in enumerate(losses.items()):
            total_loss = (
                total_loss
                + loss / (2.0 * torch.exp(self.log_vars[i]))
                + self.log_vars[i] / 2.0
            )
        return total_loss
