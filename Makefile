.PHONY: install test migrate seed run mock-replay smoke

PYTHON ?= python
DATABASE_URL ?= sqlite+pysqlite:///autodine.db
MOCK ?= data/mock/front_queue_update.json
CORE_URL ?= http://localhost:8000

install:
	$(PYTHON) -m pip install -e .[test]

test:
	$(PYTHON) -m pytest -q

migrate:
	alembic -c apps/autodine_core/alembic.ini upgrade head

seed:
	$(PYTHON) scripts/seed_data.py --database-url "$(DATABASE_URL)"

run:
	$(PYTHON) -m uvicorn autodine_core.main:create_app --factory --host 0.0.0.0 --port 8000

mock-replay:
	$(PYTHON) scripts/replay_event.py "$(MOCK)" --base-url "$(CORE_URL)"

smoke:
	$(PYTHON) scripts/smoke_test.py
