# NeatCopy 付费托管模型网关设计

日期：2026-06-10
状态：待用户评审
范围：产品设计、服务端架构、客户端改造、安全边界、落地流程

## 1. 背景

NeatCopy 当前已经支持两种处理路径：

- 本地规则模式：无需联网、无需 API Key，继续保持永久免费。
- 大模型模式：用户在设置中手动配置 OpenAI 兼容接口的 `Base URL`、`API Key`、`Model ID`，客户端直接调用 `{Base URL}/chat/completions`。

用户希望引入收费功能，但不是简单把现有功能锁起来。目标是保留免费用户的自带 API 配置能力，同时为付费用户提供免配置的托管模型体验。付费用户可以在 NeatCopy 中直接选择 Qwen、DeepSeek、豆包等模型，不再理解各平台控制台、接口地址、密钥和模型 ID。

参考文章的可复用思想是：客户端只负责展示、保存非敏感状态和验证授权；支付密钥、订单确认、私钥签发、真实服务调用都放在服务端。NeatCopy 相比文章中的插件多一层成本风险，因为付费版不只是解锁本地功能，还要由开发者承担模型调用成本，所以服务端必须同时做支付校验、订阅校验、模型代理、用量限制和风控。

## 2. 产品原则

1. 免费用户不降级。现有本地规则模式和自带 API 模式继续可用，不强迫用户购买。
2. 付费价值来自省配置和托管模型，而不是人为制造障碍。
3. 所有敏感密钥只存在服务端，包括支付平台密钥、模型供应商 API Key、license 私钥和后台管理 token。
4. 不能做无限量会员。第一版采用订阅配额或点数制，避免模型成本被滥用。
5. 默认不保存剪贴板原文和模型输出。服务端只记录用量、状态、错误类型和必要审计信息。
6. 自动化优先。购买、付款确认、激活、续费、模型选择、额度刷新都应尽量在客户端内完成。

## 3. 已确认决策

本节是后续实现计划的硬约束。除非用户明确变更，后续计划和代码都按这些决策执行。

### 3.1 商业与额度

- 收费模型：订阅 + 月度点数额度。
- 套餐周期：月付 + 年付，不做永久版。
- 价格：月付 9.9 元，年付 99 元。
- 额度：月付每月 500 点；年付每月刷新 500 点，不一次性发放全年额度。
- 点数扣减：每 1000 个输入+输出 token 扣 1 点，向上取整，并叠加模型倍率；无法从供应商获得 token 用量时按字符估算。
- 扣点时机：只有模型成功返回才扣点；请求前只做额度预检查。
- 点数用完：暂停 Pro 托管模型，提示等待下月刷新；第一版不做加购点数包。
- 免费试用：提供 7 天试用 + 100 点试用点数，试用点数作为服务端 catalog 配置项。
- 试用领取：邮箱或手机号任一验证即可领取；同账号、同设备、同风控主体只能领取一次。

### 3.2 账号、设备与登录

- 登录方式：邮箱验证码 + 手机号验证码。
- 账号绑定：同一用户可同时绑定邮箱和手机号，使用任一方式登录同一账号。
- 设备限制：每个 Pro 订阅最多绑定 2 台设备。
- 设备超限：阻止新设备使用 Pro，并提示用户到设备管理解绑；不自动挤掉旧设备。
- 用户自助页：做极简网页账号页，用于查看订阅、剩余额度、续费和解绑设备。
- 管理后台：做简单网页后台，不只做 API。
- 管理员登录：单管理员账号 + 强密码 + TOTP 双因素验证。
- 登录态：短 access token + 长 refresh token；access token 默认 30 分钟，refresh token 默认 90 天。
- 验证码限流：同邮箱/手机号 60 秒一次、每小时 5 次、每天 10 次；同 IP 每小时 30 次。

### 3.3 客户端体验

