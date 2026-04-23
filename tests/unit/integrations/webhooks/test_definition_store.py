"""Tests for the in-memory webhook definition store."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.integrations.webhooks.definition_store import (
    InMemoryWebhookDefinitionStore,
)
from synthorg.integrations.webhooks.definition_store_protocol import (
    WebhookDefinitionStore,
)
from synthorg.integrations.webhooks.models import (
    WebhookDefinition,
    WebhookVerifierKind,
)

pytestmark = pytest.mark.unit


def _definition(
    *,
    name: str = "default",
    issuer: str = "test-provider",
    created_at: datetime | None = None,
) -> WebhookDefinition:
    if created_at is None:
        return WebhookDefinition(
            name=NotBlankStr(name),
            issuer=NotBlankStr(issuer),
            verifier_kind=WebhookVerifierKind.HMAC_SHA256,
            secret_ref=NotBlankStr("ref-1"),
            channel=NotBlankStr("webhooks.inbound"),
        )
    return WebhookDefinition(
        name=NotBlankStr(name),
        issuer=NotBlankStr(issuer),
        verifier_kind=WebhookVerifierKind.HMAC_SHA256,
        secret_ref=NotBlankStr("ref-1"),
        channel=NotBlankStr("webhooks.inbound"),
        created_at=created_at,
    )


class TestInMemoryWebhookDefinitionStore:
    def test_satisfies_protocol(self) -> None:
        assert isinstance(InMemoryWebhookDefinitionStore(), WebhookDefinitionStore)

    async def test_add_then_get_by_id_and_name(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        definition = _definition()
        await store.add(definition)
        fetched_by_id = await store.get_by_id(NotBlankStr(str(definition.id)))
        fetched_by_name = await store.get_by_name(definition.name)
        assert fetched_by_id == definition
        assert fetched_by_name == definition

    async def test_add_rejects_duplicate_name(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        await store.add(_definition(name="wh"))
        with pytest.raises(ValueError, match="already exists"):
            await store.add(_definition(name="wh"))

    async def test_replace_existing(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        original = _definition()
        await store.add(original)
        updated = original.model_copy(update={"issuer": NotBlankStr("stripe")})
        await store.replace(updated)
        fetched = await store.get_by_id(NotBlankStr(str(original.id)))
        assert fetched is not None
        assert fetched.issuer == "stripe"

    async def test_replace_unknown_id_raises(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        orphan = _definition()
        with pytest.raises(KeyError):
            await store.replace(orphan)

    async def test_replace_rejects_name_collision_with_other_id(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        first = _definition(name="alpha")
        second = _definition(name="beta")
        await store.add(first)
        await store.add(second)
        clashing = second.model_copy(update={"name": first.name})
        with pytest.raises(ValueError, match="already exists"):
            await store.replace(clashing)
        fetched = await store.get_by_id(NotBlankStr(str(second.id)))
        assert fetched is not None
        assert fetched.name == "beta"

    async def test_replace_allows_same_name_same_id(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        original = _definition(name="gamma")
        await store.add(original)
        updated = original.model_copy(update={"issuer": NotBlankStr("stripe")})
        await store.replace(updated)
        fetched = await store.get_by_id(NotBlankStr(str(original.id)))
        assert fetched is not None
        assert fetched.issuer == "stripe"
        assert fetched.name == "gamma"

    async def test_delete_returns_true_when_present(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        definition = _definition()
        await store.add(definition)
        removed = await store.delete(NotBlankStr(str(definition.id)))
        assert removed is True
        assert await store.get_by_id(NotBlankStr(str(definition.id))) is None

    async def test_delete_returns_false_when_absent(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        removed = await store.delete(NotBlankStr(str(uuid4())))
        assert removed is False

    async def test_list_is_newest_first(self) -> None:
        store = InMemoryWebhookDefinitionStore()
        now = datetime.now(UTC)
        # Explicit timestamps make newest-first ordering deterministic
        # even when wall-clock resolution collapses the default factory
        # values.
        first = _definition(name="a", created_at=now - timedelta(minutes=5))
        second = _definition(name="b", created_at=now)
        await store.add(first)
        await store.add(second)
        listed = tuple(await store.list_definitions())
        assert listed[0].name == second.name
        assert listed[1].name == first.name
