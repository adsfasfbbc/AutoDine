from configparser import ConfigParser
from pathlib import Path
import sys

from sqlalchemy import MetaData


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.config import build_settings
from autodine_core.infrastructure.database.base import Base


def test_base_metadata_uses_sqlalchemy_2_metadata_with_naming_convention() -> None:
    assert isinstance(Base.metadata, MetaData)
    assert Base.metadata.naming_convention == {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


def test_runtime_and_alembic_default_to_postgresql_urls() -> None:
    settings = build_settings()
    assert settings.database_url.startswith("postgresql+psycopg://")

    parser = ConfigParser()
    parser.read(Path(__file__).resolve().parents[1] / "alembic.ini", encoding="utf-8")

    assert parser["alembic"]["sqlalchemy.url"].startswith("postgresql+psycopg://")


def test_default_store_id_matches_seeded_catalog() -> None:
    import json

    settings = build_settings()
    assert settings.default_store_id == "store-main"

    catalog_path = Path(__file__).resolve().parents[3] / "data" / "seed" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog["store_id"] == settings.default_store_id
