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

from pyfg101 import run_on_odps

fg_task = run_on_odps.FgTask(
    "feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set",
    "home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3",
    "home_flow_2604_ctrcvr_sorter_config_fg_v3.json",
    args["bizdate"],  # noqa: F821
    force_delete_output_table=False,
    force_update_resource=False,
    output_merged_str=False,
)
# fg_task.add_sql_setting('odps.stage.mapper.split.size', 64)
fg_task.run(o)  # noqa: F821
