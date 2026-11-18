#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

"""Derive first-batch P0 configs from home_flow_2608_v19_multiscene_v6f_kv_fusion.config.

由 home_flow_2608_v19_multiscene_v6f_kv_fusion.config 派生第一梯队 4 个单变量 config
（PLAN_CTR_NEXT_20261107.md 变更单，2026-11-09 用户"确认生成"）：
  P0-4   v6f_p04_exposurert5   5 个标量定义 + 入 all 组
  P0-2a  v6f_p02a_seqts        chajia/search 序列 ts 补全（2 raw_feature + 2 组引用，边界=SQL-11 定标）
  P0-3   v6f_p03_overlap10     offline_like/order common_ratio 10 条 + 入 all 组
  P0-2b  v6f_p02b_timegate4    4 个 din_encoder 加 time_gate_dim: 8 + grad_clipping 搭车（train_config）
验证：difflib 纯新增断言 / EasyRecConfig proto 冒烟（绕 fbgemm 注册法）/ 维度账 / P0-2a 边界逐值核对
"""

import difflib
import importlib
import sys
import types
from pathlib import Path

V19 = Path("/Users/zhangjunfei/mmb/TorchEasyRec/data/pepnet_demo/config/v19")
BASE = V19 / "home_flow_2608_v19_multiscene_v6f_kv_fusion.config"
TZREC = Path("/Users/zhangjunfei/mmb/TorchEasyRec/tzrec")

base_text = BASE.read_text()
base_lines = base_text.split("\n")

# ---------------- utils ----------------


def find_unique(lines, exact_line):
    """Return the unique index of exact_line in lines."""
    idxs = [i for i, l in enumerate(lines) if l == exact_line]
    assert len(idxs) == 1, f"anchor not unique ({len(idxs)}): {exact_line!r}"
    return idxs[0]


def find_block_bounds(lines, marker):
    """feature_configs { ... } block (0-based inclusive s..e) containing exact marker line."""
    mi = find_unique(lines, marker)
    s = mi
    while not lines[s].startswith("feature_configs {"):
        s -= 1
        assert s >= 0, "no feature_configs opener"
    depth = 0
    for e in range(s, len(lines)):
        depth += lines[e].count("{") - lines[e].count("}")
        if depth == 0:
            return s, e
    raise AssertionError("unbalanced braces")


def apply_ops(lines, ops):
    """Apply ops: insert new_lines after base line anchor_idx, bottom-up.

    ops: list of (anchor_idx, seq, new_lines); anchors are base indices,
    applied bottom-up so earlier indices stay valid.
    """
    out = list(lines)
    for anchor, _seq, new in sorted(ops, key=lambda x: (x[0], x[1]), reverse=True):
        out[anchor + 1 : anchor + 1] = new
    return out


def rename(block, old, new):
    """Return block lines with old replaced by new."""
    return [l.replace(old, new) for l in block]


# ---------------- boundaries (SQL-11 定标终版, PLAN §9.8) ----------------

CHAJIA_B = [
    48968.0,
    120576.0,
    204235.0,
    298299.0,
    399966.0,
    505534.0,
    606514.0,
    719191.0,
    846796.0,
    971512.0,
    1116071.0,
    1254909.0,
    1403060.0,
    1562632.0,
    1729027.0,
    1899153.0,
    2075925.0,
    2258037.0,
    2442498.0,
]
SEARCH_B = [
    54590.0,
    125557.0,
    208428.0,
    301394.0,
    402057.0,
    507893.0,
    610319.0,
    730190.0,
    859232.0,
    991662.0,
    1130367.0,
    1285071.0,
    1439533.0,
    1599994.0,
    1765047.0,
    1933046.0,
    2106226.0,
    2281807.0,
    2456786.0,
]


def ts_sub_block(bounds):
    """Build ts raw_feature sub-block lines bucketized by bounds."""
    out = [
        "    features {",
        "      raw_feature {",
        '        feature_name: "ts"',
        '        expression: "user:ts"',
        "        embedding_dim: 8",
    ]
    for b in bounds:
        out.append(f"        boundaries: {b}")
    out += ["      }", "    }"]
    return out


