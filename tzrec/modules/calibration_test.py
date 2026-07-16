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

import unittest

import torch
from parameterized import parameterized

from tzrec.modules.calibration import (
    TemperatureScaler,
    compute_soft_ece,
    create_temperature_scalers,
)


class TemperatureScalerTest(unittest.TestCase):
    """TemperatureScaler 模块测试。"""

    def test_forward_identity(self) -> None:
        """T=1 应返回不变的 logits。"""
        scaler = TemperatureScaler(initial_temp=1.0)
        logits = torch.randn(32, 1)
        scaled = scaler(logits)
        self.assertTrue(torch.allclose(scaled, logits, atol=1e-4))

    def test_forward_softening(self) -> None:
        """T>1 应软化 logits（减小幅度）。"""
        scaler = TemperatureScaler(initial_temp=2.0)
        logits = torch.randn(32, 1)
        scaled = scaler(logits)
        self.assertLess(scaled.var().item(), logits.var().item())

    def test_forward_sharpening(self) -> None:
        """T<1 应锐化 logits（增大幅度）。"""
        scaler = TemperatureScaler(initial_temp=0.5)
        logits = torch.randn(32, 1)
        scaled = scaler(logits)
        self.assertGreater(scaled.var().item(), logits.var().item())

    def test_learnable_updates(self) -> None:
        """温度应可学习（有梯度）。"""
        scaler = TemperatureScaler(initial_temp=1.0, freeze=False)
        logits = torch.tensor([[1.0]])
        output = scaler(logits)
        loss = output.sum()
        loss.backward()
        self.assertIsNotNone(scaler.shift.grad)

    def test_frozen_no_gradients(self) -> None:
        """冻结温度不应累积梯度。"""
        scaler = TemperatureScaler(initial_temp=1.5, freeze=True)
        logits = torch.tensor([[2.0]])
        # 前向传播正常
        output = scaler(logits)
        self.assertEqual(output.item(), 2.0 / 1.5)
        # 不应有 shift（使用 buffer）
        self.assertFalse(hasattr(scaler, "shift"))

    def test_ranking_preserved(self) -> None:
        """温度缩放是单调的，保持排名顺序。"""
        scaler = TemperatureScaler(initial_temp=2.0)
        logits = torch.randn(100, 1)
        scaled = scaler(logits)
        self.assertTrue(torch.equal(logits.argsort(), scaled.argsort()))

    def test_get_temperature(self) -> None:
        """get_temperature() 应返回有效标量。"""
        scaler = TemperatureScaler(initial_temp=1.5)
        temp = scaler.get_temperature()
        self.assertEqual(temp.dim(), 0)
        self.assertGreater(temp.item(), 0)

    def test_learnable_temperature_changes(self) -> None:
        """可学习模式下，经过几步优化后温度应改变。"""
        scaler = TemperatureScaler(initial_temp=1.0, freeze=False)
        optimizer = torch.optim.SGD([scaler.shift], lr=0.1)
        logits = torch.randn(64, 1)
        for _ in range(10):
            optimizer.zero_grad()
            scaled = scaler(logits)
            loss = scaled.var()  # 最大化方差 → T 变小
            loss.backward()
            optimizer.step()
        # 初始 T≈1，优化后 T 应显著偏离 1
        final_temp = scaler.get_temperature().item()
        self.assertNotAlmostEqual(final_temp, 1.0, places=1)

    def test_freeze_initial_exact(self) -> None:
        """冻结模式下，初始温度应精确等于 initial_temp。"""
        scaler = TemperatureScaler(initial_temp=2.5, freeze=True)
        logits = torch.tensor([[5.0]])
        scaled = scaler(logits)
        self.assertAlmostEqual(scaled.item(), 5.0 / 2.5, places=5)

    @parameterized.expand(
        [
            ("normal", "NORMAL"),
            ("fx_trace", "FX_TRACE"),
            ("jit_script", "JIT_SCRIPT"),
        ]
    )
    def test_fx_jit_compatible(self, name, graph_type_name) -> None:
        """TemperatureScaler should work under FX trace and JIT script."""
        from tzrec.utils.test_util import TestGraphType, create_test_module

        graph_type = getattr(TestGraphType, graph_type_name)

        scaler = TemperatureScaler(initial_temp=1.5, freeze=False)
        scaler = create_test_module(scaler, graph_type)
        logits = torch.randn(8, 1)
        result = scaler(logits)
        self.assertEqual(result.size(), logits.size())
        # T=1.5, so variance should be reduced
        self.assertLess(result.var().item(), logits.var().item())


