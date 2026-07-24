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

"""温度校准模块，用于多任务排序模型。

灵感来自 CaliCausalRank 的核心思想：分数校准应作为首要的训练目标。
提供：

- ``TemperatureScaler`` — 可学习的标量温度，在训练时除以 logits（保持排名顺序，
  单调变换）。
- ``compute_soft_ece()`` — 可微分的 Expected Calibration Error 近似，
  可用作训练损失。
"""

import math
from typing import Optional, Tuple

import torch
from torch import nn

# ---------------------------------------------------------------------------
# TemperatureScaler
# ---------------------------------------------------------------------------


class TemperatureScaler(nn.Module):
    """单任务塔的可学习温度缩放。

    应用 :math:`\\text{logit} / T`，其中 :math:`T \\ge \\epsilon`。

    参数化方式：使用 ``log_T = log(initial_temp) + shift``，
    其中 ``shift`` 是可学习参数（初始化 0），保证初始温度精确等于 ``initial_temp``。

    Args:
        initial_temp: 初始温度值。``T=1`` 表示不缩放。
        freeze: 如果为 ``True``，温度作为常数（不参与梯度更新）。
        min_temp: 最小允许温度，避免数值不稳定。
    """

    def __init__(
        self,
        initial_temp: float = 1.0,
        freeze: bool = False,
        min_temp: float = 0.01,
    ) -> None:
        super().__init__()
        self.min_temp = min_temp
        self._initial_temp = initial_temp

        if freeze:
            # 冻结模式：注册为 buffer，不参与梯度
            self.register_buffer("_temperature", torch.tensor(initial_temp))
        else:
            # 可学习模式：log_T = log(initial_temp) + shift
            # shift 初始化为 0，保证初始温度精确等于 initial_temp
            self.shift = nn.Parameter(torch.tensor(0.0))

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        """按温度缩放 logits。"""
        if hasattr(self, "shift"):
            # log_T = log(initial_temp) + shift，然后 exp 得到 T
            temperature = torch.exp(math.log(self._initial_temp) + self.shift)
            # 确保不低于 min_temp
            temperature = torch.clamp(temperature, min=self.min_temp)
        else:
            temperature = self._temperature
        return logits / temperature

    def get_temperature(self) -> torch.Tensor:
        """返回当前温度值（用于日志记录）。"""
        if hasattr(self, "shift"):
            temperature = torch.exp(math.log(self._initial_temp) + self.shift)
            return torch.clamp(temperature, min=self.min_temp)
        return self._temperature


# ---------------------------------------------------------------------------
# Soft ECE loss
# ---------------------------------------------------------------------------


@torch.no_grad()
def _compute_bin_boundaries(
    num_bins: int = 15,
    device: torch.device = torch.device("cpu"),
) -> Tuple[torch.Tensor, torch.Tensor]:
    """返回 [0, 1] 区间上等宽分桶的边界和中点。

    返回:
        boundaries: (num_bins + 1,) 张量，分桶边界值。
        mid_points: (num_bins,) 张量，分桶中心值。
    """
    boundaries = torch.linspace(0.0, 1.0, num_bins + 1, device=device)
    boundaries[0] -= 1e-8  # 略低于 0
    boundaries[-1] += 1e-8  # 略高于 1
    mid_points = (boundaries[:-1] + boundaries[1:]) / 2
    return boundaries, mid_points


