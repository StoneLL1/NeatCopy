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

## 3. 推荐方案

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

不推荐第一版做纯离线激活码解锁，因为它只能安全解锁本地功能，不能安全承载托管模型调用。付费用户使用你的模型额度时，服务端实时授权和用量扣减是必要边界。

## 4. 用户流程

### 4.1 免费用户

1. 打开设置页。
2. 选择大模型模式。
3. 模型来源保持“自带 API”。
4. 手动填写 `Base URL`、`API Key`、`Model ID`。
5. 点击测试连接。
6. 使用现有 Prompt 轮盘、预览面板、历史记录能力。

### 4.2 付费用户首次购买

1. 打开设置页的大模型页面。
2. 选择“NeatCopy Pro 托管模型”。
3. 客户端生成或读取本地 `installation_id`。
4. 客户端请求 `POST /api/create-payment`，携带套餐、客户端版本、设备指纹摘要。
5. 服务端创建订单并调用支付平台生成二维码或支付链接。
6. 客户端展示二维码，并轮询 `GET /api/check-order?out_trade_no=...`。
7. 支付平台回调 `POST /api/payment-notify`。
8. 服务端验签、验金额、验订单、幂等写入订阅和额度。
9. 客户端轮询到支付成功，自动拉取订阅状态和短期访问 token。
10. 客户端显示 Pro 已激活、到期时间、剩余额度和可选模型。

### 4.3 付费用户调用模型

1. 用户复制文本并触发清洗。
2. 客户端根据 Prompt 轮盘选择具体任务。
3. 若模型来源是 NeatCopy Pro，客户端请求 `POST /api/chat/completions`。
4. Gateway 校验 token、订阅、设备绑定、模型权限、输入长度、月度额度和速率。
5. Gateway 选择供应商适配器，比如 Qwen、DeepSeek 或豆包。
6. Gateway 调用真实供应商 API。
7. Gateway 记录用量和状态，不记录原文和结果正文。
8. 客户端收到结果，沿用现有写剪贴板、预览、历史记录流程。

### 4.4 续费与过期

1. 客户端启动或打开设置页时请求 `GET /api/subscription`。
2. 若订阅快过期，在 Pro 区域展示续费提示。
3. 若订阅过期，托管模型不可用，但自带 API 和本地规则模式继续可用。
4. 如果网络不可用，客户端可以显示最近一次缓存状态，但不能继续消耗 Pro 网关额度。

## 5. 客户端设计

### 5.1 配置结构

在 `llm` 配置下新增付费相关字段。字段命名建议：

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

### 5.2 设置页

大模型页面新增一个模型来源区域：

- “自带 API”：显示现有 API 配置卡片。
- “NeatCopy Pro”：显示登录/激活状态、购买按钮、模型下拉框、套餐和额度。

Pro 区域最小可用内容：

- 当前状态：未激活、已激活、即将过期、已过期、额度不足。
- 购买或续费按钮。
- 模型选择：由 `GET /api/catalog` 返回。
- 剩余额度：按月度调用次数、token 或点数展示。
- 隐私说明：托管模型请求会经过 NeatCopy 服务端，默认不保存原文和输出。

### 5.3 调用层改造

当前 `src/clip_processor.py` 和 `src/llm_client.py` 都直接拼接 `{base_url}/chat/completions`。实施时应抽象一个 LLM Provider 边界：

- `ByokProvider`：现有逻辑，读取 `base_url`、`api_key`、`model_id`。
- `ManagedProvider`：读取 `gateway_url`、`access_token`、`selected_model`，请求 NeatCopy Gateway。
- `LLMClient`：只关心输入文本、Prompt、配置和返回结果，不关心具体供应商。

这样可以减少对现有剪贴板、预览、历史记录、轮盘逻辑的影响。

### 5.4 本地授权缓存

客户端可以缓存订阅状态用于展示，但不能把缓存当作可无限使用的授权依据。托管模型每次请求都必须由 Gateway 实时校验额度。

本地可缓存：

- `installation_id`
- 短期 `access_token`
- 可轮换的 `refresh_token`
- 最近一次订阅摘要
- 最近一次模型目录

本地不保存：

- 支付平台密钥
- 模型供应商 API Key
- license 私钥
- 后台管理 token

## 6. 服务端设计

### 6.1 部署形态

第一版推荐使用 Cloudflare Workers + D1：

- Worker 承载 API、支付回调、模型网关。
- D1 存储订单、订阅、设备、用量和审计日志。
- Secrets 存储支付密钥、模型供应商密钥、JWT/签名密钥、后台管理 token。

如果后续模型请求量增长，模型代理部分可以迁移到独立后端，比如 Fly.io、Render、国内云函数或轻量服务器。支付、订阅和用量模型不应和具体云厂商强绑定。

### 6.2 服务端模块

服务端拆分为以下边界：