- 模型来源：自带 API 与 NeatCopy Pro 双轨并存。
- 登录、购买、设备管理：客户端打开网页完成；桌面端负责创建绑定会话、打开网页、轮询激活状态。
- 网页回传：使用绑定会话轮询，不做自定义 URL Scheme。
- 离线状态：离线时只展示最近一次授权状态；托管模型调用必须联网实时校验和扣点。
- 单次文本上限：Pro 托管模型每次最多 20,000 字符，超出后提示分段处理。
- 本地历史：Pro 请求沿用现有本地历史记录行为；服务端不保存原文和输出。
- 点数展示：客户端显示剩余点数 + 最近一次消耗。
- 到期提醒：第一版仅在客户端内提醒，不发邮件或短信提醒。
- 发布方式：同一个安装包内包含 Pro UI，由服务端 catalog 开关灰度控制。
- 最低版本：服务端 catalog 返回 `min_app_version`，低版本不允许 Pro 调用并提示升级。

### 3.4 模型与网关

- 首发国产模型供应商：DeepSeek、Qwen/通义千问、豆包、Kimi/Moonshot。
- 模型展示：客户端显示“品牌 + 友好模型名”，真实模型 ID 由服务端 catalog 控制。
- 模型目录、套餐、倍率、维护状态：服务端 catalog 动态下发，客户端只缓存最近一次用于展示。
- Gateway 接口：保持 OpenAI 兼容 `/chat/completions`。
- 流式输出：第一版不支持流式，保持一次性返回。
- 供应商故障：提示当前模型不可用，让用户手动切换，不自动替换模型。
- 供应商密钥：按 Key 池设计；第一版每家至少配置 1 个 Key，代码按多个 Key 可轮换实现。

### 3.5 服务端、支付与后台

- 服务端部署：第一版部署到 Cloudflare Workers + D1，但代码保持可迁移，不把业务逻辑写死在 Worker/D1。
- 服务端仓库：独立私有仓库；当前 NeatCopy 仓库只放客户端代码和接口契约文档。
- 支付平台：第一版主流程接 ZPAY。
- 支付测试：staging 使用 `FakePaymentProvider` 模拟支付成功，生产环境禁用；生产 ZPAY 仅做真实小额冒烟测试。
- 支付自动化：购买、回调、验签、订单确认、订阅发放、客户端激活全自动。
- 续费：手动续费，不做自动续费/代扣。
- 退款和取消：第一版人工处理，管理员后台标记退款或取消。
- 管理后台权限：后台绝不允许查看用户请求正文或模型输出。

### 3.6 隐私、风控与测试

- 服务端日志：只保存元数据，不保存剪贴板原文和模型输出。
- 用户自助页用量：只展示总剩余额度，不展示明细列表。
- 元数据和审计日志保留期：90 天。
- 账号注销和数据删除：第一版人工处理，按隐私说明执行删除或匿名化。
- 风控动作：异常用量先限速，再进入人工审核；不直接冻结，除非明确恶意或成本风险持续扩大。
- 测试环境：建立独立 staging 环境。
- 模型测试：staging 以 `FakeModelProvider` 为主，发布前对真实供应商做少量冒烟测试。
- 公开页面：购买页、隐私说明、使用说明、退款规则、服务条款。

## 4. 最终方案

采用 Free BYOK + Pro Gateway 的双轨方案。

Free BYOK 指免费用户自带 API Key：

- 客户端继续显示现有 `Base URL`、`API Key`、`Model ID`、`Temperature`、`Timeout` 配置。
- 调用链仍然是 NeatCopy 客户端直接请求用户配置的 OpenAI 兼容接口。
- 该路径不经过 NeatCopy 服务端，不产生开发者模型成本。

Pro Gateway 指付费用户使用 NeatCopy 托管模型：

- 客户端新增“模型来源”选择：自带 API 或 NeatCopy Pro。
- 选择 NeatCopy Pro 后，隐藏或弱化手动 API 配置，展示套餐状态、剩余额度、模型列表和购买入口。
- 客户端把请求发到 NeatCopy Gateway。
- Gateway 校验订阅、设备、额度、速率后，再转发到 Qwen、DeepSeek、豆包等供应商。
- Gateway 返回 OpenAI 兼容响应或规范化后的文本结果，客户端复用现有 LLM 成功/失败流程。

第一版不采用纯离线激活码解锁，因为它只能安全解锁本地功能，不能安全承载托管模型调用。付费用户使用托管模型额度时，服务端实时授权和用量扣减是必要边界。

