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

import datetime

from feature_store_py.fs_client import FeatureStoreClient
from feature_store_py.fs_config import (
    FeatureViewConfig,
    LabelInputConfig,
    PartitionConfig,
    TrainSetOutputConfig,
)
from feature_store_py.fs_datasource import (
    MaxComputeDataSource,
    TrainingSetOutput,
)
from feature_store_py.fs_features import FeatureSelector
from odps.accounts import StsAccount

cur_day = args["dt"]
print("cur_day = ", cur_day)
offset = datetime.timedelta(days=-1)
pre_day = (datetime.datetime.strptime(cur_day, "%Y%m%d") + offset).strftime("%Y%m%d")
print("pre_day = ", pre_day)

ak_id = o.account.access_id
ak_secret = o.account.secret_access_key
st = None
if isinstance(o.account, StsAccount):
    st = o.account.st
endpoint = "paifeaturestore-vpc.cn-shenzhen.aliyuncs.com"
fs = FeatureStoreClient(
    ak_id=ak_id,
    ak_secret=ak_secret,
    security_token=st,
    endpoint=endpoint,
)
cur_project_name = "feature_mall"
project = fs.get_project(cur_project_name)
if project is None:
    raise ValueError(
        "feature store project is None, need to create featore store project in PAI."
    )
feature_view_config_list = []


home_flow_2604_ads_usr_user_basic_info_preprocess_v1 = project.get_feature_view(
    "home_flow_2604_ads_usr_user_basic_info_preprocess_v1"
)
if home_flow_2604_ads_usr_user_basic_info_preprocess_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_ads_usr_user_basic_info_preprocess_v1",
    )
    home_flow_2604_ads_usr_user_basic_info_preprocess_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_ads_usr_user_basic_info_preprocess_v1",
            datasource=ds,
            online=True,
            entity="user",
            primary_key="mmb_id",
            register=True,
        )
    )
home_flow_2604_ads_usr_user_basic_info_preprocess_v1_config = FeatureViewConfig(
    name="home_flow_2604_ads_usr_user_basic_info_preprocess_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(
    home_flow_2604_ads_usr_user_basic_info_preprocess_v1_config
)
home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3 = (
    project.get_feature_view(
        "home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3"
    )
)
if home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3",
    )
    home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3 = (
        project.create_batch_feature_view(
            name="home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3",
            datasource=ds,
            online=True,
            entity="item",
            primary_key="item_id",
            register=True,
        )
    )
home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3_config = (
    FeatureViewConfig(
        name="home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3",
        partition_config=PartitionConfig(name="dt", value=pre_day),
    )
)
feature_view_config_list.append(
    home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3_config
)
home_flow_2604_gender_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_gender_static_feat_15d_v1"
)
if home_flow_2604_gender_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_gender_static_feat_15d_v1",
    )
    home_flow_2604_gender_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_gender_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="gender",
        primary_key="gender",
        register=True,
    )
home_flow_2604_gender_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_gender_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_gender_static_feat_15d_v1_config)
home_flow_2604_age_group_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_age_group_static_feat_15d_v1"
)
if home_flow_2604_age_group_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_age_group_static_feat_15d_v1",
    )
    home_flow_2604_age_group_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_age_group_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="age_group",
        primary_key="age_group",
        register=True,
    )
home_flow_2604_age_group_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_age_group_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_age_group_static_feat_15d_v1_config)
home_flow_2604_login_city_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_login_city_static_feat_15d_v1"
)
if home_flow_2604_login_city_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_login_city_static_feat_15d_v1",
    )
    home_flow_2604_login_city_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_login_city_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="login_city",
        primary_key="login_city",
        register=True,
    )
home_flow_2604_login_city_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_login_city_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_login_city_static_feat_15d_v1_config)
home_flow_2604_dev_brand_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_dev_brand_static_feat_15d_v1"
)
if home_flow_2604_dev_brand_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_dev_brand_static_feat_15d_v1",
    )
    home_flow_2604_dev_brand_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_dev_brand_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="dev_brand",
        primary_key="dev_brand",
        register=True,
    )
home_flow_2604_dev_brand_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_dev_brand_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_dev_brand_static_feat_15d_v1_config)
home_flow_2604_mmb_id_static_feat_15d_v1_agg = project.get_feature_view(
    "home_flow_2604_mmb_id_static_feat_15d_v1_agg"
)
if home_flow_2604_mmb_id_static_feat_15d_v1_agg is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_mmb_id_static_feat_15d_v1_agg",
    )
    home_flow_2604_mmb_id_static_feat_15d_v1_agg = project.create_batch_feature_view(
        name="home_flow_2604_mmb_id_static_feat_15d_v1_agg",
        datasource=ds,
        online=True,
        entity="user",
        primary_key="mmb_id",
        register=True,
    )
