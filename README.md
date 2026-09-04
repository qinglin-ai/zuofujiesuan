# 左辅云创 · 兼职人员管理小程序

前后端分离的兼职作业管理平台：微信原生小程序（兼职端）+ Flask/MySQL（后端 API）+ Flask 静态托管的 Web 管理后台。

> 覆盖任务全生命周期与资金结算链路：注册审批 → 能力认证 → 领单 → 作业提交 → 外部核验 → 佣金入账 → 提现 → 台账对账导出。

## 架构

| 端 | 技术栈 | 说明 |
|----|--------|------|
| 兼职小程序 | 微信原生小程序（WXML/WXSS/JS） | 任务列表/详情、我的作业、我的资金、公告动态、用户（底部 tabBar） |
| 后端 API | Flask + SQLAlchemy + PyJWT + PyMySQL | REST 风格 `{code, message, data}`，JWT 鉴权 |
| 管理后台 H5 | Flask 静态页（HTML/CSS/JS） | `/admin` 入口，用户/核验/认证/提现/台账/违规/公告管理 |
| 数据库 | MySQL 8（utf8mb4） | docker 或本机均可 |

## 目录结构

```
weixinapp/
├── backend/
│   ├── app/
│   │   ├── api/          # 蓝图：auth/users/certifications/tasks/quality/violations/notices/wallet/health
│   │   ├── static/admin/ # 管理后台 H5（index.html + css/js）
│   │   ├── models.py     # 数据模型（含唯一约束/索引）
│   │   ├── config.py     # 配置（读环境变量）
│   │   ├── auth/         # JWT 鉴权、微信 code→openid
│   │   ├── cli.py        # Flask CLI（seed-admin）
│   │   └── __init__.py   # 应用工厂
│   ├── migrations/       # 建表脚本（001_init.sql、002_admin_auth.sql）
│   ├── requirements.txt
│   └── wsgi.py           # 本地入口：python wsgi.py
├── miniprogram/          # 兼职端原生小程序（app.json/tabBar + pages/）
└── docs/                 # 需求/架构/数据库/任务拆解/进度文档
```

## 快速开始

### 1. Docker 一键部署（推荐）

```bash
# 1) 准备环境变量
cp .env.example .env
#    编辑 .env：填写 MYSQL_ROOT_PASSWORD / MYSQL_APP_PASSWORD / JWT_SECRET / WX_APPID / WX_SECRET

# 2) 启动（MySQL 首启自动建库建表，执行 backend/migrations/*.sql）
docker compose up -d --build
```

服务地址：

- 后端 API：`http://<host>:5000`
- 健康检查：`http://<host>:5000/api/health/ping`、`/api/health/db`
- 管理后台：`http://<host>:5000/admin`

> **⚠️ 已有数据卷时的注意事项**：`docker-entrypoint-initdb.d` 仅在新数据卷**首次启动**时执行一次。若后端更新后会新增 migration，需手动对运行中的 MySQL 补执行，否则数据库缺少新列会导致接口报 `1054 Unknown column`。手动补迁移示例：
>
> ```bash
> docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" < /docker-entrypoint-initdb.d/002_admin_auth.sql'
> ```

### 2. 本地直跑后端（不依赖 Docker）

```bash
cd backend
cp .env.example .env    # 填写 DB_URI / JWT_SECRET / WX_APPID / WX_SECRET
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py          # 默认 http://127.0.0.1:5000
```

## 初始化管理后台账号

管理后台需管理员账号密码登录（`POST /api/auth/admin/login`）。通过 `flask seed-admin` 将已有用户设为 admin 并设置密码：

```bash
# Docker 环境
docker compose exec backend flask seed-admin --account 手机号或姓名 --password 你的密码

# 本地环境（激活虚拟环境后）
flask --app app seed-admin --account 手机号或姓名 --password 你的密码
```

> 前提：该用户需已通过微信小程序登录建档（users 表存在该记录）。

## 核心业务与资金口径

| 环节 | 说明 |
|------|------|
| 任务领取 | 唯一索引 `(openid, task_id)` + 事务条件自增，并发不超领 |
| 作业提交/核验 | `claimed → submitted → passed/rejected`，`quality_checks.assignment_id` 唯一防重复回写 |
| 佣金入账 | 核验通过即结算：`commissions.amount = 提交数量 × 单价`；`commissions.assignment_id` 唯一索引幂等，同一事务内原子更新余额 |
| 提现 | 免审核，`amount ≤ available_balance`，事务内扣减并写 `withdrawals(pending→paid)`。<br>**默认走微信「商家转账到零钱」自动打款（T4-6）**：申请即自动发起，防重先查单再换单重试（≤1 次），异步回调回写；未启用自动打款时回退**半自动 manual**（财务后台确认到账）。真实自动打款需在 `.env` 配置微信商户凭据（见下方依赖提示） |
| 台账对账 | `GET /api/wallet/ledger` 按日聚合佣金+提现，含汇总行，支持 JSON/CSV/Excel（T4-5 / T5-5） |

> **⚠️ 待联调依赖（提现为最敏感功能）**：**T4-6 微信自动打款已编码实现并通过 mock/防重单测**，但**未配置真实商户凭据，尚未实机联调**。正式上线需：①开通微信支付商户号并申请「商家转账」权限（D6/O3）；②`.env` 配置 `WXPAY_ENABLED=1` + 商户号/APIv3密钥/证书/公钥/回调地址；③存量 MySQL 卷手动执行 `003_wxpay_withdrawal.sql`。**联调通过前保持 `WXPAY_ENABLED=0`，线上提现仍依赖财务人工确认到账。**

## 安全约定

- 敏感凭据（`AppID`、`AppSecret`、`JWT_SECRET`、微信支付商户号/APIv3密钥）只存于 `.env`；`.env` 已 git 忽略，**禁止提交入库**。仓库内仅保留占位模板 `.env.example`。
- 微信支付商户 API 私钥、微信支付公钥放入 `backend/certs/`（`.gitignore` 已忽略，仅保留 `.gitkeep` 占位）。
- API 统一 `login_required` / `require_role("admin")` 鉴权；`balances` 等资金数据仅本人可读。
- 资金写操作均在事务中执行（入账、扣减余额）。

## 文档索引

详细设计与进度见 `docs/`：

- `系统架构与开发规划.md` — 七阶段规划与架构
- `需求清单.md` / `数据库结构说明.md` / `业务逻辑说明.md` / `技术机制预研.md` / `原型与UI设计.md`
- `开发任务拆解表.md` — 任务级拆解与工时
- `项目进度与文档导航.md` — 阶段进度与导航（当前：阶段一~五完成 ✅；阶段四 T4-6 微信自动打款已编码实现，待真实商户凭据实机联调）
- `文档变更记录.md` — 变更登记

## 技术要点

- MySQL 8 认证需 `cryptography` 依赖（requirements 已含）。
- `commissions` 不额外存储“提交数量”字段，金额可按 `amount ÷ 单价` 反算核对。
- 管理后台台账导出复用 T4-5 接口，下载页在「台账 / 对账」菜单（T5-5）。