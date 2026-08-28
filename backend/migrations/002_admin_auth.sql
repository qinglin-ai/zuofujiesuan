-- 左辅云创 · 阶段五管理后台鉴权扩展
-- users 表新增 password_hash，供 admin 账号密码登录使用(role=admin + 密码校验)。
USE zuofu_parttime;

ALTER TABLE users
    ADD COLUMN password_hash VARCHAR(255) NULL COMMENT 'admin 登录密码哈希' AFTER inviter_openid;