home_flow_2604_mmb_id_static_feat_15d_v1_agg_config = FeatureViewConfig(
    name="home_flow_2604_mmb_id_static_feat_15d_v1_agg",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_mmb_id_static_feat_15d_v1_agg_config)

# # 物料向量
# feed_rec_flow_item_title_embedding_v5 = project.get_feature_view('feed_rec_flow_item_title_embedding_v5')
# feed_rec_flow_item_title_embedding_v5_config = FeatureViewConfig(name = 'feed_rec_flow_item_title_embedding_v5', partition_config=PartitionConfig(name = 'dt', value = cur_day), event_time = 'event_unix_time')
# feature_view_config_list.append(feed_rec_flow_item_title_embedding_v5_config)

home_flow_2604_first_cate_id_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_first_cate_id_static_feat_15d_v1"
)
if home_flow_2604_first_cate_id_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_first_cate_id_static_feat_15d_v1",
    )
    home_flow_2604_first_cate_id_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_first_cate_id_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="first_cate_id",
        primary_key="first_cate_id",
        register=True,
    )
home_flow_2604_first_cate_id_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_first_cate_id_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_first_cate_id_static_feat_15d_v1_config)
home_flow_2604_first_cate_id_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_first_cate_id_static_feat_3d_v1"
)
if home_flow_2604_first_cate_id_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_first_cate_id_static_feat_3d_v1",
    )
    home_flow_2604_first_cate_id_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_first_cate_id_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="first_cate_id",
        primary_key="first_cate_id",
        register=True,
    )
home_flow_2604_first_cate_id_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_first_cate_id_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_first_cate_id_static_feat_3d_v1_config)
home_flow_2604_first_cate_id_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_first_cate_id_static_feat_1d_v1"
)
if home_flow_2604_first_cate_id_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_first_cate_id_static_feat_1d_v1",
    )
    home_flow_2604_first_cate_id_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_first_cate_id_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="first_cate_id",
        primary_key="first_cate_id",
        register=True,
    )
home_flow_2604_first_cate_id_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_first_cate_id_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_first_cate_id_static_feat_1d_v1_config)
home_flow_2604_second_cate_id_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_second_cate_id_static_feat_15d_v1"
)
if home_flow_2604_second_cate_id_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_second_cate_id_static_feat_15d_v1",
    )
    home_flow_2604_second_cate_id_static_feat_15d_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_second_cate_id_static_feat_15d_v1",
            datasource=ds,
            online=True,
            entity="second_cate_id",
            primary_key="second_cate_id",
            register=True,
        )
    )
home_flow_2604_second_cate_id_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_second_cate_id_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_second_cate_id_static_feat_15d_v1_config)
home_flow_2604_second_cate_id_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_second_cate_id_static_feat_3d_v1"
)
if home_flow_2604_second_cate_id_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_second_cate_id_static_feat_3d_v1",
    )
    home_flow_2604_second_cate_id_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_second_cate_id_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="second_cate_id",
        primary_key="second_cate_id",
        register=True,
    )
home_flow_2604_second_cate_id_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_second_cate_id_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_second_cate_id_static_feat_3d_v1_config)
home_flow_2604_second_cate_id_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_second_cate_id_static_feat_1d_v1"
)
if home_flow_2604_second_cate_id_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_second_cate_id_static_feat_1d_v1",
    )
    home_flow_2604_second_cate_id_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_second_cate_id_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="second_cate_id",
        primary_key="second_cate_id",
        register=True,
    )
home_flow_2604_second_cate_id_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_second_cate_id_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_second_cate_id_static_feat_1d_v1_config)
home_flow_2604_cate_id_path_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_cate_id_path_static_feat_15d_v1"
)
if home_flow_2604_cate_id_path_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_cate_id_path_static_feat_15d_v1",
    )
    home_flow_2604_cate_id_path_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_cate_id_path_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="cate_id_path",
        primary_key="cate_id_path",
        register=True,
    )
home_flow_2604_cate_id_path_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_cate_id_path_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_cate_id_path_static_feat_15d_v1_config)
home_flow_2604_cate_id_path_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_cate_id_path_static_feat_3d_v1"
)
if home_flow_2604_cate_id_path_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_cate_id_path_static_feat_3d_v1",
    )
    home_flow_2604_cate_id_path_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_cate_id_path_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="cate_id_path",
        primary_key="cate_id_path",
        register=True,
    )
home_flow_2604_cate_id_path_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_cate_id_path_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_cate_id_path_static_feat_3d_v1_config)
home_flow_2604_cate_id_path_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_cate_id_path_static_feat_1d_v1"
)
if home_flow_2604_cate_id_path_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_cate_id_path_static_feat_1d_v1",
    )
    home_flow_2604_cate_id_path_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_cate_id_path_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="cate_id_path",
        primary_key="cate_id_path",
        register=True,
    )
