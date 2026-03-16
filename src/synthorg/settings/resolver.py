"""Config resolver — typed config access backed by SettingsService.

Bridges the gap between :class:`SettingsService` (which returns string
values) and consumers that need typed Python objects.  Provides scalar
accessors and composed-read methods that assemble full Pydantic config
models from individually resolved settings.
"""

import asyncio
from enum import StrEnum
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.settings import (
    SETTINGS_VALIDATION_FAILED,
    SETTINGS_VALUE_RESOLVED,
)

if TYPE_CHECKING:
    from synthorg.budget.config import BudgetConfig
    from synthorg.config.schema import RootConfig
    from synthorg.core.enums import AutonomyLevel
    from synthorg.engine.coordination.config import CoordinationConfig
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)


class ConfigResolver:
    """Typed config accessor backed by :class:`SettingsService`.

    Scalar accessors call ``SettingsService.get()`` and coerce the
    string result to the requested Python type.

    Composed-read methods assemble full Pydantic config models by
    reading individual settings and merging them onto a base config
    loaded from YAML (for fields not yet in the settings registry).

    Args:
        settings_service: The settings service for value resolution.
        config: Root company configuration used as the base for
            composed reads (provides defaults for unregistered fields).
    """

    def __init__(
        self,
        *,
        settings_service: SettingsService,
        config: RootConfig,
    ) -> None:
        self._settings = settings_service
        self._config = config

    async def get_str(self, namespace: str, key: str) -> str:
        """Resolve a setting as a string.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            The resolved value.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
        """
        result = await self._settings.get(namespace, key)
        return result.value

    async def get_int(self, namespace: str, key: str) -> int:
        """Resolve a setting as an integer.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            The resolved value as an ``int``.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
            ValueError: If the value cannot be parsed as an integer.
        """
        result = await self._settings.get(namespace, key)
        try:
            return int(result.value)
        except ValueError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_integer",
            )
            raise

    async def get_float(self, namespace: str, key: str) -> float:
        """Resolve a setting as a float.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            The resolved value as a ``float``.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
            ValueError: If the value cannot be parsed as a float.
        """
        result = await self._settings.get(namespace, key)
        try:
            return float(result.value)
        except ValueError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_float",
            )
            raise

    async def get_bool(self, namespace: str, key: str) -> bool:
        """Resolve a setting as a boolean.

        Accepts ``"true"``/``"false"``/``"1"``/``"0"``
        (case-insensitive).

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            The resolved value as a ``bool``.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
            ValueError: If the value is not a recognized boolean string.
        """
        result = await self._settings.get(namespace, key)
        try:
            return _parse_bool(result.value)
        except ValueError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_boolean",
            )
            raise

    async def get_enum[E: StrEnum](
        self,
        namespace: str,
        key: str,
        enum_cls: type[E],
    ) -> E:
        """Resolve a setting as a ``StrEnum`` member.

        Args:
            namespace: Setting namespace.
            key: Setting key.
            enum_cls: The enum class to coerce the value into.

        Returns:
            The matching enum member.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
            ValueError: If the value does not match any enum member.
        """
        result = await self._settings.get(namespace, key)
        try:
            return enum_cls(result.value)
        except ValueError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_enum",
            )
            raise

    async def get_autonomy_level(self) -> AutonomyLevel:
        """Resolve the company-wide default autonomy level.

        Returns:
            The resolved ``AutonomyLevel`` enum member.
        """
        from synthorg.core.enums import AutonomyLevel  # noqa: PLC0415

        return await self.get_enum("company", "autonomy_level", AutonomyLevel)

    async def get_budget_config(self) -> BudgetConfig:
        """Assemble a ``BudgetConfig`` from individually resolved settings.

        Starts from the YAML-loaded base config and overrides fields
        that have registered settings definitions.  Unregistered fields
        (e.g. ``downgrade_map``, ``boundary``) keep their YAML values.

        Uses ``asyncio.TaskGroup`` to resolve all settings in parallel.

        Returns:
            A ``BudgetConfig`` with DB/env overrides applied.
        """
        from synthorg.budget.config import (  # noqa: PLC0415
            BudgetAlertConfig,
        )

        base = self._config.budget

        async with asyncio.TaskGroup() as tg:
            t_monthly = tg.create_task(self.get_float("budget", "total_monthly"))
            t_per_task = tg.create_task(self.get_float("budget", "per_task_limit"))
            t_daily = tg.create_task(self.get_float("budget", "per_agent_daily_limit"))
            t_downgrade_en = tg.create_task(
                self.get_bool("budget", "auto_downgrade_enabled")
            )
            t_downgrade_th = tg.create_task(
                self.get_int("budget", "auto_downgrade_threshold")
            )
            t_reset = tg.create_task(self.get_int("budget", "reset_day"))
            t_warn = tg.create_task(self.get_int("budget", "alert_warn_at"))
            t_crit = tg.create_task(self.get_int("budget", "alert_critical_at"))
            t_stop = tg.create_task(self.get_int("budget", "alert_hard_stop_at"))

        logger.debug(
            SETTINGS_VALUE_RESOLVED,
            namespace="budget",
            key="_composed",
            source="resolver",
        )

        return base.model_copy(
            update={
                "total_monthly": t_monthly.result(),
                "per_task_limit": t_per_task.result(),
                "per_agent_daily_limit": t_daily.result(),
                "reset_day": t_reset.result(),
                "alerts": BudgetAlertConfig(
                    warn_at=t_warn.result(),
                    critical_at=t_crit.result(),
                    hard_stop_at=t_stop.result(),
                ),
                "auto_downgrade": base.auto_downgrade.model_copy(
                    update={
                        "enabled": t_downgrade_en.result(),
                        "threshold": t_downgrade_th.result(),
                    },
                ),
            },
        )

    async def get_coordination_config(
        self,
        *,
        max_concurrency_per_wave: int | None = None,
        fail_fast: bool | None = None,
    ) -> CoordinationConfig:
        """Assemble a per-run ``CoordinationConfig`` from settings.

        Resolves coordination settings from the settings service using
        ``asyncio.TaskGroup`` for parallel resolution, then applies
        request-level overrides on top.

        Args:
            max_concurrency_per_wave: Request-level override for max
                concurrency (takes precedence over the setting value).
            fail_fast: Request-level override for fail-fast behaviour.

        Returns:
            A ``CoordinationConfig`` with settings + request overrides.
        """
        from synthorg.engine.coordination.config import (  # noqa: PLC0415
            CoordinationConfig,
        )

        async with asyncio.TaskGroup() as tg:
            t_wave = tg.create_task(self.get_int("coordination", "max_wave_size"))
            t_ff = tg.create_task(self.get_bool("coordination", "fail_fast"))
            t_iso = tg.create_task(
                self.get_bool("coordination", "enable_workspace_isolation")
            )
            t_branch = tg.create_task(self.get_str("coordination", "base_branch"))

        logger.debug(
            SETTINGS_VALUE_RESOLVED,
            namespace="coordination",
            key="_composed",
            source="resolver",
        )

        return CoordinationConfig(
            max_concurrency_per_wave=(
                max_concurrency_per_wave
                if max_concurrency_per_wave is not None
                else t_wave.result()
            ),
            fail_fast=(fail_fast if fail_fast is not None else t_ff.result()),
            enable_workspace_isolation=t_iso.result(),
            base_branch=t_branch.result(),
        )


_BOOL_TRUE = frozenset({"true", "1"})
_BOOL_FALSE = frozenset({"false", "0"})


def _parse_bool(value: str) -> bool:
    """Parse a string into a boolean.

    Accepts ``"true"``/``"false"``/``"1"``/``"0"``
    (case-insensitive).

    Args:
        value: String to parse.

    Returns:
        The parsed boolean.

    Raises:
        ValueError: If the string is not a recognised boolean.
    """
    lower = value.lower()
    if lower in _BOOL_TRUE:
        return True
    if lower in _BOOL_FALSE:
        return False
    msg = f"Cannot parse {value!r} as boolean"
    raise ValueError(msg)
