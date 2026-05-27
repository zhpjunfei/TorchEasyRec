import unittest

import torch

from tzrec.modules.cdot import CDOT


class CDOTTest(unittest.TestCase):
    def test_cdot_basic(self) -> None:
        num_slots = 4
        input_dim = 8
        output_dim = 4
        mid_dim = 16
        cdot = CDOT(
            num_slots=num_slots,
            input_dim=input_dim,
            output_dim=output_dim,
            mid_dim=mid_dim,
            compress_hidden_units=[32, 32],
        )
        self.assertEqual(cdot.output_dim(), num_slots * output_dim)
        batch_size = 2
        x = torch.randn(batch_size, num_slots, input_dim)
        allint_out, allint_mid_out = cdot(x)
        self.assertEqual(allint_out.size(), (batch_size, num_slots * output_dim))
        self.assertEqual(allint_mid_out.size(), (batch_size, num_slots * output_dim))

    def test_cdot_gradient_flow(self) -> None:
        cdot = CDOT(num_slots=3, input_dim=8, output_dim=4, mid_dim=8)
        x = torch.randn(2, 3, 8, requires_grad=True)
        allint_out, _ = cdot(x)
        loss = allint_out.sum()
        loss.backward()
        self.assertIsNotNone(cdot.sub_compress_weight.grad)
        self.assertIsNotNone(cdot.compress_bias.grad)
        for name, param in cdot.named_parameters():
            self.assertIsNotNone(param.grad, f"gradient missing for {name}")

    def test_cdot_default_compress(self) -> None:
        cdot = CDOT(num_slots=2, input_dim=16, output_dim=4, mid_dim=32)
        x = torch.randn(1, 2, 16)
        allint_out, allint_mid_out = cdot(x)
        self.assertEqual(allint_out.size(), (1, 8))
        self.assertEqual(allint_mid_out.size(), (1, 8))

    def test_cdot_forward_output_values(self) -> None:
        cdot = CDOT(num_slots=2, input_dim=4, output_dim=2, mid_dim=4)
        cdot.eval()
        x = torch.ones(1, 2, 4)
        allint_out, allint_mid_out = cdot(x)
        self.assertFalse(torch.isnan(allint_out).any())
        self.assertFalse(torch.isinf(allint_out).any())
        self.assertEqual(allint_out.size(1), allint_mid_out.size(1))

    def test_cdot_single_slot(self) -> None:
        cdot = CDOT(num_slots=1, input_dim=8, output_dim=4, mid_dim=16)
        x = torch.randn(3, 1, 8)
        allint_out, allint_mid_out = cdot(x)
        self.assertEqual(allint_out.size(), (3, 4))
        self.assertEqual(allint_mid_out.size(), (3, 4))


if __name__ == "__main__":
    unittest.main()