home_flow_2604_cate_id_path_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_cate_id_path_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_cate_id_path_static_feat_1d_v1_config)
home_flow_2604_brand_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_brand_static_feat_15d_v1"
)
if home_flow_2604_brand_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_brand_static_feat_15d_v1",
    )
    home_flow_2604_brand_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_brand_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="brand",
        primary_key="brand",
        register=True,
    )
home_flow_2604_brand_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_brand_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_brand_static_feat_15d_v1_config)
home_flow_2604_brand_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_brand_static_feat_3d_v1"
)
if home_flow_2604_brand_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_brand_static_feat_3d_v1",
    )
    home_flow_2604_brand_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_brand_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="brand",
        primary_key="brand",
        register=True,
    )
home_flow_2604_brand_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_brand_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_brand_static_feat_3d_v1_config)
home_flow_2604_brand_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_brand_static_feat_1d_v1"
)
if home_flow_2604_brand_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_brand_static_feat_1d_v1",
    )
    home_flow_2604_brand_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_brand_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="brand",
        primary_key="brand",
        register=True,
    )
home_flow_2604_brand_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_brand_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_brand_static_feat_1d_v1_config)
home_flow_2604_site_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_site_static_feat_15d_v1"
)
if home_flow_2604_site_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_site_static_feat_15d_v1",
    )
    home_flow_2604_site_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_site_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="site",
        primary_key="site",
        register=True,
    )
home_flow_2604_site_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_site_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_site_static_feat_15d_v1_config)
home_flow_2604_site_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_site_static_feat_3d_v1"
)
if home_flow_2604_site_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_site_static_feat_3d_v1",
    )
    home_flow_2604_site_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_site_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="site",
        primary_key="site",
        register=True,
    )
home_flow_2604_site_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_site_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_site_static_feat_3d_v1_config)
home_flow_2604_site_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_site_static_feat_1d_v1"
)
if home_flow_2604_site_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_site_static_feat_1d_v1",
    )
    home_flow_2604_site_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_site_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="site",
        primary_key="site",
        register=True,
    )
home_flow_2604_site_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_site_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_site_static_feat_1d_v1_config)
home_flow_2604_core_entity_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_core_entity_static_feat_15d_v1"
)
if home_flow_2604_core_entity_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_core_entity_static_feat_15d_v1",
    )
    home_flow_2604_core_entity_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_core_entity_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="core_entity",
        primary_key="core_entity",
        register=True,
    )
home_flow_2604_core_entity_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_core_entity_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_core_entity_static_feat_15d_v1_config)
home_flow_2604_core_entity_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_core_entity_static_feat_3d_v1"
)
if home_flow_2604_core_entity_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_core_entity_static_feat_3d_v1",
    )
    home_flow_2604_core_entity_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_core_entity_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="core_entity",
        primary_key="core_entity",
        register=True,
    )
home_flow_2604_core_entity_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_core_entity_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_core_entity_static_feat_3d_v1_config)
home_flow_2604_core_entity_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_core_entity_static_feat_1d_v1"
)
if home_flow_2604_core_entity_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_core_entity_static_feat_1d_v1",
    )
    home_flow_2604_core_entity_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_core_entity_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="core_entity",
        primary_key="core_entity",
        register=True,
    )
home_flow_2604_core_entity_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_core_entity_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_core_entity_static_feat_1d_v1_config)
home_flow_2604_price_tag_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_price_tag_static_feat_15d_v1"
)
if home_flow_2604_price_tag_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_price_tag_static_feat_15d_v1",
    )
    home_flow_2604_price_tag_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_price_tag_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="price_tag",
        primary_key="price_tag",
        register=True,
    )
home_flow_2604_price_tag_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_price_tag_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_price_tag_static_feat_15d_v1_config)
home_flow_2604_price_tag_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_price_tag_static_feat_3d_v1"
)
if home_flow_2604_price_tag_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_price_tag_static_feat_3d_v1",
    )
    home_flow_2604_price_tag_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_price_tag_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="price_tag",
        primary_key="price_tag",
        register=True,
    )
home_flow_2604_price_tag_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_price_tag_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_price_tag_static_feat_3d_v1_config)
home_flow_2604_price_tag_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_price_tag_static_feat_1d_v1"
)
if home_flow_2604_price_tag_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_price_tag_static_feat_1d_v1",
    )
    home_flow_2604_price_tag_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_price_tag_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="price_tag",
        primary_key="price_tag",
        register=True,
    )
