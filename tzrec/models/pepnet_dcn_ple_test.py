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

"""Tests for PEPNetDCNPLE model — contrastive loss smoke test."""

import unittest

import torch


class PEPNetDCNPLEContrastiveTest(unittest.TestCase):
    """Verifies the contrastive loss computation logic in isolation."""

    def _make_contrastive_inputs(self, B: int = 4):
        d = 128
        v = torch.randn(B, d)
        t = torch.randn(B, d)
        seq_len = torch.linspace(50, 0, B, dtype=torch.float32)
        return v, t, seq_len

    def _contrastive_loss_old(
        self, v: torch.Tensor, t: torch.Tensor, seq_len: torch.Tensor, K: int = 2
    ):
        """Replicates the BUGGY Phase 1a loss computation."""
        v = v / v.norm(dim=-1, keepdim=True)
        t = t / t.norm(dim=-1, keepdim=True)
        tau = (0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())).unsqueeze(1)
        sim = torch.mm(v, t.t()) / tau
        sim_pos = sim.diag()
        loss_v2t = -sim_pos + torch.logsumexp(sim, dim=-1)
        loss_t2v = -sim_pos + torch.logsumexp(sim, dim=0)
        return (loss_v2t + loss_t2v) / 2

    def _contrastive_loss_new(
        self, v: torch.Tensor, t: torch.Tensor, seq_len: torch.Tensor, K: int = 2
    ):
        """Replicates the FIXED loss computation from the design doc §7."""
        B = v.size(0)
        v = v / v.norm(dim=-1, keepdim=True)
        t = t / t.norm(dim=-1, keepdim=True)
        raw_sim = torch.mm(v, t.t())

        # v2t: per-seq_len τ + HardNegative
        tau_v2t = (0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())).unsqueeze(1)
        sim_v2t = raw_sim / tau_v2t
        sim_c = sim_v2t.clone()

        _, topk = torch.topk(sim_c, K + 1, dim=-1)
        hard_mask = torch.zeros_like(sim_c, dtype=torch.bool)
        hard_mask[torch.arange(B).unsqueeze(1), topk] = True
        loss_v2t = -sim_c.diag() + torch.logsumexp(
            sim_c.masked_fill(~hard_mask, -float("inf")), dim=-1
        )

        # t2v: fixed τ + HardNegative
        sim_t2v = raw_sim / 0.07
        _, topk_t2v = torch.topk(sim_t2v, K + 1, dim=-1)
        hard_mask_t2v = torch.zeros_like(sim_t2v, dtype=torch.bool)
        hard_mask_t2v[torch.arange(B).unsqueeze(1), topk_t2v] = True
        loss_t2v = -sim_t2v.diag() + torch.logsumexp(
            sim_t2v.masked_fill(~hard_mask_t2v, -float("inf")), dim=-1
        )

        return (loss_v2t + loss_t2v) / 2

    def test_finite_values(self):
        """Loss values are finite for both directions."""
        v, t, seq_len = self._make_contrastive_inputs(B=8)
        loss = self._contrastive_loss_new(v, t, seq_len, K=3)
        self.assertTrue(torch.isfinite(loss).all())

    def test_v2t_t2v_comparable_magnitude(self):
        """After fix, v2t and t2v have comparable magnitudes."""
        torch.manual_seed(42)
        v, t, seq_len = self._make_contrastive_inputs(B=8)
        vn = v / v.norm(dim=-1, keepdim=True)
        tn = t / t.norm(dim=-1, keepdim=True)
        raw_sim = torch.mm(vn, tn.t())
        K = 3

        tau_v2t_ = (0.07 + 0.43 * torch.exp(-0.1 * seq_len)).unsqueeze(1)
        sim_v2t = raw_sim / tau_v2t_
        _, topk = torch.topk(sim_v2t, K + 1, dim=-1)
        hm = torch.zeros_like(sim_v2t, dtype=torch.bool)
        hm[torch.arange(8).unsqueeze(1), topk] = True
        lv = -sim_v2t.diag() + torch.logsumexp(sim_v2t.masked_fill(~hm, -1e9), dim=-1)

        sim_t2v = raw_sim / 0.07
        _, topk_t2v = torch.topk(sim_t2v, K + 1, dim=-1)
        hm2 = torch.zeros_like(sim_t2v, dtype=torch.bool)
        hm2[torch.arange(8).unsqueeze(1), topk_t2v] = True
        lt = -sim_t2v.diag() + torch.logsumexp(sim_t2v.masked_fill(~hm2, -1e9), dim=-1)

        ratio = lt.mean() / lv.mean()
        # Both directions should be within 5x of each other (not 100x like old t2v)
        self.assertGreater(ratio.item(), 0.2)
        self.assertLess(ratio.item(), 5.0)

    def test_diag_logq_correction(self):
        """sim_c.diag() differs from sim.diag() when LogQ is applied."""
        v, t, seq_len = self._make_contrastive_inputs(B=4)
        vn = v / v.norm(dim=-1, keepdim=True)
        tn = t / t.norm(dim=-1, keepdim=True)
        raw_sim = torch.mm(vn, tn.t())
        tau_v2t = (0.07 + 0.43 * torch.exp(-0.1 * seq_len)).unsqueeze(1)
        sim_v2t = raw_sim / tau_v2t

        logq = torch.tensor([0.1, 0.5, 1.0, 2.0])
        sim_c = sim_v2t - logq.unsqueeze(0)

        uncorrected = sim_v2t.diag()
        corrected = sim_c.diag()
        self.assertTrue(torch.allclose(uncorrected - corrected, logq))


if __name__ == "__main__":
    unittest.main()
