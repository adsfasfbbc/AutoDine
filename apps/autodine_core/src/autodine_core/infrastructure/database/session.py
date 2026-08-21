from __future__ import annotations

from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def build_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        engine_kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in database_url:
            engine_kwargs["poolclass"] = StaticPool
        return create_engine(database_url, future=True, **engine_kwargs)

    return create_engine(database_url, future=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