home_flow_2604_price_tag_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_price_tag_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_price_tag_static_feat_1d_v1_config)
home_flow_2604_promotion_channel_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_promotion_channel_static_feat_15d_v1"
)
if home_flow_2604_promotion_channel_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_promotion_channel_static_feat_15d_v1",
    )
    home_flow_2604_promotion_channel_static_feat_15d_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_promotion_channel_static_feat_15d_v1",
            datasource=ds,
            online=True,
            entity="promotion_channel",
            primary_key="promotion_channel",
            register=True,
        )
    )
home_flow_2604_promotion_channel_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_promotion_channel_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(
    home_flow_2604_promotion_channel_static_feat_15d_v1_config
)
home_flow_2604_promotion_channel_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_promotion_channel_static_feat_3d_v1"
)
if home_flow_2604_promotion_channel_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_promotion_channel_static_feat_3d_v1",
    )
    home_flow_2604_promotion_channel_static_feat_3d_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_promotion_channel_static_feat_3d_v1",
            datasource=ds,
            online=True,
            entity="promotion_channel",
            primary_key="promotion_channel",
            register=True,
        )
    )
home_flow_2604_promotion_channel_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_promotion_channel_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(
    home_flow_2604_promotion_channel_static_feat_3d_v1_config
)
home_flow_2604_promotion_channel_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_promotion_channel_static_feat_1d_v1"
)
if home_flow_2604_promotion_channel_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_promotion_channel_static_feat_1d_v1",
    )
    home_flow_2604_promotion_channel_static_feat_1d_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_promotion_channel_static_feat_1d_v1",
            datasource=ds,
            online=True,
            entity="promotion_channel",
            primary_key="promotion_channel",
            register=True,
        )
    )
home_flow_2604_promotion_channel_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_promotion_channel_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(
    home_flow_2604_promotion_channel_static_feat_1d_v1_config
)
home_flow_2604_discount_intensity_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_discount_intensity_static_feat_15d_v1"
)
if home_flow_2604_discount_intensity_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_discount_intensity_static_feat_15d_v1",
    )
    home_flow_2604_discount_intensity_static_feat_15d_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_discount_intensity_static_feat_15d_v1",
            datasource=ds,
            online=True,
            entity="discount_intensity",
            primary_key="discount_intensity",
            register=True,
        )
    )
home_flow_2604_discount_intensity_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_discount_intensity_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(
    home_flow_2604_discount_intensity_static_feat_15d_v1_config
)
home_flow_2604_discount_intensity_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_discount_intensity_static_feat_3d_v1"
)
if home_flow_2604_discount_intensity_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_discount_intensity_static_feat_3d_v1",
    )
    home_flow_2604_discount_intensity_static_feat_3d_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_discount_intensity_static_feat_3d_v1",
            datasource=ds,
            online=True,
            entity="discount_intensity",
            primary_key="discount_intensity",
            register=True,
        )
    )
home_flow_2604_discount_intensity_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_discount_intensity_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(
    home_flow_2604_discount_intensity_static_feat_3d_v1_config
)
home_flow_2604_discount_intensity_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_discount_intensity_static_feat_1d_v1"
)
if home_flow_2604_discount_intensity_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_discount_intensity_static_feat_1d_v1",
    )
    home_flow_2604_discount_intensity_static_feat_1d_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_discount_intensity_static_feat_1d_v1",
            datasource=ds,
            online=True,
            entity="discount_intensity",
            primary_key="discount_intensity",
            register=True,
        )
    )
home_flow_2604_discount_intensity_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_discount_intensity_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(
    home_flow_2604_discount_intensity_static_feat_1d_v1_config
)
home_flow_2604_dianpupingfen_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_dianpupingfen_static_feat_15d_v1"
)
if home_flow_2604_dianpupingfen_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_dianpupingfen_static_feat_15d_v1",
    )
    home_flow_2604_dianpupingfen_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_dianpupingfen_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="dianpupingfen",
        primary_key="dianpupingfen",
        register=True,
    )
home_flow_2604_dianpupingfen_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_dianpupingfen_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_dianpupingfen_static_feat_15d_v1_config)
home_flow_2604_dianpupingfen_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_dianpupingfen_static_feat_3d_v1"
)
if home_flow_2604_dianpupingfen_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_dianpupingfen_static_feat_3d_v1",
    )
    home_flow_2604_dianpupingfen_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_dianpupingfen_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="dianpupingfen",
        primary_key="dianpupingfen",
        register=True,
    )
home_flow_2604_dianpupingfen_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_dianpupingfen_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_dianpupingfen_static_feat_3d_v1_config)
home_flow_2604_dianpupingfen_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_dianpupingfen_static_feat_1d_v1"
)
if home_flow_2604_dianpupingfen_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_dianpupingfen_static_feat_1d_v1",
    )
    home_flow_2604_dianpupingfen_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_dianpupingfen_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="dianpupingfen",
        primary_key="dianpupingfen",
        register=True,
    )