def compute_soft_ece(
    probs: torch.Tensor,
    labels: torch.Tensor,
    weights: Optional[torch.Tensor] = None,
    num_bins: int = 15,
) -> torch.Tensor:
    """计算可微分的 Expected Calibration Error 近似。

    软 ECE 使用 sigmoid CDF 分配分数分桶隶属度，
    即使在分桶分配模糊时也能实现校准损失的梯度传播。

    .. math::
        \\mathrm{ECE} = \\sum_{b=1}^{B} \\frac{n_b}{N} \\; |\\bar{acc}_b - \\bar{conf}_b|

    其中 :math:`\\bar{acc}` 和 :math:`\\bar{conf}` 使用软分桶计数计算。

    参数:
        probs: 预测概率，形状 ``(N,)``。
        labels: 真实二值标签，形状 ``(N,)``。
        weights: 可选样本权重，形状 ``(N,)``。
        num_bins: 分桶数量。

    返回:
        标量张量 — 软 ECE 损失。
    """
    device = probs.device
    N = probs.size(0)

    boundaries, _ = _compute_bin_boundaries(num_bins, device)

    # 使用 sigmoid CDF 进行软分桶分配
    widths = boundaries[1:] - boundaries[:-1]  # (num_bins,)
    left_edges = boundaries[:-1].unsqueeze(0)  # (1, num_bins)
    right_edges = boundaries[1:].unsqueeze(0)  # (1, num_bins)

    # prob_soft_bin: (N, num_bins) — unsqueeze 确保正确广播
    probs_expanded = probs.unsqueeze(1)  # (N, 1)
    soft_bin = torch.sigmoid(
        (probs_expanded - left_edges) / (widths + 1e-8)
    ) - torch.sigmoid((probs_expanded - right_edges) / (widths + 1e-8))
    soft_bin = soft_bin.clamp(min=0.0)

    # 归一化每个样本使分桶之和为 1
    bin_sums = soft_bin.sum(dim=1, keepdim=True).clamp(min=1e-8)
    soft_bin = soft_bin / bin_sums

    # 加权求和
    if weights is not None:
        w = weights.unsqueeze(1)  # (N, 1)
    else:
        w = torch.ones(N, 1, device=device)

    # 每桶统计量
    bin_weight = soft_bin.t() @ w  # (num_bins, 1)
    bin_conf = (soft_bin * probs.unsqueeze(1)).t() @ w  # (num_bins, 1)
    bin_acc = (soft_bin * labels.unsqueeze(1)).t() @ w  # (num_bins, 1)

    # 每桶 ECE 贡献
    total_weight = bin_weight.sum()
    bin_ece = bin_weight.abs() / (total_weight + 1e-8) * (bin_acc - bin_conf).abs()

    return bin_ece.sum()


# ---------------------------------------------------------------------------
# 辅助：为多个任务创建缩放器
# ---------------------------------------------------------------------------


def create_temperature_scalers(
    num_tasks: int,
    initial_temp: float = 1.0,
    freeze: bool = False,
) -> nn.ModuleList:
    """创建 ``TemperatureScaler`` 实例的 ``ModuleList``。

    参数:
        num_tasks: 任务塔数量（例如 CTR + CVR = 2）。
        initial_temp: 共享初始温度。
        freeze: 如果为 ``True``，所有温度为固定常量。

    返回:
        长度为 ``num_tasks`` 的 ModuleList。
    """
    return nn.ModuleList(
        [
            TemperatureScaler(initial_temp=initial_temp, freeze=freeze)
            for _ in range(num_tasks)
        ]
    )


# ---------------------------------------------------------------------------
# Platt Scaling — Inference-time calibration
# ---------------------------------------------------------------------------