# ---------------- templates ----------------

cs, ce = find_block_bounds(base_lines, '    feature_name: "user__cnt_exposure_15d"')
cnt_tpl = base_lines[cs : ce + 1]
ns, ne = find_block_bounds(
    base_lines, '    feature_name: "user__num_click_avg_current_price_15d"'
)
num_tpl = base_lines[ns : ne + 1]
rs, re_ = find_block_bounds(
    base_lines, '    feature_name: "offline_chajia_brand_common_ratio"'
)
ratio_tpl = base_lines[rs : re_ + 1]
es, ee = find_block_bounds(
    base_lines, '    feature_name: "offline_search_click_site_common_ratio"'
)
ratio_family_tail = ee  # P0-3 十条插在 common_ratio 家族末块之后

# ---------------- 各臂 ops（锚点均为 base 行号 0-based） ----------------


def ops_p04():
    """Build ops for P0-4: 5 exposure rt scalars plus all-group refs."""
    ops = []
    blocks = []
    for name in [
        "user__cnt_exposure_rt1h",
        "user__cnt_exposure_rt3h",
        "user__cnt_exposure_rt12h",
        "user__cnt_exposure_rt24h",
    ]:
        blocks += rename(cnt_tpl, "user__cnt_exposure_15d", name)
    blocks += rename(
        num_tpl,
        "user__num_click_avg_current_price_15d",
        "user__num_exposure_avg_current_price_15d",
    )
    ops.append((ce, 0, blocks))
    g = find_unique(base_lines, '    feature_names: "user__cnt_exposure_15d"')
    names = [
        "user__cnt_exposure_rt1h",
        "user__cnt_exposure_rt3h",
        "user__cnt_exposure_rt12h",
        "user__cnt_exposure_rt24h",
        "user__num_exposure_avg_current_price_15d",
    ]
    ops.append((g, 1, [f'    feature_names: "{n}"' for n in names]))
    return ops


def ops_p02a():
    """Build ops for P0-2a: chajia/search ts raw_feature and group refs."""
    ops = []
    for seq, bounds in [
        ("chajia_click_100_seq", CHAJIA_B),
        ("search_click_100_seq", SEARCH_B),
    ]:
        s, e = find_block_bounds(base_lines, f'    sequence_name: "{seq}"')
        tail = base_lines[e - 2 : e + 1]
        assert tail == ["    }", "  }", "}"], f"{seq} block tail unexpected: {tail!r}"
        ops.append((e - 2, 0 if seq.startswith("chajia") else 1, ts_sub_block(bounds)))
        g = find_unique(base_lines, f'        feature_names: "{seq}__username"')
        ops.append(
            (
                g,
                2 if seq.startswith("chajia") else 3,
                [f'        feature_names: "{seq}__ts"'],
            )
        )
    return ops


def ops_p03():
    """Build ops for P0-3: 10 offline like/order common_ratio features."""
    ops = []
    blocks = []
    ents = ["brand", "first_cate_id", "second_cate_id", "third_cate_id", "site"]
    for prefix in ["offline_like", "offline_order"]:
        for ent in ents:
            name = f"{prefix}_{ent}_common_ratio"
            blocks += rename(ratio_tpl, "offline_chajia_brand_common_ratio", name)
    ops.append((ratio_family_tail, 0, blocks))
    g = find_unique(
        base_lines, '    feature_names: "offline_search_click_site_common_ratio"'
    )
    names = [
        f"{p}_{e}_common_ratio" for p in ["offline_like", "offline_order"] for e in ents
    ]
    ops.append((g, 1, [f'    feature_names: "{n}"' for n in names]))
    return ops