home_flow_2604_dianpupingfen_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_dianpupingfen_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_dianpupingfen_static_feat_1d_v1_config)
home_flow_2604_pinpaidengji_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_pinpaidengji_static_feat_15d_v1"
)
if home_flow_2604_pinpaidengji_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_pinpaidengji_static_feat_15d_v1",
    )
    home_flow_2604_pinpaidengji_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_pinpaidengji_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="pinpaidengji",
        primary_key="pinpaidengji",
        register=True,
    )
home_flow_2604_pinpaidengji_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_pinpaidengji_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_pinpaidengji_static_feat_15d_v1_config)
home_flow_2604_pinpaidengji_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_pinpaidengji_static_feat_3d_v1"
)
if home_flow_2604_pinpaidengji_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_pinpaidengji_static_feat_3d_v1",
    )
    home_flow_2604_pinpaidengji_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_pinpaidengji_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="pinpaidengji",
        primary_key="pinpaidengji",
        register=True,
    )
home_flow_2604_pinpaidengji_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_pinpaidengji_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_pinpaidengji_static_feat_3d_v1_config)
home_flow_2604_pinpaidengji_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_pinpaidengji_static_feat_1d_v1"
)
if home_flow_2604_pinpaidengji_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_pinpaidengji_static_feat_1d_v1",
    )
    home_flow_2604_pinpaidengji_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_pinpaidengji_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="pinpaidengji",
        primary_key="pinpaidengji",
        register=True,
    )
home_flow_2604_pinpaidengji_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_pinpaidengji_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_pinpaidengji_static_feat_1d_v1_config)
home_flow_2604_spu_id_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_spu_id_static_feat_15d_v1"
)
if home_flow_2604_spu_id_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_spu_id_static_feat_15d_v1",
    )
    home_flow_2604_spu_id_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_spu_id_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="spu_id",
        primary_key="spu_id",
        register=True,
    )
home_flow_2604_spu_id_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_spu_id_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_spu_id_static_feat_15d_v1_config)
home_flow_2604_spu_id_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_spu_id_static_feat_3d_v1"
)
if home_flow_2604_spu_id_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_spu_id_static_feat_3d_v1",
    )
    home_flow_2604_spu_id_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_spu_id_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="spu_id",
        primary_key="spu_id",
        register=True,
    )
home_flow_2604_spu_id_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_spu_id_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_spu_id_static_feat_3d_v1_config)
home_flow_2604_spu_id_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_spu_id_static_feat_1d_v1"
)
if home_flow_2604_spu_id_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_spu_id_static_feat_1d_v1",
    )
    home_flow_2604_spu_id_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_spu_id_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="spu_id",
        primary_key="spu_id",
        register=True,
    )
home_flow_2604_spu_id_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_spu_id_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_spu_id_static_feat_1d_v1_config)
home_flow_2604_publish_user_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_publish_user_static_feat_15d_v1"
)
if home_flow_2604_publish_user_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_publish_user_static_feat_15d_v1",
    )
    home_flow_2604_publish_user_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_publish_user_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="publish_user",
        primary_key="publish_user",
        register=True,
    )
home_flow_2604_publish_user_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_publish_user_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_publish_user_static_feat_15d_v1_config)
home_flow_2604_publish_user_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_publish_user_static_feat_3d_v1"
)
if home_flow_2604_publish_user_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_publish_user_static_feat_3d_v1",
    )
    home_flow_2604_publish_user_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_publish_user_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="publish_user",
        primary_key="publish_user",
        register=True,
    )
home_flow_2604_publish_user_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_publish_user_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_publish_user_static_feat_3d_v1_config)
home_flow_2604_publish_user_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_publish_user_static_feat_1d_v1"
)
if home_flow_2604_publish_user_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_publish_user_static_feat_1d_v1",
    )
    home_flow_2604_publish_user_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_publish_user_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="publish_user",
        primary_key="publish_user",
        register=True,
    )
home_flow_2604_publish_user_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_publish_user_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_publish_user_static_feat_1d_v1_config)
home_flow_2604_username_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_username_static_feat_15d_v1"
)
if home_flow_2604_username_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_username_static_feat_15d_v1",
    )
    home_flow_2604_username_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_username_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="username",
        primary_key="username",
        register=True,
    )
home_flow_2604_username_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_username_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_username_static_feat_15d_v1_config)
home_flow_2604_username_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_username_static_feat_3d_v1"
)
if home_flow_2604_username_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_username_static_feat_3d_v1",
    )
    home_flow_2604_username_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_username_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="username",
        primary_key="username",
        register=True,
    )