class PlattScaler(nn.Module):
    """单任务塔的可学习 Platt 校准 (a*logit + b)。

    应用 :math:`\\sigma(a \\cdot \\text{logit} + b)`，其中 :math:`a, b` 为可学习参数。

    与 TemperatureScaler 不同，PlattScaler 有两个自由度：
    - ``a`` 控制缩放（类似 temperature），但可以有符号翻转
    - ``b`` 控制偏移（temperature scaling 无法做偏移）

    用法：
        1. 创建 scaler = PlattScaler()  (a=1, b=0 初始化)
        2. 在 validation set 上 fit(fitted_logits, fitted_labels)
        3. 冻结: scaler.freeze()
        4. inference 时通过 forward() 应用校准

    Args:
        freeze: 如果为 True，a=1, b=0（即不校准）。
    """

    def __init__(self, freeze: bool = False) -> None:
        super().__init__()
        self._frozen = freeze

        if freeze:
            # 冻结模式：不参与梯度，等同于 identity
            self.register_buffer("_a", torch.tensor(1.0))
            self.register_buffer("_b", torch.tensor(0.0))
        else:
            self.a = nn.Parameter(torch.tensor(1.0))
            self.b = nn.Parameter(torch.tensor(0.0))

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        """对 logits 做 Platt 校准。"""
        if hasattr(self, "a"):
            return torch.sigmoid(self.a * logits + self.b)
        else:
            # frozen: apply sigmoid(a*logit + b) with frozen buffers
            return torch.sigmoid(self._a * logits + self._b)

    def get_a(self) -> float:
        if hasattr(self, "a"):
            return self.a.item()
        return self._a.item()

    def get_b(self) -> float:
        if hasattr(self, "b"):
            return self.b.item()
        return self._b.item()

    def fit_from_problabels(
        self,
        probs: torch.Tensor,
        labels: torch.Tensor,
        weights: Optional[torch.Tensor] = None,
        max_iter: int = 100,
    ) -> dict:
        """从已有 probs + labels 拟合 a, b。

        注意：输入是 sigmoid(logits) 后的概率值，所以我们先在 logit-space
        反求原始 logits，然后在新 logits 上用牛顿法拟合 a,b。

        这允许我们在训练结束后，用 validation set 的 preds 做离线校准，
        无需重新跑 forward。

        Returns:
            包含 fitting 统计信息的字典。
        """
        assert not self._frozen, "Cannot fit a frozen PlattScaler"

        # Clip probs to avoid log(0)
        eps = 1e-7
        probs_clipped = probs.clamp(min=eps, max=1 - eps)

        # Invert sigmoid to get back logits
        logits = torch.log(probs_clipped / (1 - probs_clipped))

        return self.fit_from_logits(logits, labels, weights, max_iter)

    def fit_from_logits(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        weights: Optional[torch.Tensor] = None,
        max_iter: int = 100,
    ) -> dict:
        """使用牛顿法拟合 Platt 参数 (a, b)。

        最小化负 log-likelihood:
            L = -sum_i [ y_i * log(sigmoid(a*x_i+b)) + (1-y_i)*log(1-sigmoid(a*x_i+b)) ]

        Args:
            logits: 原始 logits，形状 (N,)
            labels: 二值标签，形状 (N,)
            weights: 可选样本权重，形状 (N,)
            max_iter: 牛顿法最大迭代次数

        Returns:
            包含 fitting 收敛信息的字典。
        """
        N = logits.size(0)
        x = logits.float()
        y = labels.float()

        if weights is None:
            w = torch.ones(N, dtype=torch.float32, device=logits.device)
        else:
            w = weights.float()

        # 初始化 a=1, b=0
        a = torch.tensor(1.0, device=logits.device)
        b = torch.tensor(0.0, device=logits.device)

        prev_loss = None
        converged = False

        for iteration in range(max_iter):
            # z = a*x + b
            z = a * x + b
            p = torch.sigmoid(z)

            # Negative log likelihood
            pw = p * w
            yw = y * w
            loss = (
                -(
                    yw * torch.log(p.clamp(min=1e-7))
                    + (1 - yw) * torch.log((1 - p).clamp(min=1e-7))
                ).sum()
                / w.sum()
            )

            if prev_loss is not None and abs(prev_loss - loss) < 1e-6:
                converged = True
                prev_loss = loss
                break
            prev_loss = loss

            # Gradient of loss w.r.t. a, b
            # dL/da = -sum w*y*x*p(1-p)*(y-p) / sum(w)
            # dL/db = -sum w*y*p(1-p)*(y-p) / sum(w)
            residual = p - y  # (N,)
            grad_a = (w * residual * x).sum() / w.sum()
            grad_b = (w * residual).sum() / w.sum()

            # Hessian (approximate)
            hessian_a = (w * p * (1 - p) * x * x).sum() / w.sum() + 1e-6
            hessian_ab = (w * p * (1 - p) * x).sum() / w.sum()
            hessian_b = (w * p * (1 - p)).sum() / w.sum() + 1e-6

            # Newton step with damping
            det = hessian_a * hessian_b - hessian_ab * hessian_ab
            if abs(det) < 1e-10:
                # Fall back to gradient descent
                a -= 0.01 * grad_a
                b -= 0.01 * grad_b
            else:
                da = (hessian_b * grad_a - hessian_ab * grad_b) / det
                db = (hessian_a * grad_b - hessian_ab * grad_a) / det
                # Line search with damping
                a -= 0.5 * da
                b -= 0.5 * db

        # Save fitted parameters back to module parameters
        if hasattr(self, "a"):
            self.a.data = a.clone().detach()
            self.b.data = b.clone().detach()

        return {
            "a": a.item(),
            "b": b.item(),
            "final_loss": loss.item(),
            "converged": converged,
            "iterations": iteration + 1,
        }

    def freeze(self) -> None:
        """将当前拟合的 a,b 冻结为常量。"""
        if hasattr(self, "a"):
            a_val = self.a.data.clone()
            b_val = self.b.data.clone()
            del self.a
            del self.b
            self.register_buffer("_a", a_val)
            self.register_buffer("_b", b_val)
            self._frozen = True

    def is_frozen(self) -> bool:
        return self._frozen
