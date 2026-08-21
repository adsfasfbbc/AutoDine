# AutoDine v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立完整 AutoDine Monorepo，并实现可由 Mock 驱动的 AutoDineCore 第一版业务闭环。

**Architecture:** 用一个 FastAPI 模块化单体承载 Core 领域模块；PostgreSQL 保存业务真值，Redis/MQTT/WebSocket 分别承担缓存、边缘事件和实时推送。所有跨模块协议放在 contracts，A/B/D/E/F 只通过契约和 Mock 与 Core 集成。

**Tech Stack:** Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic、PostgreSQL、Redis、Mosquitto、pytest、Docker Compose、Vue 3/Vite 预留。

**Spec:** `docs/superpowers/specs/2026-08-21-autodine-v1-design.md`

## Global Constraints

- AutoDineCore 是唯一业务事实来源；其他模块不能直接访问其数据库或内部代码。
- ADP v1.0 JSON 使用 snake_case、UTF-8、ISO 8601 时间。
- REST 用于业务 API，MQTT 用于 Edge/IoT 事件，WebSocket 用于实时状态。
- PostgreSQL 是业务真值；Redis 不是库存或订单的唯一存储。
- 事件按 `event_id` 幂等，订单链路尽量使用同一 `trace_id`。
- TRACKED：`available = physical - defective - reserved`；UNLIMITED 不参与菜单可售量。

---

### Task 1: Monorepo 骨架与跨模块契约

**Files:**
- Create: `.gitignore`, `README.md`, `pyproject.toml`, `.env.example`, `Makefile`
- Create: `apps/autodine_core/`, `apps/agent_hub/`, `apps/dine_web/`, `edge/smart_storage_vision/`, `edge/front_vision/`, `edge/hardware_hub/`
- Create: `contracts/adp/v1/`, `contracts/openapi/`, `contracts/asyncapi/`, `contracts/websocket/`
- Create: `data/seed/`, `data/mock/`, `deploy/`, `scripts/`, `tests/e2e/`, `docs/`
- Test: `tests/test_repository_layout.py`

**Steps:**

- [ ] Write a failing layout test asserting each required directory and `contracts/adp/v1/envelope.schema.json` exist.
- [ ] Run `pytest tests/test_repository_layout.py -v`; expect failure because the skeleton is absent.
- [ ] Create the complete directory skeleton, placeholder READMEs, ADP JSON Schema, OpenAPI/AsyncAPI stubs, and the shared response/error constants.
- [ ] Run the layout test and a JSON parse check; expect PASS.
- [ ] Commit as `chore: scaffold autodine monorepo and contracts`.

### Task 2: Core application bootstrap and persistence

**Files:**
- Create: `apps/autodine_core/src/autodine_core/main.py`, `config.py`, `dependencies.py`
- Create: `apps/autodine_core/src/autodine_core/infrastructure/database/`
- Create: `apps/autodine_core/migrations/`, `apps/autodine_core/alembic.ini`
- Create: `apps/autodine_core/tests/test_health.py`, `tests/test_db_models.py`

**Steps:**

- [ ] Write failing tests for `GET /health` and creation of the base SQLAlchemy metadata.
- [ ] Run the focused tests and verify they fail because the app and models do not exist.
- [ ] Implement FastAPI bootstrap, settings, SQLAlchemy engine/session factory, health endpoint, and a test SQLite configuration.
- [ ] Run focused tests and the full Core test package; expect PASS.
- [ ] Commit as `feat(core): add application bootstrap and persistence base`.

### Task 3: Inventory, Recipe and Menu domain

**Files:**
- Create: `apps/autodine_core/src/autodine_core/modules/inventory/`
- Create: `apps/autodine_core/src/autodine_core/modules/recipe/`
- Create: `apps/autodine_core/src/autodine_core/modules/menu/`
- Create: `apps/autodine_core/tests/test_inventory_menu_flow.py`

**Steps:**

- [ ] Write failing tests for available quantity, UNLIMITED ingredients, BOM minimum calculation, and automatic SOLD_OUT transition.
- [ ] Run the focused tests and verify expected failures.
- [ ] Implement domain models/services and REST read endpoints; use Decimal quantities and explicit units (`pcs`, `g`, `ml`).
- [ ] Run the focused tests and verify all inventory/menu behaviors pass.
- [ ] Commit as `feat(core): implement inventory recipe and menu availability`.

### Task 4: ADP event ingestion, idempotency and outbox

