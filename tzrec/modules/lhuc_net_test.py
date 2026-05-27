import unittest

import torch

from tzrec.modules.lhuc_net import LHUC_EPNet, LHUC_PPNet


class LHUC_EPNetTest(unittest.TestCase):
    def test_epnet_basic(self) -> None:
        lhuc_dim = 16
        output_dim = 32
        epnet = LHUC_EPNet(
            lhuc_dim=lhuc_dim, output_dim=output_dim, hidden_units=[64]
        )
        self.assertEqual(epnet.output_dim(), output_dim)
        batch_size = 4
        lhuc_input = torch.randn(batch_size, lhuc_dim)
        scale = epnet(lhuc_input)
        self.assertEqual(scale.size(), (batch_size, output_dim))

    def test_epnet_scale_range(self) -> None:
        epnet = LHUC_EPNet(lhuc_dim=4, output_dim=8, hidden_units=[16])
        lhuc_input = torch.randn(100, 4) * 10.0
        scale = epnet(lhuc_input)
        self.assertTrue(scale.min().item() >= -4.0 - 1e-5)
        self.assertTrue(scale.max().item() <= 6.0 + 1e-5)

    def test_epnet_gradient_flow(self) -> None:
        epnet = LHUC_EPNet(lhuc_dim=8, output_dim=16, hidden_units=[32])
        lhuc_input = torch.randn(2, 8)
        scale = epnet(lhuc_input)
        loss = scale.sum()
        loss.backward()
        for name, param in epnet.named_parameters():
            self.assertIsNotNone(param.grad, f"gradient missing for {name}")

    def test_epnet_default_hidden(self) -> None:
        epnet = LHUC_EPNet(lhuc_dim=8, output_dim=16)
        self.assertEqual(epnet.gate[0].in_features, 8)
        self.assertEqual(epnet.gate[0].out_features, 256)
        self.assertEqual(epnet.gate[2].out_features, 16)

    def test_epnet_no_nan(self) -> None:
        epnet = LHUC_EPNet(lhuc_dim=4, output_dim=8)
        lhuc_input = torch.randn(4, 4)
        scale = epnet(lhuc_input)
        self.assertFalse(torch.isnan(scale).any())
        self.assertFalse(torch.isinf(scale).any())


class LHUC_PPNetTest(unittest.TestCase):
    def test_ppnet_basic(self) -> None:
        input_dim = 32
        lhuc_dim = 16
        nn_dims = [64, 32, 1]
        ppnet = LHUC_PPNet(
            input_dim=input_dim,
            lhuc_dim=lhuc_dim,
            nn_dims=nn_dims,
            nn_activation="nn.ReLU",
            lhuc_hidden_units=[32],
        )
        self.assertEqual(ppnet.output_dim(), nn_dims[-1])
        batch_size = 4
        x = torch.randn(batch_size, input_dim)
        lhuc_input = torch.randn(batch_size, lhuc_dim)
        result = ppnet(x, lhuc_input)
        self.assertEqual(result.size(), (batch_size, nn_dims[-1]))

    def test_ppnet_multi_layers(self) -> None:
        ppnet = LHUC_PPNet(
            input_dim=16,
            lhuc_dim=8,
            nn_dims=[32, 16, 8, 1],
            nn_activation="nn.ReLU",
        )
        x = torch.randn(2, 16)
        lhuc_input = torch.randn(2, 8)
        result = ppnet(x, lhuc_input)
        self.assertEqual(result.size(), (2, 1))

    def test_ppnet_gradient_flow(self) -> None:
        ppnet = LHUC_PPNet(
            input_dim=16,
            lhuc_dim=8,
            nn_dims=[32, 1],
            nn_activation="nn.ReLU",
        )
        x = torch.randn(2, 16)
        lhuc_input = torch.randn(2, 8)
        result = ppnet(x, lhuc_input)
        loss = result.sum()
        loss.backward()
        for name, param in ppnet.named_parameters():
            self.assertIsNotNone(param.grad, f"gradient missing for {name}")

    def test_ppnet_identity_activation(self) -> None:
        ppnet = LHUC_PPNet(
            input_dim=8,
            lhuc_dim=4,
            nn_dims=[16, 1],
            nn_activation="",
        )
        x = torch.randn(2, 8)
        lhuc_input = torch.randn(2, 4)
        result = ppnet(x, lhuc_input)
        self.assertEqual(result.size(), (2, 1))

    def test_ppnet_single_layer(self) -> None:
        ppnet = LHUC_PPNet(
            input_dim=8,
            lhuc_dim=4,
            nn_dims=[1],
            nn_activation="nn.ReLU",
        )
        x = torch.randn(3, 8)
        lhuc_input = torch.randn(3, 4)
        result = ppnet(x, lhuc_input)
        self.assertEqual(result.size(), (3, 1))

    def test_ppnet_forward_output_values(self) -> None:
        ppnet = LHUC_PPNet(
            input_dim=8, lhuc_dim=4, nn_dims=[16, 1], nn_activation="nn.ReLU",
        )
        ppnet.eval()
        x = torch.randn(4, 8)
        lhuc_input = torch.randn(4, 4)
        result = ppnet(x, lhuc_input)
        self.assertFalse(torch.isnan(result).any())
        self.assertFalse(torch.isinf(result).any())


if __name__ == "__main__":
    unittest.main()
