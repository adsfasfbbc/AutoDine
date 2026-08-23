# ADP mock events

The JSON fixtures cover storage detection, quality abnormality, front queue updates, front fire dual-confirmation alarms, device telemetry, and a documented order/production event sequence. `e2e_inventory_menu_order.json` is the executable menu sell-out/recovery fixture used by the E2E smoke test.

Replay a single envelope or an array with `make mock-replay MOCK=data/mock/front_queue_update.json`. Order creation remains a Core API transaction (rather than an inbound event); see `scripts/smoke_test.py` for the full order, reservation, and `ProductionTask` sequence.
