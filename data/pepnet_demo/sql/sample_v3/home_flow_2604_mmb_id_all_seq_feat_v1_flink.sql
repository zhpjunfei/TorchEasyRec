--********************************************************************--
-- Author:         rankang
-- Created Time:   2026-05-06 13:16:57
-- Description:    Write your description here
-- Hints:          You can use SET statements to modify the configuration
--********************************************************************--

CREATE TEMPORARY TABLE sls_user_bhv_log
(
    request_id  string
    ,`bhv_type` STRING
    ,doc_id     string
    ,user_id    string
    ,bhv_time   bigint
    ,`__topic__` STRING METADATA VIRTUAL
    ,`__source__` STRING METADATA VIRTUAL
    ,`__timestamp__` STRING METADATA VIRTUAL
    ,__tag__ MAP<VARCHAR, VARCHAR> METADATA VIRTUAL
    ,proctime as PROCTIME()
)
WITH (
    'connector' = 'sls'
    ,'endPoint' = 'cn-shenzhen-intranet.log.aliyuncs.com'
    ,'project' = 'mmb-zhekou-log'
    ,'logStore' = 'user-bhv-log'
    ,'accessId' = 'YOUR_ACCESS_ID'
    ,'accessKey' = 'gjMKVUTSj7eXlGL6zUGRBwZnfthRm6'
    ,'query' = '*| where user_id is not null and user_id != '''' and doc_id is not null and doc_id != '''''
)
;

CREATE TEMPORARY VIEW rec_realtime_user_bhv as
SELECT cast(__tag__['__receive_time__'] as bigint) as event_time
    ,bhv_type as event
    ,CAST(NULL AS STRING) as event_value
    ,doc_id as item_id
    ,user_id as mmb_id
    ,request_id as request_id
FROM sls_user_bhv_log
;

CREATE TEMPORARY TABLE mmb_id_all_seq_feat
(
    event_unix_time  bigint
    ,event           string
    ,item_id         string
    ,mmb_id          string
)
WITH (
    'connector' = 'featurestore'
    ,'region_id' = 'cn-shenzhen'
    ,'project' = 'feature_mall'
    ,'feature_view' = 'home_flow_2604_mmb_id_all_seq_feat_v1'
    ,'username' = 'mmbfeatures'
    ,'password' = 'MMB@Features0'
    ,'aliyun_access_id' = 'YOUR_ACCESS_ID'
    ,'aliyun_access_key' = 'YOUR_ACCESS_KEY'
)
;

INSERT INTO mmb_id_all_seq_feat
SELECT
    event_time
    ,event
    ,item_id
    ,mmb_id
FROM rec_realtime_user_bhv
WHERE event IN ('click','conversion','favorite')
;
