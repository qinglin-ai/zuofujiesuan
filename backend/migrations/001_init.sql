-- 左辅云创 · 兼职人员管理 初始建表脚本（对应《数据库结构说明.md》）
-- 数据库：MySQL 8.0+，utf8mb4；预先创建库：CREATE DATABASE IF NOT EXISTS zuofu_parttime DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 1. users 用户表
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    openid          VARCHAR(64)  NOT NULL COMMENT '微信 openid，唯一',
    phone           VARCHAR(20)  NOT NULL COMMENT '手机号，唯一',
    real_name       VARCHAR(50)  NOT NULL COMMENT '真实姓名',
    avatar          VARCHAR(255)          COMMENT '头像URL',
    nickname        VARCHAR(50)          COMMENT '昵称',
    role            ENUM('worker','admin') NOT NULL DEFAULT 'worker',
    approval_status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
    status          ENUM('active','blocked') NOT NULL DEFAULT 'active',
    bank_info       JSON                 COMMENT '提现账户{bankName,cardNo,cardHolder}',
    inviter_openid  VARCHAR(64)          COMMENT '邀请人openid',
    create_time     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_openid (openid),          -- 一人一账户
    UNIQUE KEY uk_users_phone (phone),            -- 防重复注册
    KEY idx_users_approval_status (approval_status),
    KEY idx_users_status (status),
    KEY idx_users_role (role),
    KEY idx_users_status_role (status, role)
) ENGINE=InnoDB COMMENT='用户表';

-- 2. balances 用户佣金账户表
CREATE TABLE IF NOT EXISTS balances (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    openid            VARCHAR(64)  NOT NULL,
    available_balance DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '可提现余额',
    update_time       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_balances_openid (openid)        -- 一人一账户
) ENGINE=InnoDB COMMENT='用户佣金账户表';

-- 3. certifications 能力认证表
CREATE TABLE IF NOT EXISTS certifications (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    openid       VARCHAR(64) NOT NULL,
    task_id      BIGINT UNSIGNED NOT NULL,
    task_name    VARCHAR(100),
    annot_type   ENUM('shadow','light_source','reflection','exposure','filter'),
    level        ENUM('junior','middle','senior'),
    exam_passed  TINYINT(1) NOT NULL DEFAULT 0,
    pass_rate    DECIMAL(5,2),
    reviewed_by  VARCHAR(64),
    review_time  DATETIME,
    update_time  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_cert_openid_task_annot (openid, task_id, annot_type),
    KEY idx_cert_task_id (task_id)
) ENGINE=InnoDB COMMENT='能力认证表';

-- 4. tasks 任务表
CREATE TABLE IF NOT EXISTS tasks (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    title          VARCHAR(100) NOT NULL,
    annot_type     ENUM('shadow','light_source','reflection','exposure','filter'),
    quantity       INT NOT NULL COMMENT '单人任务量',
    claimed_count  INT NOT NULL DEFAULT 0 COMMENT '已领取人数',
    total_people   INT NOT NULL COMMENT '总人数(任务最大领取人数)',
    unit_price     DECIMAL(10,2) NOT NULL COMMENT '单个作业佣金(非quantity*price)',
    difficulty     ENUM('junior','middle','senior'),
    require_level  ENUM('junior','middle','senior'),
    deadline       DATETIME,
    status         ENUM('open','inProgress','closed') NOT NULL DEFAULT 'open',
    owner_id       BIGINT UNSIGNED NOT NULL,
    forbidden_items JSON,
    sample_url     VARCHAR(255),
    create_time    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_tasks_status (status),
    KEY idx_tasks_annot_type (annot_type),
    KEY idx_tasks_deadline (deadline),
    KEY idx_tasks_status_annot (status, annot_type)
) ENGINE=InnoDB COMMENT='任务表';