- `payment`：创建订单、支付平台签名、支付回调验签、订单状态同步。
- `subscription`：套餐、到期时间、额度周期、续费合并。
- `license`：签发短期 token 和可验证的授权摘要。
- `model_gateway`：OpenAI 兼容入口、供应商路由、错误规范化。
- `providers`：Qwen、DeepSeek、豆包等模型供应商适配器。
- `usage`：用量预估、扣减、结算、异常回滚。
- `risk`：速率限制、设备限制、异常检测、封禁。
- `admin`：手动补单、退款标记、用户状态查询，第一版可只做受保护 API，不做完整后台 UI。

### 6.3 API 契约

最小 API 集合：

```text
GET  /api/catalog
POST /api/create-payment
GET  /api/check-order
POST /api/payment-notify
POST /api/activate
POST /api/token/refresh
GET  /api/subscription
GET  /api/usage
POST /api/chat/completions
```

`GET /api/catalog` 返回：

```json
{
  "plans": [
    {
      "id": "pro_monthly",
      "name": "Pro 月度版",
      "price_cny": "19.90",
      "quota_points": 1000,
      "duration_days": 31
    }
  ],
  "models": [
    {
      "id": "deepseek-chat",
      "name": "DeepSeek Chat",
      "provider": "deepseek",
      "required_plan": "pro",
      "point_multiplier": 1
    },
    {
      "id": "qwen-plus",
      "name": "Qwen Plus",
      "provider": "dashscope",
      "required_plan": "pro",
      "point_multiplier": 1
    },
    {
      "id": "doubao-seed",
      "name": "豆包 Seed",
      "provider": "volcengine",
      "required_plan": "pro",
      "point_multiplier": 1
    }
  ]
}
```

`POST /api/create-payment` 请求：

```json
{
  "plan_id": "pro_monthly",
  "installation_id": "uuid",
  "app_version": "2.0.5",
  "client_nonce": "random-string"
}
```

`POST /api/chat/completions` 采用 OpenAI 兼容请求体，但服务端只允许 `model` 取值来自 `catalog`：

```json
{
  "model": "deepseek-chat",
  "temperature": 0.2,
  "messages": [
    {"role": "system", "content": "prompt"},
    {"role": "user", "content": "<text>...</text>"}
  ]
}
```

### 6.4 数据库表