home_flow_2604_username_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_username_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_username_static_feat_3d_v1_config)
home_flow_2604_username_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_username_static_feat_1d_v1"
)
if home_flow_2604_username_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_username_static_feat_1d_v1",
    )
    home_flow_2604_username_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_username_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="username",
        primary_key="username",
        register=True,
    )
home_flow_2604_username_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_username_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_username_static_feat_1d_v1_config)
home_flow_2604_item_id_static_feat_15d_v1 = project.get_feature_view(
    "home_flow_2604_item_id_static_feat_15d_v1"
)
if home_flow_2604_item_id_static_feat_15d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_item_id_static_feat_15d_v1",
    )
    home_flow_2604_item_id_static_feat_15d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_item_id_static_feat_15d_v1",
        datasource=ds,
        online=True,
        entity="item",
        primary_key="item_id",
        register=True,
    )
home_flow_2604_item_id_static_feat_15d_v1_config = FeatureViewConfig(
    name="home_flow_2604_item_id_static_feat_15d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_item_id_static_feat_15d_v1_config)
home_flow_2604_item_id_static_feat_3d_v1 = project.get_feature_view(
    "home_flow_2604_item_id_static_feat_3d_v1"
)
if home_flow_2604_item_id_static_feat_3d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_item_id_static_feat_3d_v1",
    )
    home_flow_2604_item_id_static_feat_3d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_item_id_static_feat_3d_v1",
        datasource=ds,
        online=True,
        entity="item",
        primary_key="item_id",
        register=True,
    )
home_flow_2604_item_id_static_feat_3d_v1_config = FeatureViewConfig(
    name="home_flow_2604_item_id_static_feat_3d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_item_id_static_feat_3d_v1_config)
home_flow_2604_item_id_static_feat_1d_v1 = project.get_feature_view(
    "home_flow_2604_item_id_static_feat_1d_v1"
)
if home_flow_2604_item_id_static_feat_1d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_item_id_static_feat_1d_v1",
    )
    home_flow_2604_item_id_static_feat_1d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_item_id_static_feat_1d_v1",
        datasource=ds,
        online=True,
        entity="item",
        primary_key="item_id",
        register=True,
    )
home_flow_2604_item_id_static_feat_1d_v1_config = FeatureViewConfig(
    name="home_flow_2604_item_id_static_feat_1d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_item_id_static_feat_1d_v1_config)

home_flow_2604_item_id_rt_statistic_feat_v1 = project.get_feature_view(
    "home_flow_2604_item_id_rt_statistic_feat_v1"
)
if home_flow_2604_item_id_rt_statistic_feat_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_item_id_rt_statistic_feat_v1",
    )
    home_flow_2604_item_id_rt_statistic_feat_v1 = project.create_stream_feature_view(
        name="home_flow_2604_item_id_rt_statistic_feat_v1",
        datasource=ds,
        online=True,
        entity="item",
        primary_key="item_id",
        register=True,
    )
home_flow_2604_item_id_rt_statistic_feat_v1_config = FeatureViewConfig(
    name="home_flow_2604_item_id_rt_statistic_feat_v1",
    partition_config=PartitionConfig(name="dt", value=cur_day),
    second_join_key="request_id",
    use_mock=True,
)
feature_view_config_list.append(home_flow_2604_item_id_rt_statistic_feat_v1_config)
home_flow_2604_mmb_id_rt_statistic_feat_v1 = project.get_feature_view(
    "home_flow_2604_mmb_id_rt_statistic_feat_v1"
)
if home_flow_2604_mmb_id_rt_statistic_feat_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_mmb_id_rt_statistic_feat_v1",
    )
    home_flow_2604_mmb_id_rt_statistic_feat_v1 = project.create_stream_feature_view(
        name="home_flow_2604_mmb_id_rt_statistic_feat_v1",
        datasource=ds,
        online=True,
        entity="user",
        primary_key="mmb_id",
        register=True,
    )
home_flow_2604_mmb_id_rt_statistic_feat_v1_config = FeatureViewConfig(
    name="home_flow_2604_mmb_id_rt_statistic_feat_v1",
    partition_config=PartitionConfig(name="dt", value=cur_day),
    second_join_key="request_id",
    use_mock=True,
)
feature_view_config_list.append(home_flow_2604_mmb_id_rt_statistic_feat_v1_config)

home_flow_2604_mmb_id_all_seq_feat_v3 = project.get_feature_view(
    "home_flow_2604_mmb_id_all_seq_feat_v3"
)
if home_flow_2604_mmb_id_all_seq_feat_v3 is None:
    raise ValueError(
        "home_flow_2604_mmb_id_all_seq_feat_v3 is None, please run feature_view_create_sync script to create feature view."
    )