-- 5. assignments 领单/作业表
CREATE TABLE IF NOT EXISTS assignments (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    openid           VARCHAR(64) NOT NULL,
    task_id          BIGINT UNSIGNED NOT NULL,
    task_name        VARCHAR(100),
    status           ENUM('claimed','submitted','passed','rejected') NOT NULL DEFAULT 'claimed',
    zh_instruction   TEXT,
    en_instruction   TEXT,
    submit_time      DATETIME,
    checked_by       VARCHAR(64),
    audit_time       DATETIME,
    finish_time      DATETIME,
    PRIMARY KEY (id),
    UNIQUE KEY uk_assign_openid_task (openid, task_id),   -- 一人一任务仅一条(防重复领取)
    KEY idx_assign_openid (openid),
    KEY idx_assign_task_id (task_id),
    KEY idx_assign_status (status),
    KEY idx_assign_checked_by (checked_by),               -- 管理员待核验列表按人查
    KEY idx_assign_openid_status (openid, status),
    KEY idx_assign_task_status (task_id, status)
) ENGINE=InnoDB COMMENT='领单/作业表';

-- 6. quality_checks 外部核验结果表
CREATE TABLE IF NOT EXISTS quality_checks (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    assignment_id   BIGINT UNSIGNED NOT NULL,
    openid          VARCHAR(64) NOT NULL,
    task_id         BIGINT UNSIGNED NOT NULL,
    checked_by      VARCHAR(64),
    result          ENUM('pass','reject') NOT NULL,
    external_ref_no VARCHAR(64)          COMMENT '外部核验单号',
    remark          VARCHAR(255),
    check_time      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_qc_assignment (assignment_id),        -- 同一作业重复核验回写防护
    KEY idx_qc_openid (openid),
    KEY idx_qc_task_id (task_id),
    KEY idx_qc_result (result),
    KEY idx_qc_external_ref_no (external_ref_no)        -- 跨系统回查频繁
) ENGINE=InnoDB COMMENT='外部核验结果表';

-- 7. commissions 佣金流水表
CREATE TABLE IF NOT EXISTS commissions (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    openid        VARCHAR(64) NOT NULL,
    task_id       BIGINT UNSIGNED NOT NULL,
    assignment_id BIGINT UNSIGNED NOT NULL,
    amount        DECIMAL(10,2) NOT NULL COMMENT '佣金=来源任务单价',
    settle_date   DATE NOT NULL COMMENT '入账日期(记录到日)',
    create_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_comm_assignment (assignment_id),     -- 防重复结算(幂等)
    KEY idx_comm_openid (openid),
    KEY idx_comm_settle_date (settle_date),
    KEY idx_comm_openid_settle (openid, settle_date),
    KEY idx_comm_task_id (task_id),
    KEY idx_comm_settle_openid (settle_date, openid)   -- 对账报表按日聚合
) ENGINE=InnoDB COMMENT='佣金流水表';

-- 8. withdrawals 提现表(免审核)
CREATE TABLE IF NOT EXISTS withdrawals (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    openid       VARCHAR(64) NOT NULL,
    amount       DECIMAL(10,2) NOT NULL,
    bank_account JSON COMMENT '收款账户快照',
    status       ENUM('pending','paid','rejected') NOT NULL DEFAULT 'pending',
    pay_ref_no   VARCHAR(64) COMMENT '微信支付/商户单号',
    paid_source  ENUM('auto','manual') COMMENT '到账回写路径',
    apply_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_time    DATETIME,
    PRIMARY KEY (id),
    KEY idx_wd_openid (openid),
    KEY idx_wd_status (status),
    KEY idx_wd_openid_status (openid, status)
) ENGINE=InnoDB COMMENT='提现表';

-- 9. violations 违规表
CREATE TABLE IF NOT EXISTS violations (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    openid        VARCHAR(64) NOT NULL,
    user_name     VARCHAR(50),
    type          ENUM('alter_original','edit_jitter','submit_irrelevant','other'),
    punish_level  ENUM('warning','suspend','block'),
    reason        VARCHAR(255),
    operator_id   BIGINT UNSIGNED NOT NULL,
    create_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_vio_openid (openid),
    KEY idx_vio_type (type)
) ENGINE=InnoDB COMMENT='违规表';

-- 10. notices 公告表
CREATE TABLE IF NOT EXISTS notices (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    title       VARCHAR(100) NOT NULL,
    content     TEXT NOT NULL,
    target      ENUM('all','worker','admin','skill') NOT NULL DEFAULT 'all',
    type        ENUM('notice','flow','project','faq') NOT NULL DEFAULT 'notice',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_notices_type (type),
    KEY idx_notices_create_time (create_time)
) ENGINE=InnoDB COMMENT='公告表';