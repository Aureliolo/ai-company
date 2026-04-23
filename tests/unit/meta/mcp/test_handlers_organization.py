"""Unit tests for organization MCP handlers.

Covers 19 tools: company (6), departments (6), teams (5), role
versions (2).
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from synthorg.communication.mcp_errors import CapabilityNotSupportedError
from synthorg.meta.mcp.handlers.organization import ORGANIZATION_HANDLERS
from synthorg.organization.services import (
    DepartmentService,
    TeamService,
)
from tests.unit.meta.mcp.conftest import make_test_actor

pytestmark = pytest.mark.unit


@pytest.fixture
def fake_company() -> AsyncMock:
    service = AsyncMock()
    service.get_company = AsyncMock(return_value={"name": "Acme"})
    service.update_company = AsyncMock(return_value={"name": "Acme2"})
    service.list_departments = AsyncMock(return_value=())
    service.reorder_departments = AsyncMock(return_value=None)
    service.list_versions = AsyncMock(return_value=())
    service.get_version = AsyncMock(return_value=None)
    return service


@pytest.fixture
def fake_role_version() -> AsyncMock:
    service = AsyncMock()
    service.list_versions = AsyncMock(return_value=())
    service.get_version = AsyncMock(return_value=None)
    return service


@pytest.fixture
def real_department() -> DepartmentService:
    return DepartmentService()


@pytest.fixture
def real_team() -> TeamService:
    return TeamService()


@pytest.fixture
def fake_app_state(
    fake_company: AsyncMock,
    real_department: DepartmentService,
    real_team: TeamService,
    fake_role_version: AsyncMock,
) -> SimpleNamespace:
    return SimpleNamespace(
        company_read_service=fake_company,
        department_service=real_department,
        team_service=real_team,
        role_version_service=fake_role_version,
    )


class TestCompany:
    async def test_get(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_company_get"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "ok"

    async def test_update_requires_payload(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_company_update"]
        response = await handler(
            app_state=fake_app_state,
            arguments={},
            actor=make_test_actor(),
        )
        assert json.loads(response)["status"] == "error"

    async def test_update_ok(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_company_update"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"payload": {"name": "Acme2"}},
            actor=make_test_actor(),
        )
        assert json.loads(response)["status"] == "ok"

    async def test_list_departments(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_company_list_departments"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "ok"

    async def test_reorder_requires_list(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_company_reorder_departments"]
        response = await handler(
            app_state=fake_app_state,
            arguments={},
            actor=make_test_actor(),
        )
        assert json.loads(response)["status"] == "error"

    async def test_reorder_ok(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_company_reorder_departments"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"department_ids": ["a", "b"]},
            actor=make_test_actor(),
        )
        assert json.loads(response)["status"] == "ok"

    async def test_versions_list(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_company_versions_list"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "ok"

    async def test_versions_get_not_found(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_company_versions_get"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"version_id": "v1"},
        )
        assert json.loads(response)["domain_code"] == "not_found"

    async def test_get_capability_gap(
        self,
        fake_app_state: SimpleNamespace,
        fake_company: AsyncMock,
    ) -> None:
        fake_company.get_company = AsyncMock(
            side_effect=CapabilityNotSupportedError("company_get", "x"),
        )
        handler = ORGANIZATION_HANDLERS["synthorg_company_get"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["domain_code"] == "not_supported"


class TestDepartments:
    async def test_create_and_get(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_departments_create"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"name": "Eng", "description": "team"},
            actor=make_test_actor(),
        )
        created = json.loads(response)
        assert created["status"] == "ok"
        dept_id = created["data"]["id"]

        handler_get = ORGANIZATION_HANDLERS["synthorg_departments_get"]
        response_get = await handler_get(
            app_state=fake_app_state,
            arguments={"department_id": dept_id},
        )
        assert json.loads(response_get)["status"] == "ok"

    async def test_list(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_departments_list"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "ok"

    async def test_delete_requires_guardrails(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_departments_delete"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"department_id": str(uuid4())},
            actor=make_test_actor(),
        )
        assert json.loads(response)["domain_code"] == "guardrail_violated"

    async def test_health(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_departments_get_health"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"department_id": str(uuid4())},
        )
        assert json.loads(response)["status"] == "ok"


class TestTeams:
    async def test_create_and_get(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_teams_create"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"name": "Core"},
            actor=make_test_actor(),
        )
        created = json.loads(response)
        assert created["status"] == "ok"
        team_id = created["data"]["id"]
        get_handler = ORGANIZATION_HANDLERS["synthorg_teams_get"]
        response_get = await get_handler(
            app_state=fake_app_state,
            arguments={"team_id": team_id},
        )
        assert json.loads(response_get)["status"] == "ok"

    async def test_list(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_teams_list"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "ok"

    async def test_delete_guardrails(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_teams_delete"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"team_id": str(uuid4())},
            actor=make_test_actor(),
        )
        assert json.loads(response)["domain_code"] == "guardrail_violated"


class TestRoleVersions:
    async def test_list(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_role_versions_list"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "ok"

    async def test_get_not_found(self, fake_app_state: SimpleNamespace) -> None:
        handler = ORGANIZATION_HANDLERS["synthorg_role_versions_get"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"version_id": "v1"},
        )
        assert json.loads(response)["domain_code"] == "not_found"
