# AutoDine Core migrations

PostgreSQL schema creation is owned by Alembic, not application startup. From the repository root run:

```sh
alembic -c apps/autodine_core/alembic.ini upgrade head
python scripts/seed_data.py --database-url "$AUTODINE_CORE_DATABASE_URL"
```

`Base.metadata.create_all` remains only in isolated SQLite test/bootstrap paths. The Compose Core service applies `upgrade head` before loading the deterministic seed catalog.