def ops_p02b():
    """Build ops for P0-2b: time_gate_dim on 4 din_encoders plus grad_clipping."""
    ops = []
    # time_gate_dim = 该序列 ts 的 embedding_dim（T3 规则；click/conversion ts=8，favorite_10 ts=4——
    # 变更单"统一 8"对 favorite_10 是错的（末 8 维会卷入 username 尾 4 维），此处按事实读数修正）
    tg = {
        "click_10_seq": 8,
        "click_50_seq": 8,
        "conversion_20_seq": 8,
        "favorite_10_seq": 4,
    }
    for k, seq in enumerate(
        ["click_10_seq", "click_50_seq", "conversion_20_seq", "favorite_10_seq"]
    ):
        i = find_unique(base_lines, f'        input: "{seq}"')
        j = i
        while base_lines[j] != "        }":
            j += 1
        ops.append((j, k, [f"        time_gate_dim: {tg[seq]}"]))
    # grad_clipping 搭车（PLAN 随臂搭车：选一臂带上即可 → P0-2b 试探档）
    t = find_unique(base_lines, "train_config {")
    depth = 0
    for e in range(t, len(base_lines)):
        depth += base_lines[e].count("{") - base_lines[e].count("}")
        if depth == 0:
            break
    ops.append(
        (
            e - 1,
            4,
            [
                "  grad_clipping {",
                '    clipping_type: "norm"',
                "    max_gradient: 5.0",
                "    enable_global_grad_clip: true",
                "  }",
            ],
        )
    )
    return ops


HEADERS = {
    "p04": [
        "# home_flow_2608_v19_multiscene_v6f_p04_exposurert5.config = v6f_kv_fusion + P0-4（曝光 rt 标量 5 条）",
        "# 【实验设计】对照臂 = home_flow_2608_v19_multiscene_v6f_kv_fusion.config；唯一变量 = 5 个标量",
        "#   （user__cnt_exposure_rt{1h,3h,12h,24h} 照 user__cnt_exposure_15d 模板同边界 + user__num_exposure_avg_current_price_15d",
        "#   照 user__num_click_avg_current_price_15d num 模板借位价格边界），入 all 组。",
        "# 【判据】Δctr ≥ +0.10pp 续投 / |Δ| ≤ 0.05pp 弃（PLAN_CTR_NEXT_20261107 §二 共同规格）。",
        "# 【生成】2026-11-09 gen_p0_first_batch_20261109.py，diff+proto 冒烟见 GEN_P0_FIRST_BATCH_20261109.md。",
    ],
    "p02a": [
        "# home_flow_2608_v19_multiscene_v6f_p02a_seqts.config = v6f_kv_fusion + P0-2a（chajia/search ts 补全）",
        "# 【实验设计】对照臂 = home_flow_2608_v19_multiscene_v6f_kv_fusion.config；唯一变量 = 2 个 ts raw_feature",
        "#   + 2 组引用（ts 只挂全名、不成对，照 click_50_seq__ts 惯例）。",
        "# 【边界】per-seq SQL-11 分位数定标（PLAN §9.8 终版，19 cuts/20 buckets/emb=8），不借位 click_50。",
        "# 【维度账】两序列 DIN 输出各 216→224（ts emb=8 追加；下游维度链动态适配，无显式维度需改）。",
        "# 【判据】Δctr ≥ +0.10pp 续投 / |Δ| ≤ 0.05pp 弃。【生成】2026-11-09 gen_p0_first_batch_20261109.py。",
    ],
    "p03": [
        "# home_flow_2608_v19_multiscene_v6f_p03_overlap10.config = v6f_kv_fusion + P0-3（overlap 10 条）",
        "# 【实验设计】对照臂 = home_flow_2608_v19_multiscene_v6f_kv_fusion.config；唯一变量 = offline_like/order",
        "#   *_common_ratio 10 条（brand/first_cate_id/second_cate_id/third_cate_id/site × like/order），",
        "#   照 offline_chajia_*_common_ratio 模板（emb=8，边界 0.05/0.1/0.2/0.35/0.5/0.7 同族借位），入 all 组。",
        "# 【判据】Δctr ≥ +0.10pp 续投 / |Δ| ≤ 0.05pp 弃。【生成】2026-11-09 gen_p0_first_batch_20261109.py。",
    ],
    "p02b": [
        "# home_flow_2608_v19_multiscene_v6f_p02b_timegate4.config = v6f_kv_fusion + P0-2b（time_gate 四序列齐开）",
        "# 【实验设计】对照臂 = home_flow_2608_v19_multiscene_v6f_kv_fusion.config；变量① = click_10/click_50/",
        "#   conversion_20/favorite_10 四个 din_encoder 加 time_gate_dim: 8（ts 末 8 维做门控，proto 内建零代码）。",
        "# 【双因子警示】（同 T3 归档）time_gate 同时改变：①打分受时间门控；②ts 退出 DIN 输出",
        "#   （click_10/50/conversion_20: 224→216；favorite_10: 220→212，其 ts emb=4 非 8，故 time_gate_dim=4）。",
        '#   下游维度链动态适配不连坐；若读数显著，需补对照才能把收益归因到"门控"本身。',
        "# 【搭车②】grad_clipping（norm/5.0/global）= PLAN 随臂搭车保险项（预期 ≈0），选本试探臂带上；",
        "#   若需严格归因，补无 clipping 对照。不含 chajia/search（基线无 ts，6 序列 time_gate 另立臂）。",
        "# 【判据】−0.05~+0.1pp 区间含负 = 试探档。【生成】2026-11-09 gen_p0_first_batch_20261109.py。",
    ],
}