home_flow_2604_mmb_id_all_seq_feat_v3_config = FeatureViewConfig(
    name="home_flow_2604_mmb_id_all_seq_feat_v3",
    partition_config=PartitionConfig(name="dt", value=cur_day),
    second_join_key="request_id",
    equal=True,
)
feature_view_config_list.append(home_flow_2604_mmb_id_all_seq_feat_v3_config)

## 用户统计特征
home_flow_2604_ads_usr_user_tag_info_preprocess_v1 = project.get_feature_view(
    "home_flow_2604_ads_usr_user_tag_info_preprocess_v1"
)
if home_flow_2604_ads_usr_user_tag_info_preprocess_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_ads_usr_user_tag_info_preprocess_v1",
    )
    home_flow_2604_ads_usr_user_tag_info_preprocess_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_ads_usr_user_tag_info_preprocess_v1",
            datasource=ds,
            online=True,
            entity="user",
            primary_key="mmb_id",
            register=True,
        )
    )
home_flow_2604_ads_usr_user_tag_info_preprocess_v1_config = FeatureViewConfig(
    name="home_flow_2604_ads_usr_user_tag_info_preprocess_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(
    home_flow_2604_ads_usr_user_tag_info_preprocess_v1_config
)

home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1 = (
    project.get_feature_view(
        "home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1"
    )
)
if home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1",
    )
    home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1 = (
        project.create_batch_feature_view(
            name="home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1",
            datasource=ds,
            online=True,
            entity="item",
            primary_key="item_id",
            register=True,
        )
    )
home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1_config = (
    FeatureViewConfig(
        name="home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1",
        partition_config=PartitionConfig(name="dt", value=pre_day),
    )
)
feature_view_config_list.append(
    home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1_config
)

## 用户长期兴趣开始
home_flow_2604_mmb_id_static_feat_60d_v1 = project.get_feature_view(
    "home_flow_2604_mmb_id_static_feat_60d_v1"
)
if home_flow_2604_mmb_id_static_feat_60d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_mmb_id_static_feat_60d_v1",
    )
    home_flow_2604_mmb_id_static_feat_60d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_mmb_id_static_feat_60d_v1",
        datasource=ds,
        online=True,
        entity="user",
        primary_key="mmb_id",
        register=True,
    )
home_flow_2604_mmb_id_static_feat_60d_v1_config = FeatureViewConfig(
    name="home_flow_2604_mmb_id_static_feat_60d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_mmb_id_static_feat_60d_v1_config)

home_flow_2604_mmb_id_static_feat_360d_v1 = project.get_feature_view(
    "home_flow_2604_mmb_id_static_feat_360d_v1"
)
if home_flow_2604_mmb_id_static_feat_360d_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_mmb_id_static_feat_360d_v1",
    )
    home_flow_2604_mmb_id_static_feat_360d_v1 = project.create_batch_feature_view(
        name="home_flow_2604_mmb_id_static_feat_360d_v1",
        datasource=ds,
        online=True,
        entity="user",
        primary_key="mmb_id",
        register=True,
    )
home_flow_2604_mmb_id_static_feat_360d_v1_config = FeatureViewConfig(
    name="home_flow_2604_mmb_id_static_feat_360d_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_mmb_id_static_feat_360d_v1_config)

home_flow_2604_mmb_id_static_feat_60d_ctr_v1 = project.get_feature_view(
    "home_flow_2604_mmb_id_static_feat_60d_ctr_v1"
)
if home_flow_2604_mmb_id_static_feat_60d_ctr_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_mmb_id_static_feat_60d_ctr_v1",
    )
    home_flow_2604_mmb_id_static_feat_60d_ctr_v1 = project.create_batch_feature_view(
        name="home_flow_2604_mmb_id_static_feat_60d_ctr_v1",
        datasource=ds,
        online=True,
        entity="user",
        primary_key="mmb_id",
        register=True,
    )
home_flow_2604_mmb_id_static_feat_60d_ctr_v1_config = FeatureViewConfig(
    name="home_flow_2604_mmb_id_static_feat_60d_ctr_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_mmb_id_static_feat_60d_ctr_v1_config)

home_flow_2604_mmb_id_static_feat_360d_ctr_v1 = project.get_feature_view(
    "home_flow_2604_mmb_id_static_feat_360d_ctr_v1"
)
if home_flow_2604_mmb_id_static_feat_360d_ctr_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_mmb_id_static_feat_360d_ctr_v1",
    )
    home_flow_2604_mmb_id_static_feat_360d_ctr_v1 = project.create_batch_feature_view(
        name="home_flow_2604_mmb_id_static_feat_360d_ctr_v1",
        datasource=ds,
        online=True,
        entity="user",
        primary_key="mmb_id",
        register=True,
    )
