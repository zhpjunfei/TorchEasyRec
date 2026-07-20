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
from typing import Dict

import torch


class PCGradLoss(torch.nn.Module):
    """PCGrad: Project Conflicting Gradients for multi-task learning.

    Based on "Gradient Surgery for Multi-Task Learning"
    (Yu et al., NeurIPS 2020).

    For each pair of tasks with conflicting gradients (cosine similarity < 0),
    project each gradient onto the normal plane of the other, removing the
    conflicting component. The total gradient is the sum of projected gradients.
    """

    def forward(
        self, losses: Dict[str, torch.Tensor], model: torch.nn.Module
    ) -> torch.Tensor:
        """Compute PCGrad-weighted total loss.

        Args:
            losses (dict): a dict of per-task loss tensors.
            model (nn.Module): the model.

        Returns:
            total_loss (Tensor): a single loss whose backward() produces
                the PCGrad-modified gradient.
        """
        params = [p for p in model.parameters() if p.requires_grad]

        grads = []
        for loss_val in losses.values():
            single_loss = torch.sum(loss_val, dim=0)
            gradients = torch.autograd.grad(
                single_loss,
                params,
                retain_graph=True,
                allow_unused=True,
                create_graph=False,
            )
            grad_flattened = []
            for grad, param in zip(gradients, params):
                if grad is not None:
                    grad_flattened.append(grad.reshape(-1))
                else:
                    grad_flattened.append(torch.zeros_like(param).reshape(-1))
            grads.append(torch.cat(grad_flattened))

        G = torch.stack(grads)
        GGT = torch.mm(G, G.T)
        diag = GGT.diag().clamp(min=1e-8)

        eye = torch.eye(len(losses), device=GGT.device, dtype=torch.bool)
        conflict_mask = (GGT < 0) & ~eye

        penalty_ratio = GGT / diag.unsqueeze(1)
        c = 1.0 - (penalty_ratio * conflict_mask).sum(dim=1)

        total_loss = 0.0
        for i, loss_val in enumerate(losses.values()):
            total_loss = total_loss + c[i].detach() * loss_val.sum()

        return total_loss
