"""Custom signal rule service layer.

Wraps :class:`CustomRuleRepository` so the
``/meta/custom-rules`` controller stays thin and all
``META_CUSTOM_RULE_*`` audit logging lives in one place.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.meta.rules.custom import CustomRuleDefinition
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_CUSTOM_RULE_CREATED,
    META_CUSTOM_RULE_DELETED,
    META_CUSTOM_RULE_TOGGLED,
    META_CUSTOM_RULE_UPDATED,
)

if TYPE_CHECKING:
    from synthorg.persistence.custom_rule_repo import CustomRuleRepository

logger = get_logger(__name__)


class CustomRuleNotFoundError(Exception):
    """Raised when an id-targeted update/toggle/delete misses."""


class CustomRulesService:
    """CRUD + toggle orchestration with uniform audit logging."""

    __slots__ = ("_repo",)

    def __init__(self, *, repo: CustomRuleRepository) -> None:
        self._repo = repo

    async def list_rules(self) -> tuple[CustomRuleDefinition, ...]:
        """List all custom rules."""
        return await self._repo.list_rules()

    async def get(self, rule_id: NotBlankStr) -> CustomRuleDefinition | None:
        """Return a single rule by id, or ``None`` when missing."""
        return await self._repo.get(rule_id)

    async def create(self, definition: CustomRuleDefinition) -> CustomRuleDefinition:
        """Persist a new rule and emit an audit log."""
        await self._repo.save(definition)
        logger.info(
            META_CUSTOM_RULE_CREATED,
            rule_id=str(definition.id),
            rule_name=definition.name,
        )
        return definition

    async def update(
        self,
        rule_id: NotBlankStr,
        updates: dict[str, object],
    ) -> CustomRuleDefinition:
        """Apply a partial update to the rule with *rule_id*.

        Raises:
            CustomRuleNotFoundError: If the target id does not exist.
        """
        existing = await self._repo.get(rule_id)
        if existing is None:
            msg = f"Custom rule {rule_id} not found"
            raise CustomRuleNotFoundError(msg)
        payload = {
            **existing.model_dump(),
            **updates,
            "updated_at": datetime.now(UTC),
        }
        updated = CustomRuleDefinition.model_validate(payload)
        await self._repo.save(updated)
        logger.info(
            META_CUSTOM_RULE_UPDATED,
            rule_id=str(rule_id),
            rule_name=updated.name,
        )
        return updated

    async def delete(self, rule_id: NotBlankStr) -> None:
        """Delete a rule by id.

        Raises:
            CustomRuleNotFoundError: If no rule with *rule_id* exists.
        """
        deleted = await self._repo.delete(rule_id)
        if not deleted:
            msg = f"Custom rule {rule_id} not found"
            raise CustomRuleNotFoundError(msg)
        logger.info(META_CUSTOM_RULE_DELETED, rule_id=str(rule_id))

    async def toggle(self, rule_id: NotBlankStr) -> CustomRuleDefinition:
        """Flip the ``enabled`` flag on the rule with *rule_id*.

        Raises:
            CustomRuleNotFoundError: If no rule with *rule_id* exists.
        """
        existing = await self._repo.get(rule_id)
        if existing is None:
            msg = f"Custom rule {rule_id} not found"
            raise CustomRuleNotFoundError(msg)
        toggled = existing.model_copy(
            update={
                "enabled": not existing.enabled,
                "updated_at": datetime.now(UTC),
            },
        )
        await self._repo.save(toggled)
        logger.info(
            META_CUSTOM_RULE_TOGGLED,
            rule_id=str(rule_id),
            enabled=toggled.enabled,
        )
        return toggled
