"""Verify the Alembic migration produces a schema matching the ORM models."""

import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.database import Base

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def migrated_db_url():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    url = f"sqlite:///{tmp.name}"

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    try:
        yield url
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def test_migration_creates_all_model_tables(migrated_db_url):
    engine = create_engine(migrated_db_url)
    try:
        actual_tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
        model_tables = set(Base.metadata.tables.keys())
        assert model_tables <= actual_tables
    finally:
        engine.dispose()


def test_migration_column_parity(migrated_db_url):
    engine = create_engine(migrated_db_url)
    try:
        inspector = inspect(engine)
        for table_name, table in Base.metadata.tables.items():
            model_cols = {column.name for column in table.columns}
            db_cols = {column["name"] for column in inspector.get_columns(table_name)}
            assert not (model_cols - db_cols), (
                f"{table_name}: migration missing columns {model_cols - db_cols}"
            )
    finally:
        engine.dispose()


def test_migration_preserves_unique_constraint(migrated_db_url):
    engine = create_engine(migrated_db_url)
    try:
        inspector = inspect(engine)
        uniques = inspector.get_unique_constraints("certificates")
        pairs = {tuple(unique["column_names"]) for unique in uniques}
        assert ("job_id", "row_index") in pairs
    finally:
        engine.dispose()