建议第一版 D1 表结构：

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
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
  quota_period TEXT NOT NULL,
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
```

第一版可以把 `user_id` 设计为服务端生成的匿名账号，不要求手机号或邮箱登录。购买后客户端把订阅绑定到 `installation_id` 和服务端匿名 `user_id`。如果未来要支持多设备同步，再引入邮箱登录或 OAuth。

## 7. 支付与授权

### 7.1 支付自动化

支付流程必须服务端闭环：

1. 服务端生成 `out_trade_no`。
2. 服务端向支付平台创建订单。
3. 客户端展示二维码或支付链接。
4. 支付平台通知服务端。
5. 服务端验签、验订单、验金额、验套餐。
6. 服务端用事务或幂等逻辑更新订单和订阅。
7. 客户端轮询订单状态并自动激活。

客户端不能直接相信支付平台页面，也不能通过客户端参数决定“已支付”。

### 7.2 授权策略

推荐组合：

- 服务端签发短期 `access_token`，用于 Gateway 请求。
- 服务端签发可轮换 `refresh_token`，用于续期。
- 客户端内置公钥，只用于验证服务端返回的订阅摘要是否未被本地篡改。
- 托管模型请求始终以服务端实时校验为准。

如果要保留离线授权，离线授权只用于本地功能展示或未来纯本地 Pro 功能，不能用于托管模型调用。

## 8. 安全设计

### 8.1 密钥安全

- 支付平台商户密钥放入服务端 secret。
- 模型供应商 API Key 放入服务端 secret。
- JWT 或 license 私钥放入服务端 secret。
- 客户端只内置公钥和 Gateway 公共地址。
- Git 仓库禁止提交 `.env`、Wrangler secret 值、供应商 key、支付 key。

### 8.2 支付安全

- 支付回调必须验签。
- 回调金额必须等于订单金额。
- 回调订单号必须存在且未被篡改。
- 订单状态更新必须幂等。
- 已支付订单重复回调不能重复发放额度。
- 客户端轮询结果只读服务端订单状态，不能自报支付成功。

### 8.3 Gateway 安全

- 每次请求检查 token、订阅状态、设备状态和额度。
- 限制单次输入长度，避免超大剪贴板文本打穿成本。
- 限制并发和请求频率。
- 模型 ID 必须来自服务端白名单。
- 禁止客户端传入任意供应商 base URL。
- 供应商错误应规范化，避免把上游密钥、内部 URL 或完整异常栈返回给客户端。
- 用量记录采用“先预扣或限额判断，后按真实 tokens 结算”的策略。

### 8.4 隐私安全

- 默认不保存原文和模型输出。
- 错误日志只记录错误码、模型、token 数、请求 ID。
- 如果后续需要调试原文采样，必须单独做用户显式开关，默认关闭。
- 设置页必须提示：使用 NeatCopy Pro 时文本会经由 NeatCopy 服务端转发给模型供应商。

### 8.5 滥用防护

第一版至少实现：

- 每设备每分钟请求限制。
- 每用户每日请求限制。
- 每次最大字符数限制。
- 同一订阅可绑定设备数限制，建议第一版 1 到 2 台。
- 异常失败率或异常 token 消耗触发临时冻结。
- 后台管理 API 可手动吊销设备或订阅。

## 9. 错误处理

客户端显示应面向用户：

- 未登录或 token 过期：请重新激活 NeatCopy Pro。
- 订阅过期：Pro 已过期，可续费或切换自带 API。
- 额度不足：本月额度已用完，可等待刷新或购买加量包。
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

## 10. 测试计划

### 10.1 客户端测试

- 配置迁移：旧配置没有 `provider_mode` 时默认 `byok`。
- BYOK 路径：现有 LLM 测试继续通过。
- Managed 路径：客户端正确请求 Gateway，不读取本地 `api_key`。
- 设置页：切换模型来源时正确显示/隐藏配置区域。
- Token 过期：显示重新激活提示，不覆盖剪贴板。
- Gateway 错误：剪贴板保持原文，预览失败信号正常。

### 10.2 服务端测试

- 创建订单成功。
- 支付回调验签失败被拒绝。
- 金额不匹配被拒绝。
- 重复回调不重复发放额度。
- 订阅过期后 `/api/chat/completions` 返回 `402`。
- 额度不足后返回 `402`。
- 非白名单模型返回 `403`。
- 单次输入超限返回 `413` 或业务错误码。
- 上游模型超时被规范化为用户可读错误。

### 10.3 集成测试

- 未付费用户可以继续使用本地规则和 BYOK。
- 用户完成支付后无需手动联系开发者即可激活。
- Pro 模型调用成功后写入剪贴板和预览。
- Pro 模型失败时不破坏剪贴板。
- 过期后可以续费并恢复使用。

## 11. 分阶段落地

### Phase 0：准备与决策

- 确定支付平台。
- 确定第一批模型供应商和模型。
- 确定套餐价格、配额、设备数。
- 确定 Gateway 域名。

### Phase 1：客户端架构预留

- 增加 `provider_mode` 配置。
- 抽象 `ByokProvider` 和 `ManagedProvider`。
- 保证默认仍为 BYOK，不改变老用户行为。
- 增加托管模型错误分类。

### Phase 2：服务端 MVP

- 创建 Worker 项目和 D1 schema。
- 实现 catalog、create-payment、check-order、payment-notify。
- 实现 token 签发和 subscription 查询。
- 实现一个模型供应商适配器，建议先接 DeepSeek 或 Qwen。

### Phase 3：客户端 Pro UI

- 设置页加入模型来源切换。
- 加入购买二维码、支付状态轮询、订阅状态展示。
- 加入模型选择和额度展示。
- 加入隐私说明。

### Phase 4：安全与风控

- 支付回调验签和金额校验测试补齐。
- 加入请求限流、输入长度限制、设备限制。
- 加入 usage ledger 和异常用量冻结。
- 后台管理 API 支持补单、吊销、查询。

### Phase 5：发布与观测

- 灰度发布给少量用户。
- 观察支付成功率、模型失败率、成本、平均 token 使用量。
- 根据真实成本调整套餐和配额。
- 完成官网、配置教程、隐私说明和退款说明。

## 12. 明确不做

第一版不做：

- 团队账号。
- 多设备无限绑定。
- 完整 Web 管理后台。
- 多套餐复杂权益矩阵。
- 无限量会员。
- 客户端内置供应商 API Key。
- 保存用户剪贴板原文用于调试。
- 让离线激活码直接解锁托管模型调用。

## 13. 验收标准

设计完成后的产品验收标准：

- 老用户不购买也能继续使用本地规则和自带 API。
- 新用户购买 Pro 后不需要手动配置模型供应商。
- 支付后自动激活，不需要联系开发者发码。
- 任意客户端请求都无法获得供应商 API Key。
- 支付回调无法通过伪造客户端状态绕过。
- 超额、过期、滥用时服务端能阻止继续消耗模型成本。
- 默认日志不包含剪贴板原文和模型输出。
- 客户端错误提示清楚，不会因为 Pro 请求失败覆盖用户剪贴板。

## 14. 参考资料

- 本地文章：`docs/Charging features/作为个人开发者，我是如何开发收费功能的？ (2026_6_10 13：10：22).html`
- Cloudflare Workers Pricing：https://developers.cloudflare.com/workers/platform/pricing/
- Cloudflare Workers Secrets：https://developers.cloudflare.com/workers/configuration/secrets/
- Cloudflare D1 Limits：https://developers.cloudflare.com/d1/platform/limits/
- ZPAY 开发文档：https://7-pay.cn/doc.html
