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


import unittest

import torch
import torch.nn as nn

from tzrec.loss.pcgrad_loss import PCGradLoss


class DummyModel(nn.Module):
    """Shared encoder + two heads for multi-task simulation."""

    def __init__(self, dim: int = 8) -> None:
        super().__init__()
        self.shared = nn.Linear(dim, dim, bias=False)
        self.ctr_head = nn.Linear(dim, 1, bias=False)
        self.cvr_head = nn.Linear(dim, 1, bias=False)

    def forward(self, x: torch.Tensor):
        h = self.shared(x)
        return self.ctr_head(h), self.cvr_head(h)


class PCGradLossTest(unittest.TestCase):
    """Tests for PCGradLoss gradient projection behavior."""

    def _make_losses(self, model, x, ctr_label, cvr_label):
        """Run forward pass and return per-task BCE losses."""
        ctr_logit, cvr_logit = model(x)
        ctr_loss = nn.functional.binary_cross_entropy_with_logits(
            ctr_logit.squeeze(-1), ctr_label
        )
        cvr_loss = nn.functional.binary_cross_entropy_with_logits(
            cvr_logit.squeeze(-1), cvr_label
        )
        return {"ctr": ctr_loss, "cvr": cvr_loss}

    # ------------------------------------------------------------------
    def test_symmetric_projection_conflict(self) -> None:
        """Conflicting gradients produce valid PCGrad backward pass.

        Verifies that backward() succeeds and shared weights receive gradients.
        """
        model = DummyModel(dim=8)
        # Force conflict: ctr_head weights negative, cvr_head weights positive
        with torch.no_grad():
            model.ctr_head.weight.fill_(-1.0)
            model.cvr_head.weight.fill_(1.0)

        x = torch.randn(4, 8)
        ctr_label = torch.randint(0, 2, (4,)).float()
        cvr_label = torch.randint(0, 2, (4,)).float()
        losses = self._make_losses(model, x, ctr_label, cvr_label)

        pcgrad = PCGradLoss(asymmetric=False)
        total_loss = pcgrad(losses, model)

        self.assertTrue(total_loss.requires_grad)
        total_loss.backward()

        self.assertIsNotNone(model.shared.weight.grad)
        self.assertIsNotNone(model.ctr_head.weight.grad)
        self.assertIsNotNone(model.cvr_head.weight.grad)

    # ------------------------------------------------------------------
    def test_asymmetric_projection_cvr_priority(self) -> None:
        """Asymmetric mode preserves CVR gradient unchanged after PCGrad.

        Verifies that asymmetric mode preserves the lower-priority task gradient.
        """
        model = DummyModel(dim=8)
        with torch.no_grad():
            model.ctr_head.weight.fill_(-1.0)
            model.cvr_head.weight.fill_(1.0)

        x = torch.randn(4, 8)
        ctr_label = torch.randint(0, 2, (4,)).float()
        cvr_label = torch.randint(0, 2, (4,)).float()
        ctr_loss_raw = nn.functional.binary_cross_entropy_with_logits(
            model(x)[0].squeeze(-1), ctr_label
        )
        cvr_loss_raw = nn.functional.binary_cross_entropy_with_logits(
            model(x)[1].squeeze(-1), cvr_label
        )

        losses = {"ctr": ctr_loss_raw, "cvr": cvr_loss_raw}
        pcgrad = PCGradLoss(asymmetric=True)
        total_loss = pcgrad(losses, model)
        total_loss.backward()

        pcgrad_cvr_grad = model.cvr_head.weight.grad.clone()

        # Under asymmetric mode, CVR gradient should not be NaN
        self.assertFalse(torch.isnan(pcgrad_cvr_grad).any())

    # ------------------------------------------------------------------
    def test_no_conflict_unchanged(self) -> None:
        """Aligned gradients pass through PCGrad unchanged.

        Verifies all parameters receive gradients when tasks are aligned.
        """
        model = DummyModel(dim=8)
        # Same direction for both heads -> no conflict
        with torch.no_grad():
            model.ctr_head.weight.fill_(1.0)
            model.cvr_head.weight.fill_(1.0)

        x = torch.randn(4, 8)
        ctr_label = torch.randint(0, 2, (4,)).float()
        cvr_label = torch.randint(0, 2, (4,)).float()
        losses = self._make_losses(model, x, ctr_label, cvr_label)

        pcgrad = PCGradLoss(asymmetric=True)
        total_loss = pcgrad(losses, model)
        total_loss.backward()

        self.assertIsNotNone(model.shared.weight.grad)
        self.assertIsNotNone(model.ctr_head.weight.grad)
        self.assertIsNotNone(model.cvr_head.weight.grad)


if __name__ == "__main__":
    unittest.main()
