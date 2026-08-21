# Task 4 Report: ADP Event Ingestion, Idempotency, and Outbox

Date: 2026-08-21
Branch: `main`

## Scope Delivered

Implemented the Task 4 event ingestion boundary only:

- ADP v1 envelope validation aligned to `contracts/adp/v1/envelope.schema.json`
- `POST /api/v1/events` with standard response envelope
- `EventInbox` idempotency persistence keyed by `event_id`
- `EventOutbox` persistence for durable business events
- Event routing for `inventory.detected` and `quality.abnormal`
- Duplicate event acceptance without reapplying inventory mutation or creating extra outbox rows
- Transaction-safe product availability recalculation for affected recipe ingredients only
- Injectable event publisher interface with a null implementation for future dispatch
- Focused event tests for envelope validation, duplicate delivery, inventory snapshot upsert, quality abnormal handling, and outbox creation

No MQTT publish worker, order flow, or unrelated module changes were added.

## TDD Evidence

### RED

Command:

```powershell
pytest apps/autodine_core/tests/test_adp_events.py -q
```

Observed output before implementation:

```text
=================================== ERRORS ====================================
________ ERROR collecting apps/autodine_core/tests/test_adp_events.py _________
E   ModuleNotFoundError: No module named 'autodine_core.modules.event'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.52s
```

This established the missing Task 4 event boundary before any production code existed.

### GREEN

Focused Task 4 suite:

```powershell
pytest apps/autodine_core/tests/test_adp_events.py -q
```

Observed output:

```text
.....                                                                    [100%]
5 passed in 0.61s
```

## Verification

Full repository suite:

```powershell
pytest -q
```

Observed output:

```text
..................                                                       [100%]
18 passed in 0.65s
```

Whitespace check:

```powershell
git diff --check
```

Observed output:

```text
warning: in the working copy of 'apps/autodine_core/src/autodine_core/main.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'apps/autodine_core/src/autodine_core/modules/menu/service.py', LF will be replaced by CRLF the next time Git touches it
```

These were line-ending warnings only; `git diff --check` did not report whitespace errors or fail.

## Environment Notes

- Production PostgreSQL defaults were left unchanged.
- SQLite in-memory injection remains supported for tests.
- The event envelope now uses frozen ADP contract fields `timestamp`, `trace_id`, `severity`, and structured `source.module`.
- The menu recalculation helper was adjusted to participate in the caller transaction and flush pending inventory changes before affected-product recomputation.

## Files Added or Changed

- `apps/autodine_core/src/autodine_core/main.py`
- `apps/autodine_core/src/autodine_core/infrastructure/event_bus/__init__.py`
- `apps/autodine_core/src/autodine_core/infrastructure/event_bus/publisher.py`
- `apps/autodine_core/src/autodine_core/modules/event/__init__.py`
- `apps/autodine_core/src/autodine_core/modules/event/models.py`
- `apps/autodine_core/src/autodine_core/modules/event/routes.py`
- `apps/autodine_core/src/autodine_core/modules/event/schemas.py`
- `apps/autodine_core/src/autodine_core/modules/event/service.py`
- `apps/autodine_core/src/autodine_core/modules/menu/service.py`
- `apps/autodine_core/tests/test_adp_events.py`
- `.superpowers/sdd/2026-08-21-autodine-v1-implementation/task-4-report.md`

## Commit

Planned commit message:

```text
feat(core): add adp event ingestion and outbox
```