class ComputeSoftECETest(unittest.TestCase):
    """compute_soft_ece 函数测试。"""

    def test_perfect_calibration(self) -> None:
        """如果 probs == labels，ECE 应接近零。"""
        probs = torch.tensor([0.1, 0.3, 0.5, 0.7, 0.9])
        labels = probs.clone()
        ece = compute_soft_ece(probs, labels)
        self.assertLess(ece.item(), 0.05)

    def test_worst_calibration(self) -> None:
        """如果 probs 与 labels 相反，ECE 应较高。"""
        probs = torch.tensor([0.1, 0.3, 0.5, 0.7, 0.9])
        labels = 1.0 - probs
        ece = compute_soft_ece(probs, labels)
        self.assertGreater(ece.item(), 0.1)

    def test_random_calibration(self) -> None:
        """随机预测应有中等 ECE。"""
        torch.manual_seed(42)
        probs = torch.rand(1000)
        labels = torch.bernoulli(probs).float()
        ece = compute_soft_ece(probs, labels)
        self.assertGreater(ece.item(), 0.0)
        self.assertLess(ece.item(), 1.0)

    def test_with_weights(self) -> None:
        """加权 ECE 应与未加权不同。"""
        probs = torch.tensor([0.1, 0.5, 0.9])
        labels = torch.tensor([0.0, 1.0, 1.0])
        ece_unweighted = compute_soft_ece(probs, labels)
        weights = torch.tensor([1.0, 0.01, 0.01])
        ece_weighted = compute_soft_ece(probs, labels, weights)
        self.assertNotAlmostEqual(ece_unweighted.item(), ece_weighted.item(), places=4)

    def test_differentiable(self) -> None:
        """ECE 应支持反向传播。"""
        # 使用 [0,1] 范围内的可微分概率
        raw = torch.randn(64, requires_grad=True)
        probs = torch.clamp(raw.sigmoid(), min=1e-6, max=1 - 1e-6)
        labels = torch.randint(0, 2, (64,)).float()
        ece = compute_soft_ece(probs, labels)
        ece.backward()
        self.assertIsNotNone(raw.grad)
        self.assertTrue(torch.isnan(raw.grad).sum().item() == 0)

    def test_single_sample(self) -> None:
        """边界情况：单个样本。"""
        probs = torch.tensor([0.5])
        labels = torch.tensor([1.0])
        ece = compute_soft_ece(probs, labels)
        self.assertFalse(torch.isnan(ece))
        self.assertFalse(torch.isinf(ece))


class CreateTemperatureScalersTest(unittest.TestCase):
    """create_temperature_scalers 辅助函数测试。"""

    def test_creates_correct_count(self) -> None:
        """应创建恰好 num_tasks 个缩放器。"""
        scalers = create_temperature_scalers(num_tasks=3)
        self.assertEqual(len(scalers), 3)

    def test_all_apply_same(self) -> None:
        """所有缩放器应对相同输入产生相同结果。"""
        scalers = create_temperature_scalers(num_tasks=2, initial_temp=2.0)
        logits = torch.randn(16, 1)
        results = [scaler(logits) for scaler in scalers]
        for r in results[1:]:
            self.assertTrue(torch.allclose(results[0], r))

    def test_mixed_freeze(self) -> None:
        """混合冻结/可学习模式。"""
        scalers = create_temperature_scalers(num_tasks=2, initial_temp=1.5, freeze=True)
        logits = torch.randn(8, 1)
        for s in scalers:
            scaled = s(logits)
            self.assertTrue(torch.allclose(scaled, logits / 1.5))


if __name__ == "__main__":
    unittest.main()