home_flow_2604_mmb_id_static_feat_360d_ctr_v1_config = FeatureViewConfig(
    name="home_flow_2604_mmb_id_static_feat_360d_ctr_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_mmb_id_static_feat_360d_ctr_v1_config)

home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1 = project.get_feature_view(
    "home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1"
)
if home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1 is None:
    ds = MaxComputeDataSource(
        data_source_id=project.offline_datasource_id,
        table="home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1",
    )
    home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1 = project.create_batch_feature_view(
        name="home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1",
        datasource=ds,
        online=True,
        entity="user",
        primary_key="mmb_id",
        register=True,
    )
home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1_config = FeatureViewConfig(
    name="home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1",
    partition_config=PartitionConfig(name="dt", value=pre_day),
)
feature_view_config_list.append(home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1_config)
## 用户长期兴趣结束

label_partitions = PartitionConfig(name="dt", value=cur_day)
label_input_config = LabelInputConfig(partition_config=label_partitions)
train_set_partitions = PartitionConfig(name="dt", value=cur_day)
train_set_output_config = TrainSetOutputConfig(partition_config=train_set_partitions)

model_name = "home_flow_2604_ctrcvr_sorter_v6"
cur_model = project.get_model(model_name)
if cur_model is None:
    print("start create model")
    output_ds = MaxComputeDataSource(data_source_id=project.offline_datasource_id)
    train_set_output = TrainingSetOutput(output_ds)
    label_table = project.get_label_table("home_flow_2604_ctrcvr_sorter_label_table_v1")
    if label_table is None:
        print("start create label table")
        label_ds = MaxComputeDataSource(
            data_source_id=project.offline_datasource_id,
            table="home_flow_2604_ctrcvr_sorter_label_table_v1",
        )
        label_table = project.create_label_table(label_ds, event_time="event_unix_time")

    feature_select_list = []
    feature_select_list.append(
        FeatureSelector("home_flow_2604_ads_usr_user_basic_info_preprocess_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector(
            "home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3", "*"
        )
    )
    # feature_select_list.append(FeatureSelector('feed_rec_flow_item_title_embedding_v5', '*'))
    feature_select_list.append(
        FeatureSelector("home_flow_2604_gender_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_age_group_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_login_city_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_dev_brand_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_mmb_id_static_feat_15d_v1_agg", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_first_cate_id_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_first_cate_id_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_first_cate_id_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_second_cate_id_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_second_cate_id_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_second_cate_id_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_cate_id_path_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_cate_id_path_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_cate_id_path_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_brand_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_brand_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_brand_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_site_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_site_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_site_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_core_entity_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_core_entity_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_core_entity_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_price_tag_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_price_tag_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_price_tag_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_promotion_channel_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_promotion_channel_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_promotion_channel_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_discount_intensity_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_discount_intensity_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_discount_intensity_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_dianpupingfen_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_dianpupingfen_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_dianpupingfen_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_pinpaidengji_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_pinpaidengji_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_pinpaidengji_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_spu_id_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_spu_id_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_spu_id_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_publish_user_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_publish_user_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_publish_user_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_username_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_username_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_username_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_item_id_static_feat_15d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_item_id_static_feat_3d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_item_id_static_feat_1d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_item_id_rt_statistic_feat_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_mmb_id_rt_statistic_feat_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_mmb_id_all_seq_feat_v3", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_ads_usr_user_tag_info_preprocess_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector(
            "home_flow_2604_ads_log_zhekou_rec_item_tag_info_preprocess_v1", "*"
        )
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_mmb_id_static_feat_60d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_mmb_id_static_feat_360d_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_mmb_id_static_feat_60d_ctr_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_mmb_id_static_feat_360d_ctr_v1", "*")
    )
    feature_select_list.append(
        FeatureSelector("home_flow_2604_mmb_id_other_bhv_pre_t_seq_v1", "*")
    )
    train_set = project.create_training_set(
        train_set_output=train_set_output,
        feature_selectors=feature_select_list,
        label_table_name="home_flow_2604_ctrcvr_sorter_label_table_v1",
    )
    # 如果是 label 表优先，即特征优先从 label 表取，则设置 label_priority_level 为 1.
    # 如果是特征视图优先，即特征优先从特征视图取，则设置  label_priority_level 为 2.
    cur_model = project.create_model(model_name, train_set, label_priority_level=1)
# task = cur_model.export_train_set(label_input_config, feature_view_config_list, train_set_output_config)
# task.wait()
# task.print_summary()
# output_table_name = 'feature_mall_home_flow_2604_ctrcvr_sorter_v2_training_set'
# output_table_result = o.execute_sql(f'select count(*) from {output_table_name} where dt = {cur_day};')
# with output_table_result.open_reader() as reader:
#     for record in reader:
#         print(f"分区表 {output_table_name} 在业务日期 {cur_day} 的总条数为: {record[0]}")
#         if record[0] == '0':
#             raise ValueError("training set is None.")
