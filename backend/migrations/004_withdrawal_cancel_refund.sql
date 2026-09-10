-- 左辅云创 · 微信转账「用户确认模式」CANCELLED 收口扩展
-- withdrawals 表新增 balance_refunded 标记：
--   balance_refunded  CANCELLED（转账因超时未确认被微信取消，钱已退回商户账户）且换单重试耗尽后，
--                    余额已退回用户可提现余额，置 1。用于：①区分「确定性 FAIL 转人工补发」与
--                    「CANCELLED 已退余额」两类 rejected 单；②阻止管理员对已退回单重复「失败补发」（防重复打款）。
USE zuofu_parttime;

ALTER TABLE withdrawals
    ADD COLUMN balance_refunded TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'CANCELLED重试耗尽后余额是否已退回用户' AFTER retry_count;

-- 注意：docker-entrypoint-initdb.d 仅首启执行一次；存量 mysql_data 卷需手动补跑本脚本，
-- 否则触发 1054 Unknown column 错误（schema 脱节）。
