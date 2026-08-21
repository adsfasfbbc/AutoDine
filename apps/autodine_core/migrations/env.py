from __future__ import with_statement

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from autodine_core.infrastructure.database import Base
from autodine_core.modules.alarm import models as _alarm_models  # noqa: F401
from autodine_core.modules.device import models as _device_models  # noqa: F401
from autodine_core.modules.event import models as _event_models  # noqa: F401
from autodine_core.modules.inventory import models as _inventory_models  # noqa: F401
from autodine_core.modules.inventory import reservations as _reservations  # noqa: F401
from autodine_core.modules.menu import models as _menu_models  # noqa: F401
from autodine_core.modules.order import models as _order_models  # noqa: F401
from autodine_core.modules.production import models as _production_models  # noqa: F401
from autodine_core.modules.queue import models as _queue_models  # noqa: F401
from autodine_core.modules.recipe import models as _recipe_models  # noqa: F401


config = context.config
database_url = os.environ.get("AUTODINE_CORE_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
