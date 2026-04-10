"""Fixtures for persistence integration tests."""

import asyncio
import shutil
import sys
import uuid
import warnings
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from psycopg import sql
from pydantic import SecretStr

from synthorg.persistence.config import PostgresConfig, SQLiteConfig
from synthorg.persistence.postgres.backend import PostgresPersistenceBackend
from synthorg.persistence.sqlite.backend import SQLitePersistenceBackend

if TYPE_CHECKING:
    from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def event_loop_policy() -> Any:
    """Use SelectorEventLoop on Windows so psycopg async mode works.

    Scoped to the integration directory so other test suites keep
    their default ProactorEventLoop.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        if sys.platform == "win32":
            return asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined,unused-ignore]
        return asyncio.DefaultEventLoopPolicy()  # type: ignore[attr-defined,unused-ignore,unreachable]


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Return a temporary on-disk database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
async def on_disk_backend(db_path: str) -> AsyncGenerator[SQLitePersistenceBackend]:
    """Connected + migrated on-disk SQLite backend."""
    backend = SQLitePersistenceBackend(SQLiteConfig(path=db_path))
    await backend.connect()
    await backend.migrate()
    yield backend
    await backend.disconnect()


def _docker_available() -> bool:
    """Return ``True`` if the Docker CLI is reachable."""
    return shutil.which("docker") is not None


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Start one shared Postgres 18 container per pytest session."""
    if not _docker_available():
        pytest.skip("Docker is required for postgres integration tests")

    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:18-alpine")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture
async def postgres_backend(
    postgres_container: PostgresContainer,
) -> AsyncIterator[PostgresPersistenceBackend]:
    """Yield a connected, migrated PostgresPersistenceBackend.

    Creates a unique database on the shared container so tests stay
    isolated, migrates it via Atlas, hands the backend to the test,
    then drops the database on teardown.
    """
    db_name = f"test_{uuid.uuid4().hex}"
    admin_conninfo = psycopg.conninfo.make_conninfo(
        host=postgres_container.get_container_host_ip(),
        port=int(postgres_container.get_exposed_port(5432)),
        user=postgres_container.username,
        password=postgres_container.password,
        dbname=postgres_container.dbname,
    )
    async with await psycopg.AsyncConnection.connect(
        admin_conninfo, autocommit=True
    ) as admin:
        await admin.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
        )

    config = PostgresConfig(
        host=postgres_container.get_container_host_ip(),
        port=int(postgres_container.get_exposed_port(5432)),
        database=db_name,
        username=postgres_container.username,
        password=SecretStr(postgres_container.password),
        ssl_mode="disable",
        pool_min_size=1,
        pool_max_size=4,
        pool_timeout_seconds=10.0,
        connect_timeout_seconds=5.0,
    )
    backend = PostgresPersistenceBackend(config)
    await backend.connect()
    try:
        await backend.migrate()
        yield backend
    finally:
        await backend.disconnect()
        async with await psycopg.AsyncConnection.connect(
            admin_conninfo, autocommit=True
        ) as admin:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid != pg_backend_pid()",
                (db_name,),
            )
            await admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name))
            )
