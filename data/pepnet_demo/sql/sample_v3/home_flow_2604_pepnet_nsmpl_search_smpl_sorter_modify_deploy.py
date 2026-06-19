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

import json
import os

from odps.accounts import StsAccount

service_name = "zhekou_mode_rank_pepnet_2604_nsmpl_allsmpl"

sts_token = None
if isinstance(o.account, StsAccount):
    sts_token = o.account.sts_token

config = {
    "name": service_name,
    "token": "MjY2MDM4MTU2ZWQzZGZhYjRjN2IxYWVhNDViMTQ4MTE1ZTFhOTI5YQ==",
    "cloud": {
        "networking": {
            "security_group_id": "sg-wz9gxdx0b1qpkjfvajx8",
            "vpc_id": "vpc-wz9cxf4qmesxtrrwbvmqs",
            "vswitch_id": "vsw-wz9nk436b03yeqhmdr8j9",
        }
    },
    "metadata": {
        "cpu": 6,
        "disk": "30Gi",
        "gateway": "default",
        "gpu_memory": 15,
        "instance": 3,
        "memory": 42000,
        "name": service_name,
        "resource": "eas-r-6dig78fwjk2a20x539",
        "resource_burstable": False,
        "rpc": {"enable_jemalloc": 1, "max_queue_size": 256},
        "workspace_id": "252434",
    },
    "storage": [
        {
            "mount_path": "/home/admin/docker_ml/workspace/model/",
            "oss": {
                "path": f"oss://mmb-spu/EasyRec/deploy/home_flow_2604_ctrcvr_sorter_v1/pepnet_nsmpl_search_smpl/{args['ymd']}/export/final_with_fg",
                "readOnly": False,
            },
            "properties": {"resource_type": "code"},
        }
    ],
    "model_config": {
        "outputs": "probs_ctr,probs_cvr",
        "storage_api_quota_name": "pay-as-you-go",
        "fg_mode": "normal",
        "steady_mode": True,
        "period": 2880,
        "use_privatelink_for_loading_features": False,
        "load_feature_view_in_parallel": False,
        "access_key_id": f"{o.account.access_id}",
        "access_key_secret": f"{o.account.secret_access_key}",
        "security_token": f"{sts_token}",
        "region": "cn-shenzhen",
        "fs_project": "feature_mall",
        "fs_model": "home_flow_2604_ctrcvr_sorter_v6",
        "fs_entity": "item",
        "featuredb_username": "mmbfeatures",
        "featuredb_password": "MMB@Features0",
        "load_feature_from_offlinestore": True,
    },
    "processor": "easyrec-torch-2.1",
}

with open("echo.json", "w") as output_file:
    json.dump(config, output_file)

# os.system(f'wget https://eas-data.oss-cn-shanghai.aliyuncs.com/tools/eascmd/v2/eascmd64')
# os.system(f'chmod +x eascmd64')
os.system(
    f"/home/admin/usertools/tools/eascmd64 -i {o.account.access_id} -k {o.account.secret_access_key} -t {sts_token} -e pai-eas-manage-vpc.cn-shenzhen.aliyuncs.com modify {service_name} -s echo.json"
)