## 5. 用户流程

### 5.1 免费用户

1. 打开设置页。
2. 选择大模型模式。
3. 模型来源保持“自带 API”。
4. 手动填写 `Base URL`、`API Key`、`Model ID`。
5. 点击测试连接。
6. 使用现有 Prompt 轮盘、预览面板、历史记录能力。

### 5.2 付费用户首次购买

1. 打开设置页的大模型页面。
2. 选择“NeatCopy Pro 托管模型”。
3. 客户端生成或读取本地 `installation_id`。
4. 客户端请求 `POST /api/binding-sessions`，创建设备绑定会话。
5. 客户端打开网页登录/购买页面，URL 中携带绑定会话 ID。
6. 用户在网页中使用邮箱验证码或手机号验证码登录。
7. 用户选择月付或年付并发起 ZPAY 支付。
8. 服务端创建订单并调用支付平台生成二维码或支付链接。
9. 网页展示二维码，并由网页或客户端轮询订单状态。
10. 支付平台回调 `POST /api/payment-notify`。
11. 服务端验签、验金额、验订单、幂等写入订阅和额度。
12. 服务端将绑定会话标记为可激活。
13. 客户端轮询到绑定成功，自动拉取订阅状态和 token。
14. 客户端显示 Pro 已激活、到期时间、剩余额度、最近一次消耗和可选模型。

### 5.3 付费用户调用模型

1. 用户复制文本并触发清洗。
2. 客户端根据 Prompt 轮盘选择具体任务。
3. 若模型来源是 NeatCopy Pro，客户端请求 `POST /api/chat/completions`。
4. Gateway 校验 token、订阅、设备绑定、模型权限、20,000 字符上限、月度点数和速率。
5. Gateway 根据服务端 catalog 将友好模型名映射到 DeepSeek、Qwen、豆包或 Kimi 的真实模型。
6. Gateway 调用真实供应商 API。
7. Gateway 成功后按 token/字符阶梯扣点，记录元数据和状态，不记录原文和结果正文。
8. 客户端收到结果，沿用现有写剪贴板、预览、历史记录流程。

### 5.4 续费与过期

1. 客户端启动或打开设置页时请求 `GET /api/subscription`。
2. 若订阅快过期，在 Pro 区域展示续费提示。
3. 若订阅过期，托管模型不可用，但自带 API 和本地规则模式继续可用。
4. 如果网络不可用，客户端可以显示最近一次缓存状态，但不能继续消耗 Pro 网关额度。

## 6. 客户端设计

### 6.1 配置结构

在 `llm` 配置下新增付费相关字段。字段命名如下：

```json
{
  "llm": {
    "provider_mode": "byok",
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model_id": "gpt-4o-mini",
    "managed": {
      "gateway_url": "",
      "installation_id": "local-generated-uuid",
      "access_token": "",
      "refresh_token": "",
      "selected_model": "deepseek-chat",
      "subscription_cached_until": "",
      "last_known_plan": "",
      "last_known_quota": null
    }
  }
}
```

`provider_mode` 取值：

- `byok`：用户自带 API，沿用现有直连逻辑。
- `managed`：NeatCopy Pro 托管模型，走 Gateway。

`gateway_url` 由正式发布配置写入，开发和测试环境可通过测试配置覆盖，避免把临时域名写入默认用户配置。

### 6.2 设置页

大模型页面新增一个模型来源区域：

- “自带 API”：显示现有 API 配置卡片。
- “NeatCopy Pro”：显示登录/激活状态、购买按钮、模型下拉框、套餐和额度。

Pro 区域最小可用内容：

- 当前状态：未激活、已激活、即将过期、已过期、额度不足。
- 登录/购买/续费按钮，点击后打开网页绑定会话。
- 模型选择：由 `GET /api/catalog` 返回。
- 剩余额度和最近一次消耗：按点数展示。
- 隐私说明：托管模型请求会经过 NeatCopy 服务端，默认不保存原文和输出。

### 6.3 调用层改造

当前 `src/clip_processor.py` 和 `src/llm_client.py` 都直接拼接 `{base_url}/chat/completions`。实施时应抽象一个 LLM Provider 边界：

