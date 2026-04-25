"""Integration tests for ``SettingsRepository.set_many`` on both backends.

PR #1239 introduced single-key CAS on the settings repo.  This follow-up
adds a transactional ``set_many`` that writes multiple rows under CAS
in one shot, so mutations like ``delete_department`` can pin several
keys at once and avoid TOCTOU races.

The tests are duplicated across SQLite and Postgres rather than
parameterised with ``request.getfixturevalue``, because the latter
clashes with ``pytest-asyncio``'s runner when the underlying fixture
is async.
"""

from datetime import UTC, datetime

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.persistence.postgres.backend import PostgresPersistenceBackend
from synthorg.persistence.settings_protocol import SettingsRepository
from synthorg.persistence.sqlite.backend import SQLitePersistenceBackend


def _iso(minute: int) -> str:
    return datetime(2026, 4, 11, 12, minute, 0, tzinfo=UTC).isoformat()


async def _run_all_success(repo: SettingsRepository) -> None:
    ns = NotBlankStr("company")
    ok = await repo.set_many(
        [
            (ns, NotBlankStr("departments"), "[]", _iso(0)),
            (ns, NotBlankStr("agents"), "[]", _iso(0)),
            (ns, NotBlankStr("company_name"), "Acme", _iso(0)),
        ],
    )
    assert ok is True
    for key in ("departments", "agents", "company_name"):
        row = await repo.get(ns, NotBlankStr(key))
        assert row is not None
        assert row[0] in ("[]", "Acme")


async def _run_cas_conflict_rolls_back(repo: SettingsRepository) -> None:
    ns = NotBlankStr("company")

    await repo.set(
        ns,
        NotBlankStr("departments"),
        "[]",
        _iso(0),
        expected_updated_at="",
    )
    await repo.set(
        ns,
        NotBlankStr("agents"),
        "[]",
        _iso(0),
        expected_updated_at="",
    )
    stale_dept_row = await repo.get(ns, NotBlankStr("departments"))
    live_agents_row = await repo.get(ns, NotBlankStr("agents"))
    assert stale_dept_row is not None
    assert live_agents_row is not None
    stale_dept_version = stale_dept_row[1]
    live_agents_version = live_agents_row[1]
    # Bump departments out from under the upcoming set_many so the
    # CAS check fails when the batch runs.
    await repo.set(
        ns,
        NotBlankStr("departments"),
        '["bumped"]',
        _iso(5),
        expected_updated_at=stale_dept_version,
    )

    ok = await repo.set_many(
        [
            (ns, NotBlankStr("departments"), '["new"]', _iso(10)),
            (ns, NotBlankStr("agents"), '["new-agent"]', _iso(10)),
        ],
        expected_updated_at_map={
            ("company", "departments"): stale_dept_version,
            ("company", "agents"): live_agents_version,
        },
    )
    assert ok is False
    dept_row = await repo.get(ns, NotBlankStr("departments"))
    agents_row = await repo.get(ns, NotBlankStr("agents"))
    assert dept_row is not None
    assert agents_row is not None
    assert dept_row[0] == '["bumped"]'
    assert agents_row[0] == "[]"


async def _run_first_write_sentinel(repo: SettingsRepository) -> None:
    ns = NotBlankStr("company")
    ok = await repo.set_many(
        [(ns, NotBlankStr("departments"), "[]", _iso(0))],
        expected_updated_at_map={("company", "departments"): ""},
    )
    assert ok is True
    row = await repo.get(ns, NotBlankStr("departments"))
    assert row is not None
    assert row[0] == "[]"


async def _run_no_cas_upserts(repo: SettingsRepository) -> None:
    ns = NotBlankStr("company")
    await repo.set(
        ns,
        NotBlankStr("company_name"),
        "Acme",
        _iso(0),
        expected_updated_at="",
    )
    ok = await repo.set_many(
        [(ns, NotBlankStr("company_name"), "Zeta", _iso(10))],
    )
    assert ok is True
    row = await repo.get(ns, NotBlankStr("company_name"))
    assert row is not None
    assert row[0] == "Zeta"


async def _run_empty_noop(repo: SettingsRepository) -> None:
    ok = await repo.set_many([])
    assert ok is True


async def _run_mixed(repo: SettingsRepository) -> None:
    ns = NotBlankStr("company")
    await repo.set(
        ns,
        NotBlankStr("departments"),
        "[]",
        _iso(0),
        expected_updated_at="",
    )
    live_dept_row = await repo.get(ns, NotBlankStr("departments"))
    assert live_dept_row is not None
    live_dept_version = live_dept_row[1]

    ok = await repo.set_many(
        [
            (ns, NotBlankStr("departments"), '["a"]', _iso(10)),
            (ns, NotBlankStr("autonomy_level"), "L3", _iso(10)),
        ],
        expected_updated_at_map={
            ("company", "departments"): live_dept_version,
        },
    )
    assert ok is True
    dept_row = await repo.get(ns, NotBlankStr("departments"))
    auton_row = await repo.get(ns, NotBlankStr("autonomy_level"))
    assert dept_row is not None
    assert dept_row[0] == '["a"]'
    assert auton_row is not None
    assert auton_row[0] == "L3"


@pytest.mark.integration
class TestSetManySqlite:
    async def test_all_success(
        self,
        on_disk_backend: SQLitePersistenceBackend,
    ) -> None:
        await _run_all_success(on_disk_backend.settings)

    async def test_cas_conflict_rolls_back(
        self,
        on_disk_backend: SQLitePersistenceBackend,
    ) -> None:
        await _run_cas_conflict_rolls_back(on_disk_backend.settings)

    async def test_first_write_sentinel(
        self,
        on_disk_backend: SQLitePersistenceBackend,
    ) -> None:
        await _run_first_write_sentinel(on_disk_backend.settings)

    async def test_no_cas_upserts(
        self,
        on_disk_backend: SQLitePersistenceBackend,
    ) -> None:
        await _run_no_cas_upserts(on_disk_backend.settings)

    async def test_empty_noop(
        self,
        on_disk_backend: SQLitePersistenceBackend,
    ) -> None:
        await _run_empty_noop(on_disk_backend.settings)

    async def test_mixed(
        self,
        on_disk_backend: SQLitePersistenceBackend,
    ) -> None:
        await _run_mixed(on_disk_backend.settings)


@pytest.mark.integration
class TestSetManyPostgres:
    async def test_all_success(
        self,
        postgres_backend: PostgresPersistenceBackend,
    ) -> None:
        await _run_all_success(postgres_backend.settings)

    async def test_cas_conflict_rolls_back(
        self,
        postgres_backend: PostgresPersistenceBackend,
    ) -> None:
        await _run_cas_conflict_rolls_back(postgres_backend.settings)

    async def test_first_write_sentinel(
        self,
        postgres_backend: PostgresPersistenceBackend,
    ) -> None:
        await _run_first_write_sentinel(postgres_backend.settings)

    async def test_no_cas_upserts(
        self,
        postgres_backend: PostgresPersistenceBackend,
    ) -> None:
        await _run_no_cas_upserts(postgres_backend.settings)

    async def test_empty_noop(
        self,
        postgres_backend: PostgresPersistenceBackend,
    ) -> None:
        await _run_empty_noop(postgres_backend.settings)

    async def test_mixed(
        self,
        postgres_backend: PostgresPersistenceBackend,
    ) -> None:
        await _run_mixed(postgres_backend.settings)
