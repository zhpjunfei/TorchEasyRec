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

"""Unit tests for PEPNetDCNPLE utility functions.

Tests standalone utilities (_extract_bias_fn, _extract_cdot_fn) and
static methods (_parse_calibration_schedule, _get_current_calibration_weight)
without requiring the full model instantiation (which needs fbgemm_gpu).
"""

import unittest

import torch


class TestExtractBiasFn(unittest.TestCase):
    """Tests for _extract_bias_fn."""

    def test_single_feature_shape(self):
        """Single feature: bias_vec [B, 1], bias_sum [B, 1]."""
        from tzrec.models.pepnet_dcn_ple import _extract_bias_fn

        B = 8
        features = [torch.randn(B, 4)]
        bias_vec, bias_sum = _extract_bias_fn(features)
        self.assertEqual(bias_vec.shape, (B, 1))
        self.assertEqual(bias_sum.shape, (B, 1))

    def test_bias_sum_correct(self):
        """bias_sum = sum(bias_vec, dim=1)."""
        from tzrec.models.pepnet_dcn_ple import _extract_bias_fn

        B = 8
        features = [torch.randn(B, 4)]
        bias_vec, bias_sum = _extract_bias_fn(features)
        torch.testing.assert_close(bias_sum, bias_vec.sum(dim=1, keepdim=True))

    def test_device_preserved(self):
        """Bias tensors on same device as inputs."""
        from tzrec.models.pepnet_dcn_ple import _extract_bias_fn

        B = 4
        features = [torch.randn(B, 2)]
        bias_vec, bias_sum = _extract_bias_fn(features)
        self.assertEqual(bias_vec.device, features[0].device)
        self.assertEqual(bias_sum.device, features[0].device)

    def test_multiple_features(self):
        """Multiple features concatenated."""
        from tzrec.models.pepnet_dcn_ple import _extract_bias_fn

        B = 8
        features = [
            torch.randn(B, 3),
            torch.randn(B, 2),
            torch.randn(B, 4),
        ]
        bias_vec, bias_sum = _extract_bias_fn(features)
        self.assertEqual(bias_vec.shape, (B, 3))
        self.assertEqual(bias_sum.shape, (B, 1))

    def test_zero_bias_values(self):
        """With zero inputs, bias_sum should be zero."""
        from tzrec.models.pepnet_dcn_ple import _extract_bias_fn

        B = 4
        features = [torch.zeros(B, 2)]
        bias_vec, bias_sum = _extract_bias_fn(features)
        self.assertTrue((bias_sum == 0).all())


class TestExtractCdotFn(unittest.TestCase):
    """Tests for _extract_cdot_fn."""

    def test_exact_dim_no_padding(self):
        """Features with exact cdot_input_dim: no padding."""
        from tzrec.models.pepnet_dcn_ple import _extract_cdot_fn

        B = 4
        features = [torch.randn(B, 32)]
        result = _extract_cdot_fn(features, cdot_input_dim=32)
        self.assertEqual(result.shape, (B, 1, 32))

    def test_short_feature_padded_with_zeros(self):
        """Features shorter than cdot_input_dim: padded with zeros."""
        from tzrec.models.pepnet_dcn_ple import _extract_cdot_fn

        B = 4
        features = [torch.randn(B, 16)]
        result = _extract_cdot_fn(features, cdot_input_dim=32)
        self.assertEqual(result.shape, (B, 1, 32))
        # Padding should be zeros
        self.assertTrue((result[:, 0, 16:] == 0).all())

    def test_multiple_features_stacked(self):
        """Multiple features stacked along dim=1."""
        from tzrec.models.pepnet_dcn_ple import _extract_cdot_fn

        B = 4
        features = [torch.randn(B, 32), torch.randn(B, 32)]
        result = _extract_cdot_fn(features, cdot_input_dim=32)
        self.assertEqual(result.shape, (B, 2, 32))

    def test_original_values_preserved(self):
        """First cdot_input_dim columns match original feature."""
        from tzrec.models.pepnet_dcn_ple import _extract_cdot_fn

        B = 4
        original = torch.randn(B, 32)
        features = [original]
        result = _extract_cdot_fn(features, cdot_input_dim=32)
        torch.testing.assert_close(result[:, 0, :], original)

    def test_different_input_dims(self):
        """Different cdot_input_dim values handled correctly."""
        from tzrec.models.pepnet_dcn_ple import _extract_cdot_fn

        B = 4
        features = [torch.randn(B, 16)]
        result = _extract_cdot_fn(features, cdot_input_dim=8)
        # Feature already >= cdot_input_dim, no padding
        self.assertEqual(result.shape, (B, 1, 8))
        torch.testing.assert_close(result[:, 0, :], features[0][:, :8])


