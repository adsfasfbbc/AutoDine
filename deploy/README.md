# Local deployment

Start the local stack from the repository root:

```sh
docker compose -f deploy/docker-compose.yml up --build
```

It runs Core, PostgreSQL, Redis, and Mosquitto. PostgreSQL, Redis, and Mosquitto data are persisted in named volumes. Core waits for PostgreSQL, applies the Alembic schema, then idempotently loads the demo catalog. The non-secret local defaults are intentionally embedded for a clean checkout; override them with a Compose environment file before any shared deployment.

Ownership boundary: `apps/autodine_core` owns this service and schema. The `edge/` A/B/D directories, `apps/agent_hub`, and `apps/dine_web` remain independently owned integration clients; they communicate through `contracts/` and `data/mock/`, not by importing Core internals.
