# scripts

- `seed_data.py` loads the deterministic 20-product/25-ingredient catalog and is safe to rerun.
- `replay_event.py` replays one ADP JSON fixture or a named fixture mapping to a running Core.
- `smoke_test.py` runs the local E2E proof for inventory, menu, order, reservation, and production-task creation.

The same commands are exposed through the root `Makefile` (`seed`, `mock-replay`, and `smoke`).