**Files:**
- Create: `apps/autodine_core/src/autodine_core/modules/event/`
- Create: `apps/autodine_core/src/autodine_core/infrastructure/event_bus/`
- Create: `apps/autodine_core/src/autodine_core/workers/`
- Create: `apps/autodine_core/tests/test_adp_events.py`

**Steps:**

- [ ] Write failing tests for Envelope validation, duplicate `event_id`, `inventory.detected`, `quality.abnormal`, and outbox creation.
- [ ] Run focused tests and verify failures are caused by missing handlers.
- [ ] Implement Pydantic Envelope validation, EventInbox deduplication, domain routing, EventOutbox persistence, and MQTT adapter interface.
- [ ] Run event tests and verify duplicates are ignored without a second inventory mutation.
- [ ] Commit as `feat(core): add adp event ingestion and outbox`.

### Task 5: Order, reservation and production flow

**Files:**
- Create: `apps/autodine_core/src/autodine_core/modules/order/`
- Create: `apps/autodine_core/src/autodine_core/modules/production/`
- Create: `apps/autodine_core/src/autodine_core/modules/inventory/reservations.py`
- Create: `apps/autodine_core/tests/test_order_production_flow.py`

**Steps:**

- [ ] Write failing tests for successful order reservation/task creation, insufficient inventory rejection (`4091`), sold-out rejection (`4092`), cancellation release, and repeated idempotency key.
- [ ] Run focused tests and verify failures.
- [ ] Implement one transactional application service that locks tracked inventory, aggregates BOM, writes reservations/order/task, and emits outbox events.
- [ ] Run order tests and verify state transitions `PENDING → CONFIRMED → PRODUCING → READY → COMPLETED`.
- [ ] Commit as `feat(core): add order reservation and production workflow`.

### Task 6: Queue, device, alarm, analytics and WebSocket read model

**Files:**
- Create: `apps/autodine_core/src/autodine_core/modules/queue/`, `device/`, `alarm/`, `analytics/`
- Create: `apps/autodine_core/src/autodine_core/infrastructure/websocket/`
- Create: `apps/autodine_core/tests/test_realtime_read_models.py`

**Steps:**

- [ ] Write failing tests for queue snapshot ingestion, temperature alarm creation, device status updates, operation summary, and WebSocket event fan-out interface.
- [ ] Run focused tests and verify failures.
- [ ] Implement REST read models, alarm rules, WebSocket connection manager, and Redis Pub/Sub adapter boundary.
- [ ] Run focused tests and verify the Core remains usable when the external AI adapter is unavailable.
- [ ] Commit as `feat(core): add realtime queue device alarm and analytics modules`.

### Task 7: Seed, Mock, Docker Compose and end-to-end demo

**Files:**
- Create: `data/seed/*.json`, `data/mock/*.json`, `scripts/seed_data.py`, `scripts/replay_event.py`, `scripts/smoke_test.py`
- Create: `deploy/docker-compose.yml`, `deploy/mosquitto/mosquitto.conf`, `apps/autodine_core/Dockerfile`
- Create: `tests/e2e/test_core_demo.py`, `docs/api/`, `docs/deployment/`, `docs/integration/`

**Steps:**

- [ ] Write a failing end-to-end test that replays inventory and quality events, confirms menu availability, creates an order, and observes a ProductionTask.
- [ ] Run the E2E test and verify failure due to missing Seed/Mock/deployment wiring.
- [ ] Add at least 20 product records, 25 ingredient records, standard BOMs, the required Mock scenarios, Docker Compose services, and a repeatable demo reset.
- [ ] Run the full test suite, `docker compose config`, and the smoke script; record the exact outputs.
- [ ] Commit as `feat: add seed mock deployment and core demo flow`.

### Task 8: Final verification and GitHub publication

**Files:**
- Modify: `README.md`, `docs/project-management/`, `CHANGELOG.md`

**Steps:**

- [ ] Run the complete verification checklist: layout test, Core tests, E2E tests, JSON Schema parse, OpenAPI parse, `docker compose config`, and `git diff --check`.
- [ ] Inspect `git status`, staged diff and commit history; stage only project files.
- [ ] Configure `origin` to `https://github.com/adsfasfbbc/AutoDine.git`, verify the remote, and push `main` only after local verification succeeds.
- [ ] Verify the remote branch and commit through `git ls-remote`.
- [ ] Commit any final documentation-only updates as `docs: document v1 verification and integration guide`.
