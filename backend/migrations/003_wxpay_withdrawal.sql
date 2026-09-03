-- 左辅云创 · 微信支付「商家转账到零钱」自动打款扩展
-- withdrawals 表新增自动打款相关字段：
--   out_bill_no        商户转账单号（商户内唯一，唯一索引；notify 定位键 + 防重复创建键）
--   transfer_bill_no   微信转账单号（最新一次，对账用）
--   transfer_status    微信侧单据状态镜像（ACCEPTED/PROCESSING/.../SUCCESS/FAIL）
--   transfer_time      转账终态时间
--   fail_reason        最终失败原因（向用户/财务展示）
--   retry_count        因 FAIL 自动换单重试的次数
USE zuofu_parttime;

ALTER TABLE withdrawals
    ADD COLUMN out_bill_no VARCHAR(64) NULL COMMENT '商户转账单号(自动打款,商户内唯一)' AFTER paid_source,
    ADD COLUMN transfer_bill_no VARCHAR(64) NULL COMMENT '微信转账单号(最新一次)' AFTER out_bill_no,
    ADD COLUMN transfer_status VARCHAR(20) NULL COMMENT '微信侧单据状态镜像' AFTER transfer_bill_no,
    ADD COLUMN transfer_time DATETIME NULL COMMENT '转账终态时间' AFTER transfer_status,
    ADD COLUMN fail_reason VARCHAR(255) NULL COMMENT '最终失败原因' AFTER transfer_time,
    ADD COLUMN retry_count INT NOT NULL DEFAULT 0 COMMENT '因FAIL换单重试次数' AFTER fail_reason,
    ADD UNIQUE KEY uk_wd_out_bill_no (out_bill_no),
    ADD KEY idx_wd_transfer_status (transfer_status);

-- 注意：docker-entrypoint-initdb.d 仅首启执行一次；存量 mysql_data 卷需手动补跑本脚本，
-- 否则触发 1054 Unknown column 错误（schema 脱节）。
