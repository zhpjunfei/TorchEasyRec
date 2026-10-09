#!/usr/bin/env python3
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

"""查询 PAI FeatureStore ModelFeature 下的 FeatureView 列表及其读写次数.

步骤:
  1. 调用 GetModelFeature API 获取 ModelFeature 详情（包含其绑定的 FeatureViews）
  2. 对每个 FeatureView，调用 CloudMonitor 获取指定时间窗口的 ReadCount / WriteCount

用法:
  python3 get_featureview_metrics.py \
    --instance-id fs-cn-xxxxxx \
    --model-feature-id 3 \
    --ak-id YOUR_AK_ID \
    --ak-secret YOUR_AK_SECRET \
    --region cn-shenzhen \
    --start-time 2026-08-25T00:00:00Z \
    --end-time   2026-08-26T00:00:00Z

说明:
  - GetModelFeature 返回的 Features 列表中，每个元素包含 feature_view_id / feature_view_name
  - 读写次数来自 CloudMonitor，namespace 为 acs_pai_featurestore
  - 若 CloudMonitor 指标不可用，脚本会打印警告并继续列出 FeatureView 元信息
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# PAI FeatureStore REST API
# ---------------------------------------------------------------------------
FS_API_VERSION = "2023-06-21"


def _build_fs_url(endpoint: str, path: str, query: dict | None = None) -> str:
    """拼接 FeatureStore REST API URL（内网 endpoint，如 paifeaturestore-vpc.xxx.aliyuncs.com)."""
    url = f"https://{endpoint}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    return url


def _fs_get(endpoint: str, path: str, query: dict | None = None) -> dict:
    """发送 GET 请求到 FeatureStore API，返回 JSON."""
    url = _build_fs_url(endpoint, path, query)
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"[ERROR] HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CloudMonitor
# ---------------------------------------------------------------------------
CMS_ENDPOINT = "cms.cn-shenzhen.aliyuncs.com"  # 可按 region 调整
CMS_API_VERSION = "2024-03-30"


def _sign_cms(ak_id: str, ak_secret: str, params: dict, method: str = "GET") -> dict:
    """用 HMAC-SHA1 对 CloudMonitor 请求签名（简化版，生产环境建议用 aliyun-python-sdk-cms)."""
    # 按 key 排序
    sorted_params = sorted(params.items())
    canonical_query = urllib.parse.urlencode(sorted_params)

    # 构造待签名字符串
    string_to_sign = (
        f"{method}&"
        f"{urllib.parse.quote('/', safe='')}&"
        f"{urllib.parse.quote(canonical_query, safe='~')}"
    )

    key = (ak_secret + "&").encode("utf-8")
    sig = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    params["Signature"] = urllib.parse.quote(base64.b64encode(sig).decode("utf-8"))
    return params


def _get_cms_metrics(
    ak_id: str,
    ak_secret: str,
    namespace: str,
    metric_names: list[str],
    project: str,
    dimensions: dict,
    start_time: str,
    end_time: str,
    period: int = 300,
) -> dict:
    """调用 CloudMonitor ListMetricPoints 获取指标数据."""
    params = {
        "Action": "ListMetricPoints",
        "Version": CMS_API_VERSION,
        "Format": "JSON",
        "RegionId": "cn-shenzhen",
        "Namespace": namespace,
        "Project": project,
        "Period": str(period),
        "StartTime": start_time,
        "EndTime": end_time,
    }
    for i, name in enumerate(metric_names):
        params[f"MetricName.{i + 1}"] = name

    # Dimensions as JSON string
    params["Dimensions"] = json.dumps(dimensions, separators=(",", ":"))

    params = _sign_cms(ak_id, ak_secret, params)
    url = f"https://{CMS_ENDPOINT}/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"[CMS ERROR] HTTP {e.code}: {body}", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def get_model_feature(
    endpoint: str,
    instance_id: str,
    model_feature_id: str,
) -> dict:
    """调用 GetModelFeature，返回解析后的响应."""
    path = f"/api/v1/instances/{instance_id}/modelfeatures/{model_feature_id}"
    resp = _fs_get(endpoint, path)
    if resp.get("Code") != "200" and resp.get("Success") is not True:
        print(
            f"[WARN] GetModelFeature 返回非成功状态: {json.dumps(resp, ensure_ascii=False)}",
            file=sys.stderr,
        )
    return resp


def extract_feature_views(model_feature_resp: dict) -> list[dict]:
    """从 GetModelFeature 响应中提取 FeatureView 列表."""
    features = model_feature_resp.get("Features", [])
    views = []
    seen = set()
    for f in features:
        vid = str(f.get("FeatureViewId", ""))
        if vid in seen:
            continue
        seen.add(vid)
        views.append(
            {
                "feature_view_id": vid,
                "feature_view_name": f.get("FeatureViewName", ""),
                "feature_name": f.get("Name", ""),
                "feature_type": f.get("Type", ""),
                "alias_name": f.get("AliasName", ""),
            }
        )
    return views


def query_cms_read_write(
    ak_id: str,
    ak_secret: str,
    namespace: str,
    project: str,
    dimensions: dict,
    start_time: str,
    end_time: str,
) -> dict:
    """查询 CloudMonitor 的 ReadCount / WriteCount."""
    resp = _get_cms_metrics(
        ak_id,
        ak_secret,
        namespace,
        metric_names=["ReadCount", "WriteCount"],
        project=project,
        dimensions=dimensions,
        start_time=start_time,
        end_time=end_time,
    )
    return resp


def format_timestamp(ts_ms: int | str) -> str:
    """毫秒时间戳 → 可读字符串."""
    try:
        return datetime.fromtimestamp(int(ts_ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts_ms)


def main():
    """主入口：解析命令行参数并运行查询."""
    parser = argparse.ArgumentParser(
        description="查询 PAI FeatureStore ModelFeature 的 FeatureView 及读写次数"
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="FeatureStore VPC endpoint，如 paifeaturestore-vpc.cn-shenzhen.aliyuncs.com",
    )
    parser.add_argument(
        "--instance-id", required=True, help="FeatureStore 实例 ID，如 fs-cn-xxxxxx"
    )
    parser.add_argument(
        "--model-feature-id",
        required=True,
        help="ModelFeature ID，可从 ListModelFeatures 获取",
    )
    parser.add_argument("--ak-id", required=True, help="阿里云 AccessKey ID")
    parser.add_argument("--ak-secret", required=True, help="阿里云 AccessKey Secret")
    parser.add_argument(
        "--start-time",
        default=None,
        help="查询起始时间 ISO8601，默认 24h 前，如 2026-08-25T00:00:00Z",
    )
    parser.add_argument(
        "--end-time",
        default=None,
        help="查询结束时间 ISO8601，默认当前，如 2026-08-26T00:00:00Z",
    )
    parser.add_argument(
        "--namespace",
        default="acs_pai_featurestore",
        help="CloudMonitor namespace（默认 acs_pai_featurestore）",
    )
    parser.add_argument(
        "--project",
        default="",
        help="CloudMonitor Project 名（通常与实例同名，留空则由 CM 推断）",
    )
    parser.add_argument("--output", default=None, help="输出 JSON 文件路径（可选）")
    args = parser.parse_args()

    # 默认时间范围：最近 24 小时
    if not args.end_time:
        args.end_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if not args.start_time:
        args.start_time = datetime.utcnow().timestamp() - 86400
        args.start_time = datetime.utcfromtimestamp(args.start_time).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    print(f"[*] 实例: {args.instance_id}")
    print(f"[*] ModelFeatureId: {args.model_feature_id}")
    print(f"[*] 时间范围: {args.start_time} ~ {args.end_time}")
    print()

    # Step 1: 获取 ModelFeature 详情
    print("[1/2] 调用 GetModelFeature ...")
    mf_resp = get_model_feature(args.endpoint, args.instance_id, args.model_feature_id)
    mf_name = mf_resp.get("Name", "<unknown>")
    mf_id = mf_resp.get("ModelFeatureId", args.model_feature_id)
    print(f"    ModelFeature: {mf_name} (id={mf_id})")
    print()

    # Step 2: 提取 FeatureView 列表
    feature_views = extract_feature_views(mf_resp)
    print(f"[2/2] 共 {len(feature_views)} 个 FeatureView:")
    print(f"  {'FeatureViewId':<12} {'FeatureViewName':<50} {'SampleFeature':<30}")
    print(f"  {'-' * 12} {'-' * 50} {'-' * 30}")
    for fv in feature_views:
        print(
            f"  {fv['feature_view_id']:<12} {fv['feature_view_name']:<50} {fv['feature_name']:<30}"
        )
    print()

    # Step 3: 尝试查询 CloudMonitor 读写次数
    print("[3/3] 查询 CloudMonitor 读写指标 ...")
    all_metrics = {}
    for fv in feature_views:
        dims = {
            "FeatureStoreInstanceId": args.instance_id,
            "FeatureViewName": fv["feature_view_name"],
        }
        if args.project:
            dims["ProjectName"] = args.project
        cms_resp = query_cms_read_write(
            ak_id=args.ak_id,
            ak_secret=args.ak_secret,
            namespace=args.namespace,
            project=args.project,
            dimensions=dims,
            start_time=args.start_time,
            end_time=args.end_time,
        )
        # 解析结果
        codes = cms_resp.get("Code")
        if codes != "200" and codes != "Success":
            err_msg = cms_resp.get("Message", "unknown error")
            print(
                f"  [WARN] {fv['feature_view_name']}: CMS 查询失败 ({codes}): {err_msg}"
            )
            all_metrics[fv["feature_view_name"]] = {"error": err_msg}
            continue

        data = cms_resp.get("Data", {})
        points = data.get("MetricPoints", [])
        requests = data.get("Requests", {})
        summary = data.get("Summary", {})
        all_metrics[fv["feature_view_name"]] = {
            "points": points,
            "requests": requests,
            "summary": summary,
        }
        total_read = summary.get("ReadCount_sum", summary.get("read_count", "N/A"))
        total_write = summary.get("WriteCount_sum", summary.get("write_count", "N/A"))
        print(
            f"  [{fv['feature_view_name']:<40}] read={total_read}  write={total_write}"
        )

    # Step 4: 输出汇总
    output = {
        "instance_id": args.instance_id,
        "model_feature_id": mf_id,
        "model_feature_name": mf_name,
        "time_range": {"start": args.start_time, "end": args.end_time},
        "feature_views": feature_views,
        "metrics": all_metrics,
    }

    print()
    print("=" * 60)
    print("汇总结果:")
    print(json.dumps(output, indent=2, ensure_ascii=False))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