- `ByokProvider`：现有逻辑，读取 `base_url`、`api_key`、`model_id`。
- `ManagedProvider`：读取 `gateway_url`、`access_token`、`selected_model`，请求 NeatCopy Gateway。
- `LLMClient`：只关心输入文本、Prompt、配置和返回结果，不关心具体供应商。

这样可以减少对现有剪贴板、预览、历史记录、轮盘逻辑的影响。

### 6.4 本地授权缓存

客户端可以缓存订阅状态用于展示，但不能把缓存当作可无限使用的授权依据。托管模型每次请求都必须由 Gateway 实时校验额度。

本地可缓存：

- `installation_id`
- 短期 `access_token`
- 90 天可轮换的 `refresh_token`
- 最近一次订阅摘要
- 最近一次模型目录

本地不保存：

- 支付平台密钥
- 模型供应商 API Key
- license 私钥
- 后台管理 token

## 7. 服务端设计

### 7.1 部署形态

第一版部署到 Cloudflare Workers + D1，但服务端代码放在独立私有仓库，并保持业务逻辑可迁移：

- Worker 承载 API、支付回调、模型网关、用户自助页和简单管理后台。
- D1 存储用户、登录身份、订单、订阅、设备、用量和审计日志。
- Secrets 存储支付密钥、模型供应商密钥、JWT/签名密钥、后台管理 token。

服务端代码应把业务逻辑、数据库访问和 Cloudflare runtime 适配层分开。若后续国内访问、支付回调或 D1 能力成为瓶颈，可以迁移到国内云函数、轻量服务器或 Postgres 后端，而不重写支付、订阅、用量和模型适配核心逻辑。

### 7.2 服务端模块

服务端拆分为以下边界：

- `payment`：创建订单、支付平台签名、支付回调验签、订单状态同步。
- `subscription`：套餐、到期时间、额度周期、续费合并。
- `license`：签发短期 token 和可验证的授权摘要。
- `model_gateway`：OpenAI 兼容入口、供应商路由、错误规范化。
- `providers`：Qwen、DeepSeek、豆包等模型供应商适配器。
- `usage`：用量预估、扣减、结算、异常回滚。
- `risk`：速率限制、设备限制、异常检测、封禁。
- `user_portal`：用户登录、购买、续费、订阅查看、设备解绑。
- `admin_web`：单管理员后台，支持订单查询、补单、退款标记、设备吊销、风控审核。

### 7.3 API 契约

最小 API 集合：

```text
GET  /api/catalog
POST /api/auth/send-code
POST /api/auth/verify-code
POST /api/binding-sessions
GET  /api/binding-sessions/:id
POST /api/create-payment
GET  /api/check-order
POST /api/payment-notify
POST /api/activate
POST /api/token/refresh
GET  /api/subscription
GET  /api/usage
GET  /api/devices
POST /api/devices/:id/revoke
POST /api/chat/completions
```

`GET /api/catalog` 返回首版正式套餐、模型、开关和限制：

```json
{
  "pro_enabled": true,
  "min_app_version": "2.1.0",
  "plans": [
    {
      "id": "pro_monthly",
      "name": "Pro 月度版",
      "price_cny": "9.90",
      "quota_points_per_month": 500,
      "duration_days": 31
    },
    {
      "id": "pro_yearly",
      "name": "Pro 年度版",
      "price_cny": "99.00",
      "quota_points_per_month": 500,
      "duration_days": 366
    },
    {
      "id": "pro_trial",
      "name": "Pro 7 天试用",
      "price_cny": "0.00",
      "quota_points": 100,
      "duration_days": 7
    }
  ],
  "request_limits": {
    "max_input_chars": 20000
  },
  "point_policy": {
    "tokens_per_point": 1000,
    "rounding": "ceil",
    "charge_on_success_only": true
  },
  "models": [
    {
      "id": "deepseek-standard",
      "name": "DeepSeek - 标准模型",
      "provider": "deepseek",
      "required_plan": "pro",
      "point_multiplier": 1,
      "status": "available"
    },
    {
      "id": "qwen-standard",
      "name": "通义千问 - 标准模型",
      "provider": "dashscope",
      "required_plan": "pro",
      "point_multiplier": 1,
      "status": "available"
    },
    {
      "id": "doubao-standard",
      "name": "豆包 - 标准模型",
      "provider": "volcengine",
      "required_plan": "pro",
      "point_multiplier": 1,
      "status": "available"
    },
    {
      "id": "kimi-standard",
      "name": "Kimi - 标准模型",
      "provider": "moonshot",
      "required_plan": "pro",
      "point_multiplier": 1,
      "status": "available"
    }
  ]
}
```

