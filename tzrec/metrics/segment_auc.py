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

import logging
from typing import Any, Dict, Optional

import torch
from torchmetrics.functional.classification.auroc import _binary_auroc_compute

from tzrec.metrics.grouped_auc import GroupedAUC

logger = logging.getLogger("tzrec")


class SegmentAUC(GroupedAUC):
    """AUC for a specific segment/group."""

    def __init__(
        self,
        target_group: int = 0,
        group_name_map: Optional[Dict[int, str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(group_name_map=group_name_map, **kwargs)
        self._target_group = target_group

    def compute(self) -> torch.Tensor:
        """Compute the metric for the target segment."""
        preds = torch.cat(self.preds)
        target = torch.cat(self.target)
        grouping_key = torch.cat(self.grouping_key)

        sorted_grouping_key, indices = torch.sort(grouping_key)
        sorted_preds = preds[indices]
        sorted_target = target[indices]

        unique_group_values, counts = torch.unique_consecutive(
            sorted_grouping_key, return_counts=True
        )
        counts = counts.tolist()
        unique_group_values_list = unique_group_values.tolist()

        grouped_preds = torch.split(sorted_preds, counts)
        grouped_target = torch.split(sorted_target, counts)

        for group_val, g_preds, g_target in zip(
            unique_group_values_list, grouped_preds, grouped_target
        ):
            if group_val == self._target_group:
                mean_target = torch.mean(g_target.to(torch.float32)).item()
                if mean_target > 0 and mean_target < 1:
                    auc = _binary_auroc_compute((g_preds, g_target), None)
                    if isinstance(auc, torch.Tensor):
                        return auc
                    return torch.tensor(auc, device=preds.device)
                else:
                    logger.warning(
                        f"SegmentAUC: target_group={self._target_group} "
                        f"has mean_target={mean_target:.4f}, cannot compute AUC"
                    )
                    return torch.tensor(0.0, device=preds.device)

        logger.warning(
            f"SegmentAUC: target_group={self._target_group} not found in data"
        )
        return torch.tensor(0.0, device=preds.device)