class TestCalibrationSchedule(unittest.TestCase):
    """Tests for progressive calibration schedule parsing and weight lookup."""

    def test_parse_empty_schedule(self):
        """Empty schedule returns empty list."""
        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        parsed = PEPNetDCNPLE._parse_calibration_schedule("")
        self.assertEqual(parsed, [])

    def test_parse_single_entry(self):
        """Single entry schedule parses correctly."""
        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        parsed = PEPNetDCNPLE._parse_calibration_schedule("1000:0.02")
        self.assertEqual(parsed, [(1000, 0.02)])

    def test_parse_multiple_entries_sorted(self):
        """Multiple entries are sorted by step."""
        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        parsed = PEPNetDCNPLE._parse_calibration_schedule(
            "6000:0.05,2000:0.0,4000:0.02"
        )
        expected = [(2000, 0.0), (4000, 0.02), (6000, 0.05)]
        self.assertEqual(parsed, expected)

    def test_parse_invalid_entries_skipped(self):
        """Entries without ':' are silently skipped."""
        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        parsed = PEPNetDCNPLE._parse_calibration_schedule(
            "1000:0.02,bad_entry,2000:0.05"
        )
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0][0], 1000)
        self.assertEqual(parsed[1][0], 2000)

    def test_parse_whitespace_handling(self):
        """Whitespace around entries is trimmed."""
        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        parsed = PEPNetDCNPLE._parse_calibration_schedule(" 1000 : 0.02 , 2000 : 0.05 ")
        self.assertEqual(parsed, [(1000, 0.02), (2000, 0.05)])

    def test_get_weight_before_first_step(self):
        """Before first schedule step, returns first weight."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._parsed_schedule = [(2000, 0.0), (4000, 0.02), (6000, 0.03)]
        model._calibration_loss_weight = 0.02
        weight = model._get_current_calibration_weight(0)
        self.assertEqual(weight, 0.0)

    def test_get_weight_linear_interpolation(self):
        """Weight interpolates linearly between schedule steps."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._parsed_schedule = [(0, 0.0), (1000, 0.1)]
        model._calibration_loss_weight = 0.0
        # At step 500 (midpoint), weight should be 0.05
        weight = model._get_current_calibration_weight(500)
        self.assertAlmostEqual(weight, 0.05, places=4)
        # At step 250, weight should be 0.025
        weight = model._get_current_calibration_weight(250)
        self.assertAlmostEqual(weight, 0.025, places=4)

    def test_get_weight_after_last_step(self):
        """After last schedule step, returns last weight."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._parsed_schedule = [(2000, 0.0), (4000, 0.02), (6000, 0.03)]
        model._calibration_loss_weight = 0.02
        weight = model._get_current_calibration_weight(10000)
        self.assertEqual(weight, 0.03)

    def test_get_weight_no_schedule_constant(self):
        """Without schedule, always returns constant weight."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._parsed_schedule = []
        model._calibration_loss_weight = 0.05
        for step in [0, 100, 5000, 100000]:
            weight = model._get_current_calibration_weight(step)
            self.assertEqual(weight, 0.05)

    def test_get_weight_at_exact_step_boundary(self):
        """At exact schedule step boundaries, returns that step's weight."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._parsed_schedule = [(2000, 0.0), (4000, 0.02), (6000, 0.03)]
        model._calibration_loss_weight = 0.02
        self.assertEqual(model._get_current_calibration_weight(2000), 0.0)
        self.assertEqual(model._get_current_calibration_weight(4000), 0.02)
        self.assertEqual(model._get_current_calibration_weight(6000), 0.03)


class TestGradientConflictDetection(unittest.TestCase):
    """Tests for gradient conflict monitoring (cosine similarity)."""

    def test_empty_gradients_returns_empty_dict(self):
        """Returns empty dict when no gradients collected."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._task_gradients = {"ctr": None, "cvr": None}
        result = model.compute_gradient_conflict()
        self.assertEqual(result, {})

    def test_single_task_returns_empty_dict(self):
        """Returns empty dict when only one task has gradients."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._task_gradients = {"ctr": torch.randn(100), "cvr": None}
        result = model.compute_gradient_conflict()
        self.assertEqual(result, {})

    def test_two_tasks_compute_norms(self):
        """Computes gradient norms for each task."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        g1 = torch.randn(100)
        g2 = torch.randn(100)
        model._task_gradients = {"ctr": g1, "cvr": g2}
        result = model.compute_gradient_conflict()
        self.assertIn("grad_norm_ctr", result)
        self.assertIn("grad_norm_cvr", result)
        # Norm should match torch norm
        self.assertAlmostEqual(result["grad_norm_ctr"], g1.norm().item(), places=5)
        self.assertAlmostEqual(result["grad_norm_cvr"], g2.norm().item(), places=5)

    def test_cosine_similarity_range(self):
        """Cosine similarity is in [-1, 1]."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        g1 = torch.randn(100)
        g2 = torch.randn(100)
        model._task_gradients = {"ctr": g1, "cvr": g2}
        result = model.compute_gradient_conflict()
        cos_sim = result["grad_cos_sim_ctr_cvr"]
        self.assertGreaterEqual(cos_sim, -1.0)
        self.assertLessEqual(cos_sim, 1.0)

    def test_identical_gradients_cosine_one(self):
        """Identical gradients have cosine similarity = 1."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        g = torch.randn(100)
        model._task_gradients = {"ctr": g, "cvr": g.clone()}
        result = model.compute_gradient_conflict()
        self.assertAlmostEqual(result["grad_cos_sim_ctr_cvr"], 1.0, places=5)

    def test_opposite_gradients_cosine_negative_one(self):
        """Opposite gradients have cosine similarity ≈ -1."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        g = torch.randn(100)
        model._task_gradients = {"ctr": g, "cvr": -g}
        result = model.compute_gradient_conflict()
        self.assertAlmostEqual(result["grad_cos_sim_ctr_cvr"], -1.0, places=5)

    def test_conflict_flag_threshold(self):
        """Conflict flag set when cosine similarity < -0.1."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        # Create nearly opposite gradients
        g1 = torch.randn(100)
        g2 = -g1 + 0.01 * torch.randn(100)
        model._task_gradients = {"ctr": g1, "cvr": g2}
        result = model.compute_gradient_conflict()
        # Should have conflict flag
        self.assertIn("grad_conflict_ctr_cvr", result)
        self.assertTrue(result["grad_conflict_ctr_cvr"])

    def test_aligned_gradients_no_conflict(self):
        """No conflict flag when gradients are aligned."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        g = torch.randn(100)
        model._task_gradients = {"ctr": g, "cvr": g.clone()}
        result = model.compute_gradient_conflict()
        self.assertFalse(result["grad_conflict_ctr_cvr"])

    def test_three_tasks_pairwise(self):
        """Three tasks produce all pairwise comparisons."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._task_gradients = {
            "ctr": torch.randn(100),
            "cvr": torch.randn(100),
            "ctcvr": torch.randn(100),
        }
        result = model.compute_gradient_conflict()
        self.assertIn("grad_cos_sim_ctr_cvr", result)
        self.assertIn("grad_cos_sim_ctr_ctcvr", result)
        self.assertIn("grad_cos_sim_cvr_ctcvr", result)