`POST /api/create-payment` 请求：

```json
{
  "plan_id": "pro_monthly",
  "binding_session_id": "binding-session-id",
  "installation_id": "uuid",
  "app_version": "2.0.5",
  "client_nonce": "random-string"
}
```

`POST /api/chat/completions` 采用 OpenAI 兼容请求体，但服务端只允许 `model` 取值来自 `catalog`：

```json
{
  "model": "deepseek-standard",
  "temperature": 0.2,
  "messages": [
    {"role": "system", "content": "prompt"},
    {"role": "user", "content": "<text>...</text>"}
  ]
}
```

### 7.4 数据库表

第一版 D1 表结构：

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE TABLE user_identities (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  identity_type TEXT NOT NULL,
  identity_value_hash TEXT UNIQUE NOT NULL,
  verified_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE verification_codes (
  id TEXT PRIMARY KEY,
  identity_type TEXT NOT NULL,
  identity_value_hash TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  purpose TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  consumed_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE devices (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  installation_id TEXT NOT NULL,
  label TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  revoked_at TEXT
);

CREATE TABLE binding_sessions (
  id TEXT PRIMARY KEY,
  installation_id TEXT NOT NULL,
  user_id TEXT,
  status TEXT NOT NULL,
  app_version TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  out_trade_no TEXT UNIQUE NOT NULL,
  user_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  amount_cny TEXT NOT NULL,
  status TEXT NOT NULL,
  payment_provider TEXT NOT NULL,
  provider_trade_no TEXT,
  created_at TEXT NOT NULL,
  paid_at TEXT,
  raw_notify_hash TEXT
);

CREATE TABLE subscriptions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  status TEXT NOT NULL,
  starts_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  quota_points INTEGER NOT NULL,
  remaining_points INTEGER NOT NULL,
  quota_period TEXT NOT NULL,
  renews_manually INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE usage_ledger (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  device_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  points_used INTEGER NOT NULL,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE payment_events (
  id TEXT PRIMARY KEY,
  out_trade_no TEXT NOT NULL,
  event_type TEXT NOT NULL,
  verified INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  action TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE trial_claims (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  identity_hash TEXT NOT NULL,
  device_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE admin_users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  totp_secret_encrypted TEXT NOT NULL,
  created_at TEXT NOT NULL,
  last_login_at TEXT
);
```

账号必须通过邮箱验证码或手机号验证码创建和登录。同一 `users.id` 可以绑定一个邮箱和一个手机号；设备绑定到账号，订阅权益跟账号走。

## 8. 支付与授权

### 8.1 支付自动化

支付流程必须服务端闭环：

1. 用户通过网页登录账号。
2. 客户端创建绑定会话并打开购买页。
3. 服务端生成 `out_trade_no`。
4. 服务端向 ZPAY 创建订单。
5. 网页展示二维码或支付链接。
6. 支付平台通知服务端。
7. 服务端验签、验订单、验金额、验套餐。
8. 服务端用事务或幂等逻辑更新订单和订阅。
9. 客户端轮询绑定会话和订单状态并自动激活。

客户端不能直接相信支付平台页面，也不能通过客户端参数决定“已支付”。

### 8.2 授权策略

授权组合：

- 服务端签发 30 分钟 `access_token`，用于 Gateway 请求。
- 服务端签发 90 天可轮换 `refresh_token`，用于续期。
- 客户端内置公钥，只用于验证服务端返回的订阅摘要是否未被本地篡改。
- 托管模型请求始终以服务端实时校验为准。

离线授权摘要只用于本地展示最近一次订阅状态，不能用于托管模型调用，也不能用于扣点。

## 9. 安全设计

### 9.1 密钥安全

- 支付平台商户密钥放入服务端 secret。
- 模型供应商 API Key 放入服务端 secret。
- JWT 或 license 私钥放入服务端 secret。
- 客户端只内置公钥和 Gateway 公共地址。
- Git 仓库禁止提交 `.env`、Wrangler secret 值、供应商 key、支付 key。

### 9.2 支付安全

- 支付回调必须验签。
- 回调金额必须等于订单金额。
- 回调订单号必须存在且未被篡改。
- 订单状态更新必须幂等。
- 已支付订单重复回调不能重复发放额度。
- 客户端轮询结果只读服务端订单状态，不能自报支付成功。

### 9.3 Gateway 安全

- 每次请求检查 token、订阅状态、设备状态和额度。
- 单次输入最多 20,000 字符，避免超大剪贴板文本打穿成本。
- 限制并发和请求频率。
- 模型 ID 必须来自服务端白名单。
- 禁止客户端传入任意供应商 base URL。
- 供应商错误应规范化，避免把上游密钥、内部 URL 或完整异常栈返回给客户端。
- 用量记录采用“请求前额度预检查，成功后按真实 tokens 扣点”的策略；失败请求不扣点。

### 9.4 隐私安全

- 默认不保存原文和模型输出。
- 错误日志只记录错误码、模型、token 数、请求 ID。
- 第一版不提供服务端正文诊断模式；管理后台绝不展示请求正文或模型输出。
- 设置页必须提示：使用 NeatCopy Pro 时文本会经由 NeatCopy 服务端转发给模型供应商。

### 9.5 滥用防护

第一版至少实现：

- 每设备每分钟请求限制。
- 每用户每日请求限制。
- 每次最大字符数限制。
- 同一订阅最多绑定 2 台设备。
- 异常失败率或异常 token 消耗先触发限速，再进入人工审核。
- 管理后台可手动吊销设备或订阅。

## 10. 错误处理

客户端显示应面向用户：

- 未登录或 token 过期：请重新激活 NeatCopy Pro。
- 订阅过期：Pro 已过期，可续费或切换自带 API。
- 额度不足：本月额度已用完，可等待下月刷新。
- 模型维护：当前模型暂不可用，请切换其他模型。
- 网络失败：无法连接 NeatCopy Gateway，请检查网络。
- 支付处理中：付款确认中，请稍后。

服务端应区分：

- `401`：token 缺失或无效。
- `402`：订阅过期或额度不足。
- `403`：设备被吊销或无模型权限。
- `408`：上游超时。
- `429`：速率限制。
- `502`：模型供应商错误。

## 11. 测试计划

### 11.1 客户端测试

- 配置迁移：旧配置没有 `provider_mode` 时默认 `byok`。
- BYOK 路径：现有 LLM 测试继续通过。
- Managed 路径：客户端正确请求 Gateway，不读取本地 `api_key`。
- 设置页：切换模型来源时正确显示/隐藏配置区域。
- Token 过期：显示重新激活提示，不覆盖剪贴板。
- Gateway 错误：剪贴板保持原文，预览失败信号正常。
- 超过 20,000 字符：客户端提示分段处理，不发送请求。
- 设备超限：客户端提示到用户自助页解绑设备。

### 11.2 服务端测试

- 创建订单成功。
- 支付回调验签失败被拒绝。
- 金额不匹配被拒绝。
- 重复回调不重复发放额度。
- 订阅过期后 `/api/chat/completions` 返回 `402`。
- 额度不足后返回 `402`。
- 非白名单模型返回 `403`。
- 单次输入超限返回 `413` 或业务错误码。
- 上游模型超时被规范化为用户可读错误。
- FakePaymentProvider 只能在 staging 启用，生产环境启动时若启用则失败。
- FakeModelProvider 覆盖 staging 主流程，真实供应商做冒烟测试。
- 邮箱和手机号验证码满足频率限制。
- 超过 2 台设备时阻止新设备 Pro 调用。

### 11.3 集成测试

- 未付费用户可以继续使用本地规则和 BYOK。
- 用户完成支付后无需手动联系开发者即可激活。
- Pro 模型调用成功后写入剪贴板和预览。
- Pro 模型失败时不破坏剪贴板。
- 过期后可以续费并恢复使用。

## 12. 分阶段落地

### Phase 0：准备与决策

- 确定 ZPAY 商户配置。
- 确定 DeepSeek、Qwen/通义千问、豆包、Kimi/Moonshot 的首发友好模型名和真实模型映射。
- 确定月付 9.9 元、年付 99 元、每月 500 点、试用 7 天 100 点。
- 确定 Gateway 域名。
- 确定邮箱和短信验证码服务商。

### Phase 1：客户端架构预留

- 增加 `provider_mode` 配置。
- 抽象 `ByokProvider` 和 `ManagedProvider`。
- 保证默认仍为 BYOK，不改变老用户行为。
- 增加托管模型错误分类。
- 增加 20,000 字符上限和点数状态展示。

### Phase 2：服务端 MVP

- 创建 Worker 项目和 D1 schema。
- 实现验证码登录、绑定会话、catalog、create-payment、check-order、payment-notify。
- 实现 token 签发和 subscription 查询。
- 实现 DeepSeek、Qwen/通义千问、豆包、Kimi/Moonshot 供应商适配器。
- 实现 FakePaymentProvider 和 FakeModelProvider，并限制只在 staging 使用。

### Phase 3：客户端 Pro UI

- 设置页加入模型来源切换。
- 加入网页登录/购买/设备管理入口、绑定会话轮询、订阅状态展示。
- 加入模型选择和额度展示。
- 加入隐私说明。

### Phase 4：安全与风控

- 支付回调验签和金额校验测试补齐。
- 加入请求限流、输入长度限制、设备限制。
- 加入 usage ledger、异常用量限速和人工审核状态。
- 简单管理后台支持补单、退款标记、吊销、查询。
- 极简用户自助页支持订阅查看、续费和设备解绑。

### Phase 5：发布与观测

- 灰度发布给少量用户。
- 观察支付成功率、模型失败率、成本、平均 token 使用量。
- 根据真实成本调整套餐和配额。
- 完成购买页、隐私说明、使用说明、退款规则和服务条款。

## 13. 明确不做

第一版不做：

- 团队账号。
- 多设备无限绑定。
- 复杂 RBAC 管理后台。
- 多套餐复杂权益矩阵。
- 无限量会员。
- 加购点数包。
- 自动续费或代扣。
- 自动退款。
- 自定义 URL Scheme 回调客户端。
- 流式输出。
- 客户端内置供应商 API Key。
- 保存用户剪贴板原文用于调试。
- 管理后台查看用户请求正文或模型输出。
- 让离线激活码直接解锁托管模型调用。

## 14. 验收标准

设计完成后的产品验收标准：

- 老用户不购买也能继续使用本地规则和自带 API。
- 新用户购买 Pro 后不需要手动配置模型供应商。
- 支付后自动激活，不需要联系开发者发码。
- 任意客户端请求都无法获得供应商 API Key。
- 支付回调无法通过伪造客户端状态绕过。
- 超额、过期、滥用时服务端能阻止继续消耗模型成本。
- 默认日志不包含剪贴板原文和模型输出。
- 后台不能查看请求正文或模型输出。
- 单个 Pro 订阅最多 2 台设备，超限时必须引导解绑。
- staging 可以用 FakePaymentProvider 和 FakeModelProvider 跑通完整流程，生产环境不能启用 Fake 支付。
- 客户端错误提示清楚，不会因为 Pro 请求失败覆盖用户剪贴板。

## 15. 参考资料

- 本地文章：`docs/Charging features/作为个人开发者，我是如何开发收费功能的？ (2026_6_10 13：10：22).html`
- Cloudflare Workers Pricing：https://developers.cloudflare.com/workers/platform/pricing/
- Cloudflare Workers Secrets：https://developers.cloudflare.com/workers/configuration/secrets/
- Cloudflare D1 Limits：https://developers.cloudflare.com/d1/platform/limits/
- ZPAY 开发文档：https://7-pay.cn/doc.html
