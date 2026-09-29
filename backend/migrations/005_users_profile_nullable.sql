-- 005_users_profile_nullable.sql
-- 用户信息绑定：users.phone / users.real_name 改为可空。
-- 背景：登录即建档写入占位空串 ''，而 phone 上有唯一索引 uk_users_phone，
--       第 2 个新用户登录时会因 '' 重复违反唯一约束（500 错误）。
--       改为 NULL 后，未绑定用户不占用唯一索引，互不冲突。
-- 同时把历史空串归一为 NULL。
-- 执行：docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" < /docker-entrypoint-initdb.d/005_users_profile_nullable.sql'

USE zuofu_parttime;

-- 1. 历史空串归一为 NULL（先解除空串对唯一索引的占用）
UPDATE users SET phone = NULL WHERE phone = '';
UPDATE users SET real_name = NULL WHERE real_name = '';

-- 2. 改为可空
ALTER TABLE users MODIFY COLUMN phone     VARCHAR(20) NULL COMMENT '手机号，唯一；未绑定为 NULL';
ALTER TABLE users MODIFY COLUMN real_name VARCHAR(50) NULL COMMENT '真实姓名；未绑定为 NULL';