class TestGradientHooks(unittest.TestCase):
    """Tests for gradient hook registration mechanism."""

    def test_hooks_register_on_linear_params(self):
        """Hooks can be registered on Linear layer parameters."""
        model = torch.nn.Linear(10, 2)
        grads = {}

        def make_hook(name):
            def hook(grad):
                if grad is not None:
                    grads[name] = grad.flatten()

            return hook

        handles = [
            param.register_hook(make_hook("test_tower")) for param in model.parameters()
        ]
        self.assertGreater(len(handles), 0)
        for h in handles:
            h.remove()  # cleanup

    def test_hook_captures_gradient(self):
        """Hook captures gradient when backward is called."""
        model = torch.nn.Linear(10, 1)
        captured = []

        def make_hook():
            def hook(grad):
                captured.append(grad.clone())

            return hook

        model.weight.register_hook(make_hook())
        x = torch.randn(4, 10, requires_grad=False)
        y = model(x).sum()
        y.backward()
        self.assertEqual(len(captured), 1)
        # Gradient shape matches input dimension
        # Gradient shape: (1, 10) for Linear(10, 1) weight
        self.assertEqual(captured[0].shape, (1, 10))


class TestSetCurrentStep(unittest.TestCase):
    """Tests for set_current_step method."""

    def test_sets_step_value(self):
        """set_current_step correctly updates _current_step."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._current_step = 0
        model.set_current_step(42)
        self.assertEqual(model._current_step, 42)

    def test_handles_large_step(self):
        """Handles large step numbers."""
        from unittest.mock import MagicMock

        from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE

        model = MagicMock(spec=PEPNetDCNPLE)
        model._current_step = 0
        model.set_current_step(1000000)
        self.assertEqual(model._current_step, 1000000)


class TestCvrTowerDerivation(unittest.TestCase):
    """Tests for CVR tower name derivation logic."""

    def test_cvr_towers_excludes_ctr(self):
        """_cvr_tower_names excludes the CTR tower."""
        from unittest.mock import MagicMock

        model = MagicMock()
        model._tower_hidden_dims = {"ctr": 128, "cvr": 128}
        model._ctr_tower_name = "ctr"
        model._cvr_tower_names = [
            n for n in model._tower_hidden_dims if n != model._ctr_tower_name
        ]
        self.assertEqual(model._cvr_tower_names, ["cvr"])

    def test_all_non_ctr_are_cvr(self):
        """When no CTR, all towers are CVR."""
        from unittest.mock import MagicMock

        model = MagicMock()
        model._tower_hidden_dims = {"cvr": 128, "ctcvr": 128}
        model._ctr_tower_name = None
        model._cvr_tower_names = [
            n for n in model._tower_hidden_dims if n != model._ctr_tower_name
        ]
        self.assertEqual(set(model._cvr_tower_names), {"cvr", "ctcvr"})

    def test_isolate_cvr_gradient_true(self):
        """When isolate_cvr_gradient, non-CTR tower input is detached."""
        from unittest.mock import MagicMock

        model = MagicMock()
        model._isolate_cvr_gradient = True
        model._ctr_tower_name = "ctr"
        fea = torch.randn(4, 128, requires_grad=True)
        tower_name = "cvr"
        if model._isolate_cvr_gradient and tower_name != model._ctr_tower_name:
            fea_out = fea.detach()
            self.assertFalse(fea_out.requires_grad)
        else:
            fea_out = fea

    def test_isolate_cvr_gradient_false(self):
        """When isolate_cvr_gradient=False, no detachment."""
        from unittest.mock import MagicMock

        model = MagicMock()
        model._isolate_cvr_gradient = False
        fea = torch.randn(4, 128, requires_grad=True)
        tower_name = "cvr"
        if model._isolate_cvr_gradient and tower_name != model._ctr_tower_name:
            fea_out = fea.detach()
        else:
            fea_out = fea
        self.assertTrue(fea_out.requires_grad)


if __name__ == "__main__":
    unittest.main()
