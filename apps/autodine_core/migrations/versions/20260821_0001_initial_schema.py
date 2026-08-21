"""create initial autodine schema

Revision ID: 20260821_0001
Revises:
Create Date: 2026-08-21 00:00:00
"""
from alembic import op

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


revision = "20260821_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
