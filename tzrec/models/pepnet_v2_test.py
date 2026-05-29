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

"""Tests for PEPNet_v2 model."""

import unittest

import torch
from torchrec import KeyedJaggedTensor, KeyedTensor

from tzrec.datasets.utils import BASE_DATA_GROUP, Batch
from tzrec.features.feature import create_features
from tzrec.models.pepnet_v2 import PEPNet_v2
from tzrec.protos import feature_pb2, loss_pb2, model_pb2, module_pb2, tower_pb2
from tzrec.protos.models import multi_task_rank_pb2
from tzrec.utils.state_dict_util import init_parameters


class PEPNet_v2Test(unittest.TestCase):
    def _run_test(self, use_cdot=False, use_dcnv2=False):
        feature_cfgs = [
            feature_pb2.FeatureConfig(
                id_feature=feature_pb2.IdFeature(
                    feature_name="cat_a", embedding_dim=16, num_buckets=100
                )
            ),
            feature_pb2.FeatureConfig(
                id_feature=feature_pb2.IdFeature(
                    feature_name="cat_b", embedding_dim=8, num_buckets=1000
                )
            ),
            feature_pb2.FeatureConfig(
                raw_feature=feature_pb2.RawFeature(feature_name="int_a")
            ),
        ]
        feature_groups = [
            model_pb2.FeatureGroupConfig(
                group_name="all",
                feature_names=["cat_a", "cat_b", "int_a"],
                group_type=model_pb2.FeatureGroupType.DEEP,
            ),
        ]
        feature_cfgs.append(
            feature_pb2.FeatureConfig(
                id_feature=feature_pb2.IdFeature(
                    feature_name="domainf", embedding_dim=16, num_buckets=3
                )
            )
        )
        feature_groups.append(
            model_pb2.FeatureGroupConfig(
                group_name="domain",
                feature_names=["domainf"],
                group_type=model_pb2.FeatureGroupType.DEEP,
            )
        )

        features = create_features(feature_cfgs)

        pepnet_v2_config = multi_task_rank_pb2.PEPNet_v2(
            epnet_hidden_unit=8,
            ppnet_hidden_units=[8, 4],
            bias_group_name="all",
            lhuc_group_name="domain",
            task_towers=[
                tower_pb2.TaskTower(
                    tower_name="ctr",
                    label_name="label1",
                    mlp=module_pb2.MLP(hidden_units=[8, 4]),
                    losses=[
                        loss_pb2.LossConfig(
                            binary_cross_entropy=loss_pb2.BinaryCrossEntropy()
                        )
                    ],
                ),
                tower_pb2.TaskTower(
                    tower_name="cvr",
                    label_name="label2",
                    mlp=module_pb2.MLP(hidden_units=[8, 4]),
                    losses=[
                        loss_pb2.LossConfig(
                            binary_cross_entropy=loss_pb2.BinaryCrossEntropy()
                        )
                    ],
                    task_space_indicator_label="label1",
                    in_task_space_weight=1,
                    out_task_space_weight=0,
                ),
            ],
            cvr_add_ctr_logits=True,
        )
        if use_cdot:
            pepnet_v2_config.cdot.CopyFrom(
                multi_task_rank_pb2.CDOTConfig(
                    input_dim=4, output_dim=2, mid_dim=4, compress_hidden_units=[8, 6]
                )
            )
        if use_dcnv2:
            pepnet_v2_config.dcnv2.CopyFrom(module_pb2.CrossV2(cross_num=2, low_rank=4))

        model_config = model_pb2.ModelConfig(
            feature_groups=feature_groups, pepnet_v2=pepnet_v2_config
        )
        pepnet_v2 = PEPNet_v2(
            model_config=model_config,
            features=features,
            labels=["label1", "label2"],
        )
        init_parameters(pepnet_v2, device=torch.device("cpu"))
        pepnet_v2.eval()

        sparse_keys = ["cat_a", "cat_b", "domainf"]
        sparse_values = torch.tensor([1, 2, 3, 4, 5, 6, 7, 1, 2])
        sparse_lengths = torch.tensor([1, 2, 1, 3, 1, 1])
        sparse_feature = KeyedJaggedTensor.from_lengths_sync(
            keys=sparse_keys, values=sparse_values, lengths=sparse_lengths
        )
        dense_feature = KeyedTensor.from_tensor_list(
            keys=["int_a"], tensors=[torch.tensor([[0.2], [0.3]])]
        )
        batch = Batch(
            dense_features={BASE_DATA_GROUP: dense_feature},
            sparse_features={BASE_DATA_GROUP: sparse_feature},
            labels={"domainf": torch.tensor([1, 2])},
        )

        with torch.no_grad():
            predictions = pepnet_v2(batch)

        self.assertEqual(predictions["logits_ctr"].size(), (2,))
        self.assertEqual(predictions["probs_ctr"].size(), (2,))
        self.assertEqual(predictions["logits_cvr"].size(), (2,))
        self.assertEqual(predictions["probs_cvr"].size(), (2,))

    def test_pepnet_v2_no_cdot(self):
        self._run_test(use_cdot=False)

    def test_pepnet_v2_with_cdot(self):
        self._run_test(use_cdot=True)

    def test_pepnet_v2_with_dcnv2(self):
        self._run_test(use_dcnv2=True)

    def test_pepnet_v2_with_cdot_and_dcnv2(self):
        self._run_test(use_cdot=True, use_dcnv2=True)


if __name__ == "__main__":
    unittest.main()
