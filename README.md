# AutoDine

AutoDine v1 monorepo skeleton for core services, edge integrations, shared contracts, deployment assets, and end-to-end test scaffolding.

This repository contains the runnable first Core flow plus stable integration boundaries for parallel tracks.

Quick start: `make install`, `make seed DATABASE_URL=sqlite+pysqlite:///autodine.db`, and `make smoke`. For the full local stack, run `docker compose -f deploy/docker-compose.yml up --build`.

Core owns business state in `apps/autodine_core`. Edge A/B/D (`edge/`), Agent E (`apps/agent_hub`), and Web F (`apps/dine_web`) stay independent and exchange only contracts and fixtures in `contracts/` and `data/mock/`.
