# AutoDine v1 项目设计说明

## 目标

在 14 天内建立可演示的云边协同无人甜品店系统骨架，并完成 C 负责的 AutoDineCore 第一版：库存变化、Recipe BOM、菜单可售量、订单库存预留、生产任务、ADP 事件接收/发布和三端可调用的 REST 接口。

## 约束

- AutoDineCore 是唯一业务事实来源；其他模块不能直接访问其数据库或内部代码。
- 统一使用 ADP v1.0；JSON 使用 snake_case、UTF-8、ISO 8601 时间。
- REST 用于业务 API，MQTT 用于 Edge/IoT 事件，WebSocket 用于前端实时状态。
- PostgreSQL 保存业务真值；Redis 只用于缓存、Pub/Sub 和短期在线状态。
- 所有外部事件必须通过 `event_id` 幂等；订单链路尽量贯穿同一 `trace_id`。
- TRACKED 原料使用 `available = physical - defective - reserved`；UNLIMITED 原料不参与可售量计算。

## 架构

项目采用 Monorepo。`apps/autodine_core` 是模块化单体，按 inventory、recipe、menu、order、production、event、queue、device、alarm、analytics 划分领域模块。`edge/` 为 A、B、D 的预留位置，`apps/agent_hub` 和 `apps/dine_web` 为 E、F 的预留位置。所有跨模块契约集中在 `contracts/`，由 C 维护并生成客户端类型。

第一版优先保证核心业务闭环，边缘、Agent 和 Web 先提供明确的目录、协议文件、Mock 事件和健康检查入口，后续成员可以独立开发。

## 核心业务流程

1. Edge 发布 ADP 事件。
2. Core 校验 Envelope，写入事件接收表并按 `event_id` 去重。
3. Core 更新库存或其他领域状态。
4. 只重算受影响商品的 BOM 可售量。
5. 状态变化写入业务事件 Outbox，再发布到 MQTT/WebSocket。
6. 创建订单时在同一事务内重新校验菜单、锁定库存、创建预留、订单和 ProductionTask。
7. 生产完成按实际消耗核销预留并记录库存流水。

## v1 数据边界

基础实体包括 Store、Ingredient、Inventory、Product、Recipe、RecipeItem、Order、OrderItem、ProductionTask、Event、Alarm、Device；实现中补充 InventoryMovement、InventoryReservation、EventInbox、EventOutbox、QueueSnapshot 和 OrderStatusHistory，以支持审计、幂等和并发安全。

## 需要在接口评审时冻结的决策

- Edge 原始事件命名采用 `vision.storage.*`、`vision.front.*`；Core 业务事件采用 `inventory.*`、`queue.*` 等独立命名空间。
- 温控下行命令统一为 `device.command`，结果为 `device.command_result`。
- 质量异常若只是分类，不减少 physical；实际移出异常原料时才更新 physical，避免 defective 被重复扣减。
- Day 2 发布接口候选版，Day 4 冻结 ADP/OpenAPI v1.0；之后只做兼容扩展。

## 验收标准

- 仅使用 Mock Event 可以完成：库存变化 → BOM 重算 → 菜单停售/恢复 → 下单 → 库存预留 → ProductionTask。
- 重复事件不会重复扣库存；库存不足不能创建订单。
- REST 响应统一包含 `code`、`message`、`request_id`、`timestamp`、`data`。
- Docker Compose 可以启动 Core、PostgreSQL、Redis、MQTT Broker；健康检查和 Seed 命令可重复执行。
- 目录中保留 A/B/D/E/F 独立开发位置，并有契约和 Mock 示例。
