"""Phase 1: alembic upgrade head creates the full schema with all constraints/indexes."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer

EXPECTED_TABLES = {
    "accounts",
    "organizations",
    "users",
    "firewalls",
    "agent_tokens",
    "snapshots",
    "findings",
    "alert_channels",
    "alert_rules",
    "alert_deliveries",
    "subscriptions",
    "audit_logs",
    "firewall_commands",
    "remote_change_logs",
}


@pytest.fixture(scope="module")
def migrated_async_url():
    with PostgresContainer("postgres:16-alpine") as postgres:
        async_url = postgres.get_connection_url().replace("psycopg2", "asyncpg")

        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", async_url)
        command.upgrade(cfg, "head")

        yield async_url


async def test_all_tables_created(migrated_async_url):
    engine = create_async_engine(migrated_async_url)
    async with engine.connect() as conn:
        tables = set(await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names()))
    await engine.dispose()
    assert EXPECTED_TABLES.issubset(tables)


async def test_firewall_command_status_check_constraint_exists(migrated_async_url):
    engine = create_async_engine(migrated_async_url)
    async with engine.connect() as conn:
        result = (
            await conn.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname = 'chk_firewall_command_status'"
                )
            )
        ).fetchone()
    await engine.dispose()
    assert result is not None


async def test_remote_change_logs_firewall_command_id_is_unique(migrated_async_url):
    engine = create_async_engine(migrated_async_url)
    async with engine.connect() as conn:
        unique_constraints = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_unique_constraints("remote_change_logs")
        )
    await engine.dispose()
    assert any("firewall_command_id" in uc["column_names"] for uc in unique_constraints)


async def test_firewall_commands_partial_indexes_exist(migrated_async_url):
    engine = create_async_engine(migrated_async_url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'firewall_commands'")
            )
        ).fetchall()
    await engine.dispose()
    index_names = {row[0] for row in rows}
    assert "idx_firewall_commands_firewall_id_status" in index_names
    assert "idx_firewall_commands_status_expires_at" in index_names


async def test_snapshots_processing_status_partial_index_exists(migrated_async_url):
    engine = create_async_engine(migrated_async_url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'snapshots'")
            )
        ).fetchall()
    await engine.dispose()
    index_names = {row[0] for row in rows}
    assert "idx_snapshots_processing_status" in index_names
