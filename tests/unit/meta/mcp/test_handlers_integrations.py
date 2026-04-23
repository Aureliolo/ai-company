"""Unit tests for integrations MCP handlers.

Covers 21 tools across MCP catalog (5), oauth (3), clients (5),
artifacts (4), ontology (4).
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from synthorg.communication.mcp_errors import CapabilityNotSupportedError
from synthorg.integrations.mcp_services import (
    ArtifactFacadeService,
    ClientFacadeService,
    OAuthFacadeService,
)
from synthorg.meta.mcp.handlers.integrations import INTEGRATION_HANDLERS
from tests.unit.meta.mcp.conftest import make_test_actor

pytestmark = pytest.mark.unit


@pytest.fixture
def fake_catalog() -> AsyncMock:
    service = AsyncMock()
    service.list_catalog = AsyncMock(return_value=())
    service.search_catalog = AsyncMock(return_value=())
    service.get_catalog_entry = AsyncMock(return_value=None)
    service.install_catalog_entry = AsyncMock(return_value={"installed": True})
    service.uninstall_catalog_entry = AsyncMock(return_value=True)
    return service


@pytest.fixture
def fake_ontology() -> AsyncMock:
    service = AsyncMock()
    service.list_entities = AsyncMock(return_value=())
    service.get_entity = AsyncMock(return_value=None)
    service.get_relationships = AsyncMock(return_value=())
    service.search = AsyncMock(return_value=())
    return service


@pytest.fixture
def real_oauth() -> OAuthFacadeService:
    return OAuthFacadeService()


@pytest.fixture
def real_clients() -> ClientFacadeService:
    return ClientFacadeService()


@pytest.fixture
def real_artifacts() -> ArtifactFacadeService:
    storage = MagicMock()
    return ArtifactFacadeService(storage=storage)


@pytest.fixture
def fake_app_state(
    fake_catalog: AsyncMock,
    real_oauth: OAuthFacadeService,
    real_clients: ClientFacadeService,
    real_artifacts: ArtifactFacadeService,
    fake_ontology: AsyncMock,
) -> SimpleNamespace:
    return SimpleNamespace(
        mcp_catalog_facade_service=fake_catalog,
        oauth_facade_service=real_oauth,
        client_facade_service=real_clients,
        artifact_facade_service=real_artifacts,
        ontology_facade_service=fake_ontology,
    )


class TestMCPCatalog:
    async def test_list(self, fake_app_state: SimpleNamespace) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_mcp_catalog_list"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "ok"

    async def test_search_requires_query(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_mcp_catalog_search"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "error"

    async def test_get_not_found(self, fake_app_state: SimpleNamespace) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_mcp_catalog_get"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"entry_id": "x"},
        )
        assert json.loads(response)["domain_code"] == "not_found"

    async def test_install(self, fake_app_state: SimpleNamespace) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_mcp_catalog_install"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"entry_id": "x"},
            actor=make_test_actor(),
        )
        assert json.loads(response)["status"] == "ok"

    async def test_install_capability_gap(
        self,
        fake_app_state: SimpleNamespace,
        fake_catalog: AsyncMock,
    ) -> None:
        fake_catalog.install_catalog_entry = AsyncMock(
            side_effect=CapabilityNotSupportedError("mcp_catalog_install", "x"),
        )
        handler = INTEGRATION_HANDLERS["synthorg_mcp_catalog_install"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"entry_id": "x"},
            actor=make_test_actor(),
        )
        assert json.loads(response)["domain_code"] == "not_supported"

    async def test_uninstall_guardrails(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_mcp_catalog_uninstall"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"installation_id": "x"},
            actor=make_test_actor(),
        )
        assert json.loads(response)["domain_code"] == "guardrail_violated"


class TestOAuth:
    async def test_configure_and_list(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        configure = INTEGRATION_HANDLERS["synthorg_oauth_configure_provider"]
        response = await configure(
            app_state=fake_app_state,
            arguments={
                "name": "test-provider",
                "client_id": "c",
                "authorize_url": "https://example.test/auth",
                "token_url": "https://example.test/token",
                "scopes": ["repo"],
            },
            actor=make_test_actor(),
        )
        assert json.loads(response)["status"] == "ok"
        lst = await INTEGRATION_HANDLERS["synthorg_oauth_list_providers"](
            app_state=fake_app_state,
            arguments={},
        )
        payload = json.loads(lst)
        assert payload["status"] == "ok"
        assert len(payload["data"]) == 1

    async def test_remove_guardrails(self, fake_app_state: SimpleNamespace) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_oauth_remove_provider"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"name": "test-provider"},
            actor=make_test_actor(),
        )
        assert json.loads(response)["domain_code"] == "guardrail_violated"


class TestClients:
    async def test_create_and_satisfaction(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        create = INTEGRATION_HANDLERS["synthorg_clients_create"]
        response = await create(
            app_state=fake_app_state,
            arguments={"name": "Acme"},
            actor=make_test_actor(),
        )
        data = json.loads(response)["data"]
        client_id = data["id"]
        sat = await INTEGRATION_HANDLERS["synthorg_clients_get_satisfaction"](
            app_state=fake_app_state,
            arguments={"client_id": client_id},
        )
        assert json.loads(sat)["status"] == "ok"

    async def test_deactivate_guardrails(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_clients_deactivate"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"client_id": str(uuid4())},
            actor=make_test_actor(),
        )
        assert json.loads(response)["domain_code"] == "guardrail_violated"


class TestArtifacts:
    async def test_create_and_list(self, fake_app_state: SimpleNamespace) -> None:
        create = INTEGRATION_HANDLERS["synthorg_artifacts_create"]
        response = await create(
            app_state=fake_app_state,
            arguments={
                "name": "a.txt",
                "content_type": "text/plain",
                "size_bytes": 10,
                "storage_ref": "s3://bucket/a.txt",
            },
            actor=make_test_actor(),
        )
        assert json.loads(response)["status"] == "ok"
        listing = await INTEGRATION_HANDLERS["synthorg_artifacts_list"](
            app_state=fake_app_state,
            arguments={},
        )
        assert json.loads(listing)["pagination"]["total"] == 1

    async def test_delete_guardrails(self, fake_app_state: SimpleNamespace) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_artifacts_delete"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"artifact_id": str(uuid4())},
            actor=make_test_actor(),
        )
        assert json.loads(response)["domain_code"] == "guardrail_violated"


class TestOntology:
    async def test_list_entities(self, fake_app_state: SimpleNamespace) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_ontology_list_entities"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "ok"

    async def test_get_not_found(self, fake_app_state: SimpleNamespace) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_ontology_get_entity"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"entity_id": "x"},
        )
        assert json.loads(response)["domain_code"] == "not_found"

    async def test_search_requires_query(
        self,
        fake_app_state: SimpleNamespace,
    ) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_ontology_search"]
        response = await handler(app_state=fake_app_state, arguments={})
        assert json.loads(response)["status"] == "error"

    async def test_get_relationships(self, fake_app_state: SimpleNamespace) -> None:
        handler = INTEGRATION_HANDLERS["synthorg_ontology_get_relationships"]
        response = await handler(
            app_state=fake_app_state,
            arguments={"entity_id": "x"},
        )
        assert json.loads(response)["status"] == "ok"
