# 接口适配层说明

前端所有数据经 `src/api/` 访问，页面与数据源解耦。适配层按团队契约
（`../../../contracts/openapi/autodine-core-v1.yaml`、`../../../contracts/websocket/topics.yaml`）实现。

## 数据源切换

`src/api/index.ts`：

- 默认 `VITE_USE_MOCK !== 'false'` → `MockApiClient` + `MockRealtimeClient`
- 设置 `VITE_USE_MOCK=false` → `HttpApiClient` + `HttpRealtimeClient`

## REST 映射（HttpApiClient）

| OpenAPI operationId | 方法 | 说明 |
|---|---|---|
| `listMenu` | `listMenu(storeId?)` | 菜单可售量投影 |
| `getMenuItem` | `getMenuItem(productId)` | 商品详情（含 BOM） |
| `createOrder` | `createOrder(input)` | 下单（幂等键 + 库存校验） |
| `getOrder` | `getOrder(orderId)` | 订单详情 |
| `cancelOrder` | `cancelOrder(orderId)` | 取消订单 |
| `start/ready/completeTask` | `startTask/readyTask/completeTask` | 生产任务流转 |
| `listQueueSnapshots` | `listQueueSnapshots(storeId)` | 排队快照 |
| `listAlarms` / `acknowledge` / `resolve` | 同名方法 | 告警 |
| `getAnalyticsSummary` | `getAnalyticsSummary(...)` | 经营 KPI |
| `listInventory` | `listInventory()` | 库存快照 |

统一信封：`request<T>()` 解包 `{code, message, request_id, timestamp, data}`；
`code !== 0` 或非 2xx 抛 `ApiError`。

## WebSocket 映射

- endpoint：`/ws/stores/{store_id}`（默认 `store-main`）
- 主题：`../../../contracts/websocket/topics.yaml` 中 21 个主题
- 当前消费：`menu.availability_changed`（菜单售罄即时更新）、`production.task_started/ready/completed`
  （订单状态推进）、`queue.updated`（排队刷新）

## Mock 语义

`MockApiClient`（`src/api/mock/adapter.ts`）：

- 延迟 120–260ms 模拟网络
- 菜单在售/售罄由 `stock` 驱动（模拟 BOM 可售量联动语义，下单即扣减，售罄自动停售）
- 订单自动流转：`CONFIRMED → PRODUCING(+3s) → READY(+8s) → COMPLETED(+14s)`，广播实时事件
- 生产端可手动 start/ready/complete 覆盖自动流转
- 取消订单释放库存并恢复在售
- 额外内置演示数据：10 条历史订单、9 台设备（含 1 台异常冷藏柜）、3 条质检事件、
  分时客流/营收序列、品类构成、库存流水（下单自动记录消耗）

## Mock 扩展方法（契约 v1 未定义，真实客户端抛出未实现）

| 方法 | 说明 |
|---|---|
| `listOrders` | 订单列表（历史 + 实时合并） |
| `listDevices` | 设备列表 |
| `listQualityEvents` / `handleQualityEvent` | 质检事件与处理（实时事件走 `quality.abnormal` 主题） |
| `getTrafficSummary` / `getCategoryBreakdown` | 客流与品类分析 |
| `listInventoryMovements` | 库存流水 |

`issueDeviceCommand` 按契约实现（`POST /api/v1/devices/{device_id}/commands`）。

## Agent Hub 接入边界

当前 `AgentView.vue` 使用本地菜单规则，不发起模型请求。团队 Agent Hub 的预期接入方向为：

1. 浏览器请求 Agent Hub 的 `POST /api/v1/agents/consumer/chat`；
2. Agent Hub 通过 Core 工具读取菜单、队列、订单等业务真相；
3. Agent Hub 可使用默认 scripted 驱动，或在服务端配置 OpenAI-compatible 模型；
4. 前端只接收对话与结构化商品推荐，不持有模型 API Key。

正式接入前仍需完成：Agent Hub 云端部署、同域代理或 CORS、P001 系列新菜单模型同步，以及
在 `{ agent, reply }` 之外补充可稳定渲染的结构化推荐商品字段。联通验收依次检查 Core `/health`、
Agent Hub `/health`、`/api/v1/agents` 与 consumer chat；任一步失败时保留本地规则作为降级体验。

## 类型对齐

`src/api/types.ts` 字段命名沿用 ADP snake_case：
`product_id / price_cent / calories_kcal / prep_time_sec / status / tags / allergens / bom`，
价格仅由 `price_cent` 换算人民币显示。