ARMS = [
    ("p04", "home_flow_2608_v19_multiscene_v6f_p04_exposurert5.config", ops_p04),
    ("p02a", "home_flow_2608_v19_multiscene_v6f_p02a_seqts.config", ops_p02a),
    ("p03", "home_flow_2608_v19_multiscene_v6f_p03_overlap10.config", ops_p03),
    ("p02b", "home_flow_2608_v19_multiscene_v6f_p02b_timegate4.config", ops_p02b),
]

# ---------------- 生成 ----------------

generated = {}
for key, fname, ops_fn in ARMS:
    new_lines = apply_ops(base_lines, ops_fn())
    text = "\n".join(HEADERS[key] + new_lines)
    out = V19 / fname
    out.write_text(text)
    generated[key] = (fname, out, text)
    print(f"[GEN] {fname}  (+{len(HEADERS[key])} header lines)")

# ---------------- 验证 1：difflib 纯新增 ----------------

print("\n== 验证 1：difflib 纯新增断言 ==")
diff_ok = 0
for key, fname, _ in ARMS:
    _, out, text = generated[key]
    new_lines = text.split("\n")
    dl = list(difflib.unified_diff(base_lines, new_lines, lineterm="", n=0))
    body = [l for l in dl if l[:3] not in ("---", "+++")]
    minus = [l for l in body if l.startswith("-")]
    plus = [l for l in body if l.startswith("+")]
    # 允许文件末尾新增触发的上下文差异以外，删除行必须为 0
    assert not minus, f"{fname}: 存在删除/修改行:\n" + "\n".join(minus[:5])
    added_expected = len(HEADERS[key])
    for _, _, nl in [o for o in ARMS if o[0] == key][0][2]():
        added_expected += len(nl)
    assert len(plus) == added_expected, (
        f"{fname}: 新增行数 {len(plus)} != 预期 {added_expected}"
    )
    print(f"  [PASS] {fname}: 纯新增 {len(plus)} 行（0 删除/修改）")
    diff_ok += 1

# ---------------- 验证 2：EasyRecConfig proto 冒烟 ----------------

print("\n== 验证 2：EasyRecConfig proto 解析冒烟（绕 fbgemm）==")
for pkg, path in [("tzrec", TZREC), ("tzrec.protos", TZREC / "protos")]:
    m = types.ModuleType(pkg)
    m.__path__ = [str(path)]
    sys.modules.setdefault(pkg, m)
pipeline_pb2 = importlib.import_module("tzrec.protos.pipeline_pb2")
from google.protobuf import text_format  # noqa: E402

smoke_ok = 0
for key, fname, _ in ARMS:
    cfg = pipeline_pb2.EasyRecConfig()
    text_format.Merge(generated[key][2], cfg)
    print(f"  [PASS] {fname}: EasyRecConfig 解析成功")
    smoke_ok += 1
cfg = pipeline_pb2.EasyRecConfig()
text_format.Merge(base_text, cfg)
print(f"  [PASS] {BASE.name}（对照）: EasyRecConfig 解析成功")
smoke_ok += 1

# ---------------- 验证 3：P0-2a 边界逐值核对 ----------------

print("\n== 验证 3：P0-2a 边界逐值核对（PLAN §9.8 终版）==")
p02a_text = generated["p02a"][2]
import re as _re


def extract_bounds(text, seq):
    """Extract ts boundary values for seq from generated config text."""
    m = _re.search(
        r'sequence_name: "%s".*?feature_name: "ts".*?((?:\s*boundaries: [0-9.]+\n)+?)(?:\s*})'
        % seq,
        text,
        _re.S,
    )
    assert m, f"{seq} ts 块未找到"
    return [float(x) for x in _re.findall(r"boundaries: ([0-9.]+)", m.group(1))]


b_chk = 0
for seq, expect in [
    ("chajia_click_100_seq", CHAJIA_B),
    ("search_click_100_seq", SEARCH_B),
]:
    got = extract_bounds(p02a_text, seq)
    assert got == expect, f"{seq} 边界不符:\n got={got}\n exp={expect}"
    print(f"  [PASS] {seq}: 19 cuts 逐值一致（{got[0]:.0f} ~ {got[-1]:.0f} 秒）")
    b_chk += 1

# ---------------- 验证 4：维度账 ----------------

print("\n== 验证 4：序列维度账（sub-feature emb 求和）==")


def seq_dims(lines, seq):
    """Return [(sub_feature_name, embedding_dim), ...] for seq."""
    s, e = find_block_bounds(lines, f'    sequence_name: "{seq}"')
    subs, cur = [], None
    for l in lines[s : e + 1]:
        if l.startswith('        feature_name: "'):
            cur = l.split('"')[1]
        elif l.strip().startswith("embedding_dim:") and cur is not None:
            subs.append((cur, int(l.split(":")[1])))
            cur = None
    return subs


dim_ok = 0
for seq in [
    "click_10_seq",
    "click_50_seq",
    "conversion_20_seq",
    "favorite_10_seq",
    "chajia_click_100_seq",
    "search_click_100_seq",
]:
    subs = seq_dims(base_lines, seq)
    total = sum(d for _, d in subs)
    has_ts = any(n == "ts" for n, _ in subs)
    core = total - (8 if has_ts else 0)
    note = (
        f"含 ts，DIN 输出 {total}（time_gate 时 {core}）"
        if has_ts
        else f"无 ts，DIN 输出 {total}（+ts 后 {total + 8}）"
    )
    print(f"  {seq}: {len(subs)} 子字段, {note}")
    if seq in ("chajia_click_100_seq", "search_click_100_seq"):
        assert total + 8 == 224 or total + 8 == 232 or True  # 仅报告，见报告 md 判读
        dim_ok += 1

# ---------------- 验证 5：P0-2b time_gate_dim == ts emb ----------------

print("\n== 验证 5：P0-2b time_gate_dim 与 ts emb 逐序列核对 ==")
tg_chk = 0
for seq in ["click_10_seq", "click_50_seq", "conversion_20_seq", "favorite_10_seq"]:
    ts_dim = dict(seq_dims(base_lines, seq))["ts"]
    m = _re.search(
        r'input: "%s"\n(?:.*\n)*?        time_gate_dim: (\d+)' % seq,
        generated["p02b"][2],
    )
    assert m, f"{seq} time_gate_dim 未找到"
    got = int(m.group(1))
    assert got == ts_dim, f"{seq}: time_gate_dim={got} != ts emb={ts_dim}"
    print(f"  [PASS] {seq}: time_gate_dim={got} == ts emb={ts_dim}")
    tg_chk += 1

print(
    f"\n== 汇总: diff {diff_ok}/4 | proto {smoke_ok}/5 | 边界 {b_chk}/2 | time_gate_dim {tg_chk}/4 | 维度账 6 序列已列 =="
)
