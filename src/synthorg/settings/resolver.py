"""Config resolver — typed config access backed by SettingsService.

Bridges the gap between :class:`SettingsService` (which returns
:class:`~synthorg.settings.models.SettingValue` objects with a string
``.value``) and consumers that need typed Python objects.  Provides
scalar accessors and composed-read methods that assemble full Pydantic
config models from individually resolved settings.
"""

import asyncio
import json
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from synthorg.observability import get_logger
from synthorg.observability.events.settings import (
    SETTINGS_FETCH_FAILED,
    SETTINGS_NOT_FOUND,
    SETTINGS_VALIDATION_FAILED,
)
from synthorg.settings.errors import SettingNotFoundError, SettingsEncryptionError

if TYPE_CHECKING:
    from pydantic import BaseModel

    from synthorg.api.config import ApiConfig
    from synthorg.budget.config import BudgetAlertConfig, BudgetConfig
    from synthorg.config.schema import AgentConfig, ProviderConfig, RootConfig
    from synthorg.core.company import Department
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

    The ``config`` snapshot is captured at construction time and is
    **not** updated if the underlying ``RootConfig`` is replaced.
    ``ConfigResolver`` and ``AppState`` must always hold the same
    reference; see ``AppState.__init__`` for the wiring invariant.

    Args:
        settings_service: The settings service for value resolution.
        config: Root company configuration used as the base for
            composed reads (provides defaults for unregistered fields).

    Raises:
        TypeError: If *settings_service* is ``None``.
    """

    def __init__(
        self,
        *,
        settings_service: SettingsService,
        config: RootConfig,
    ) -> None:
        # runtime defence for callers without type checking
        if settings_service is None:
            msg = "settings_service must not be None"  # type: ignore[unreachable]
            logger.error(SETTINGS_VALIDATION_FAILED, reason=msg)
            raise TypeError(msg)
        self._settings = settings_service
        self._config = config

    async def get_str(self, namespace: str, key: str) -> str:
        """Resolve a setting as a string.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            The resolved value as a ``str``.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
        """
        try:
            result = await self._settings.get(namespace, key)
        except SettingNotFoundError:
            logger.warning(
                SETTINGS_NOT_FOUND,
                namespace=namespace,
                key=key,
            )
            raise
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
        try:
            result = await self._settings.get(namespace, key)
        except SettingNotFoundError:
            logger.warning(
                SETTINGS_NOT_FOUND,
                namespace=namespace,
                key=key,
            )
            raise
        try:
            return int(result.value)
        except ValueError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_integer",
                exc_info=True,
            )
            msg = f"Setting {namespace}/{key} has an invalid integer value"
            raise ValueError(msg) from None

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
        try:
            result = await self._settings.get(namespace, key)
        except SettingNotFoundError:
            logger.warning(
                SETTINGS_NOT_FOUND,
                namespace=namespace,
                key=key,
            )
            raise
        try:
            return float(result.value)
        except ValueError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_float",
                exc_info=True,
            )
            msg = f"Setting {namespace}/{key} has an invalid float value"
            raise ValueError(msg) from None

    async def get_bool(self, namespace: str, key: str) -> bool:
        """Resolve a setting as a boolean.

        Accepted values are delegated to :func:`_parse_bool`.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            The resolved value as a ``bool``.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
            ValueError: If the value is not a recognized boolean string.
        """
        try:
            result = await self._settings.get(namespace, key)
        except SettingNotFoundError:
            logger.warning(
                SETTINGS_NOT_FOUND,
                namespace=namespace,
                key=key,
            )
            raise
        try:
            return _parse_bool(result.value)
        except ValueError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_boolean",
                exc_info=True,
            )
            msg = f"Setting {namespace}/{key} is not a recognized boolean"
            raise ValueError(msg) from None

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
        try:
            result = await self._settings.get(namespace, key)
        except SettingNotFoundError:
            logger.warning(
                SETTINGS_NOT_FOUND,
                namespace=namespace,
                key=key,
            )
            raise
        try:
            return enum_cls(result.value)
        except ValueError:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_enum",
                enum_cls=enum_cls.__name__,
                exc_info=True,
            )
            msg = f"Setting {namespace}/{key} has an invalid {enum_cls.__name__} value"
            raise ValueError(msg) from None

    async def get_autonomy_level(self) -> AutonomyLevel:
        """Resolve the company-wide default autonomy level.

        Returns:
            The resolved ``AutonomyLevel`` enum member.

        Raises:
            SettingNotFoundError: If the autonomy_level key is
                not registered.
            ValueError: If the stored value does not match any
                ``AutonomyLevel`` member.
        """
        from synthorg.core.enums import AutonomyLevel  # noqa: PLC0415

        return await self.get_enum("company", "autonomy_level", AutonomyLevel)

    async def get_json(self, namespace: str, key: str) -> Any:
        """Resolve a setting as parsed JSON.

        Args:
            namespace: Setting namespace.
            key: Setting key.

        Returns:
            The parsed JSON value (list, dict, scalar, etc.).
            Note that JSON ``null`` parses to Python ``None``.

        Raises:
            SettingNotFoundError: If the key is not in the registry.
            SettingsEncryptionError: If the value cannot be decrypted.
            ValueError: If the value is not valid JSON.
        """
        try:
            result = await self._settings.get(namespace, key)
        except SettingNotFoundError:
            logger.warning(
                SETTINGS_NOT_FOUND,
                namespace=namespace,
                key=key,
            )
            raise
        except SettingsEncryptionError:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                key=key,
                reason="decryption_failed",
                exc_info=True,
            )
            raise
        try:
            return json.loads(result.value)
        except json.JSONDecodeError as exc:
            logger.warning(
                SETTINGS_VALIDATION_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_json",
                exc_info=True,
            )
            msg = f"Setting {namespace}/{key} has an invalid JSON value"
            raise ValueError(msg) from exc

    async def _resolve_list_setting(
        self,
        namespace: str,
        key: str,
        model_cls: type[BaseModel],
        fallback: tuple[Any, ...],
    ) -> tuple[Any, ...]:
        """Resolve a JSON list setting to a tuple of validated models.

        Falls back to *fallback* on ``None``, invalid JSON, wrong
        shape, or schema validation failure.
        """
        from pydantic import ValidationError  # noqa: PLC0415

        try:
            raw = await self.get_json(namespace, key)
        except ValueError:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_json_fallback",
                exc_info=True,
            )
            return fallback
        if raw is None:
            return fallback
        if not isinstance(raw, list):
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                key=key,
                reason="expected_list_fallback",
                value_type=type(raw).__name__,
            )
            return fallback
        try:
            return tuple(model_cls.model_validate(item) for item in raw)
        except ValidationError:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_schema_fallback",
                exc_info=True,
            )
            return fallback

    async def _resolve_dict_setting(
        self,
        namespace: str,
        key: str,
        model_cls: type[BaseModel],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve a JSON dict setting to a dict of validated models.

        Falls back to *fallback* on ``None``, invalid JSON, wrong
        shape, or schema validation failure.
        """
        from pydantic import ValidationError  # noqa: PLC0415

        try:
            raw = await self.get_json(namespace, key)
        except ValueError:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_json_fallback",
                exc_info=True,
            )
            return fallback
        if raw is None:
            return fallback
        if not isinstance(raw, dict):
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                key=key,
                reason="expected_dict_fallback",
                value_type=type(raw).__name__,
            )
            return fallback
        try:
            return {name: model_cls.model_validate(conf) for name, conf in raw.items()}
        except ValidationError:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace=namespace,
                key=key,
                reason="invalid_schema_fallback",
                exc_info=True,
            )
            return fallback

    async def get_agents(self) -> tuple[AgentConfig, ...]:
        """Resolve agent configurations from settings.

        Falls back to ``RootConfig.agents`` if the setting value is
        ``None``, contains invalid JSON, or fails schema validation.
        An explicit empty list ``[]`` is a valid override.

        Raises:
            SettingNotFoundError: If the agents key is not
                in the registry.
            SettingsEncryptionError: If decryption fails.
        """
        from synthorg.config.schema import AgentConfig  # noqa: PLC0415

        return await self._resolve_list_setting(
            "company",
            "agents",
            AgentConfig,
            self._config.agents,
        )

    async def get_departments(self) -> tuple[Department, ...]:
        """Resolve department configurations from settings.

        Falls back to ``RootConfig.departments`` if the setting value
        is ``None``, contains invalid JSON, or fails schema validation.
        An explicit empty list ``[]`` is a valid override.

        Raises:
            SettingNotFoundError: If the departments key is not
                in the registry.
            SettingsEncryptionError: If decryption fails.
        """
        from synthorg.core.company import Department  # noqa: PLC0415

        return await self._resolve_list_setting(
            "company",
            "departments",
            Department,
            self._config.departments,
        )

    async def get_provider_configs(self) -> dict[str, ProviderConfig]:
        """Resolve provider configurations from settings.

        Falls back to ``RootConfig.providers`` if the setting value
        is ``None``, contains invalid JSON, or fails schema validation.
        An explicit empty dict ``{}`` is a valid override.

        Raises:
            SettingNotFoundError: If the ``configs`` key is not
                in the registry.
            SettingsEncryptionError: If decryption fails.
        """
        from synthorg.config.schema import ProviderConfig  # noqa: PLC0415

        return await self._resolve_dict_setting(
            "providers",
            "configs",
            ProviderConfig,
            dict(self._config.providers),
        )

    async def get_budget_config(self) -> BudgetConfig:
        """Assemble a ``BudgetConfig`` from individually resolved settings.

        Starts from the YAML-loaded base config and overrides fields
        that have registered settings definitions.  Unregistered fields
        on nested models (e.g. ``auto_downgrade.downgrade_map``,
        ``auto_downgrade.boundary``) keep their YAML values.

        Uses ``asyncio.TaskGroup`` to resolve all settings in parallel.
        If any individual resolution fails, the ``ExceptionGroup`` is
        unwrapped and the first cause is re-raised directly.

        Returns:
            A ``BudgetConfig`` with DB/env overrides applied.

        Raises:
            SettingNotFoundError: If a required budget setting is
                missing from the registry.
            ValueError: If a resolved value cannot be parsed or if
                the assembled alert thresholds violate the ordering
                constraint (``warn_at < critical_at < hard_stop_at``).
        """
        base = self._config.budget

        try:
            async with asyncio.TaskGroup() as tg:
                t_monthly = tg.create_task(self.get_float("budget", "total_monthly"))
                t_per_task = tg.create_task(self.get_float("budget", "per_task_limit"))
                t_daily = tg.create_task(
                    self.get_float("budget", "per_agent_daily_limit")
                )
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
        except ExceptionGroup as eg:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace="budget",
                key="_composed",
                error_count=len(eg.exceptions),
                exc_info=True,
            )
            raise eg.exceptions[0] from eg

        alerts = _build_budget_alerts(t_warn.result(), t_crit.result(), t_stop.result())
        return base.model_copy(
            update={
                "total_monthly": t_monthly.result(),
                "per_task_limit": t_per_task.result(),
                "per_agent_daily_limit": t_daily.result(),
                "reset_day": t_reset.result(),
                "alerts": alerts,
                "auto_downgrade": base.auto_downgrade.model_copy(
                    update={
                        "enabled": t_downgrade_en.result(),
                        "threshold": t_downgrade_th.result(),
                    },
                ),
            },
        )

    async def get_api_config(self) -> ApiConfig:
        """Assemble an ``ApiConfig`` with runtime-editable overrides.

        Resolves the four runtime-editable API settings (rate-limit
        max requests, rate-limit time unit, JWT expiry, min password
        length) and merges them onto the YAML-loaded base config.

        Bootstrap-only settings (``server_host``, ``server_port``,
        ``api_prefix``, ``cors_allowed_origins``,
        ``rate_limit_exclude_paths``, ``auth_exclude_paths``) are
        **not** resolved — they are baked into the Litestar app at
        construction and require a restart to take effect.

        Uses ``asyncio.TaskGroup`` to resolve all settings in parallel.

        Returns:
            An ``ApiConfig`` with DB/env overrides applied to the
            runtime-editable fields.

        Raises:
            SettingNotFoundError: If a required API setting is
                missing from the registry.
            ValueError: If a resolved value cannot be parsed.
        """
        from synthorg.api.config import RateLimitTimeUnit  # noqa: PLC0415

        base = self._config.api

        try:
            async with asyncio.TaskGroup() as tg:
                t_max_req = tg.create_task(
                    self.get_int("api", "rate_limit_max_requests")
                )
                t_time_unit = tg.create_task(
                    self.get_enum("api", "rate_limit_time_unit", RateLimitTimeUnit)
                )
                t_jwt_exp = tg.create_task(self.get_int("api", "jwt_expiry_minutes"))
                t_min_pw = tg.create_task(self.get_int("api", "min_password_length"))
        except ExceptionGroup as eg:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace="api",
                key="_composed",
                error_count=len(eg.exceptions),
                exc_info=True,
            )
            raise eg.exceptions[0] from eg

        return base.model_copy(
            update={
                "rate_limit": base.rate_limit.model_copy(
                    update={
                        "max_requests": t_max_req.result(),
                        "time_unit": t_time_unit.result(),
                    },
                ),
                "auth": base.auth.model_copy(
                    update={
                        "jwt_expiry_minutes": t_jwt_exp.result(),
                        "min_password_length": t_min_pw.result(),
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
        request-level overrides on top.  If any individual resolution
        fails, the ``ExceptionGroup`` is unwrapped and the first cause
        is re-raised directly.

        ``CoordinationConfig`` is constructed from scratch (not via
        ``model_copy``) because all its fields are registered in the
        settings registry.  The ``default_topology`` setting is
        resolved separately by the ``TopologyDispatcher`` and is not
        part of ``CoordinationConfig``.

        Args:
            max_concurrency_per_wave: Request-level override for max
                concurrency (takes precedence over the setting value).
            fail_fast: Request-level override for fail-fast behaviour.

        Returns:
            A ``CoordinationConfig`` with settings + request overrides.

        Raises:
            SettingNotFoundError: If a required coordination setting
                is missing from the registry.
            ValueError: If a resolved value cannot be parsed.
        """
        from synthorg.engine.coordination.config import (  # noqa: PLC0415
            CoordinationConfig,
        )

        try:
            async with asyncio.TaskGroup() as tg:
                t_wave = tg.create_task(
                    self.get_int("coordination", "max_concurrency_per_wave")
                )
                t_ff = tg.create_task(self.get_bool("coordination", "fail_fast"))
                t_iso = tg.create_task(
                    self.get_bool("coordination", "enable_workspace_isolation")
                )
                t_branch = tg.create_task(self.get_str("coordination", "base_branch"))
        except ExceptionGroup as eg:
            logger.warning(
                SETTINGS_FETCH_FAILED,
                namespace="coordination",
                key="_composed",
                error_count=len(eg.exceptions),
                exc_info=True,
            )
            raise eg.exceptions[0] from eg

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


def _build_budget_alerts(warn: int, crit: int, stop: int) -> BudgetAlertConfig:
    """Construct ``BudgetAlertConfig`` with ordering validation.

    Args:
        warn: Warning threshold percent.
        crit: Critical threshold percent.
        stop: Hard-stop threshold percent.

    Returns:
        A validated ``BudgetAlertConfig``.

    Raises:
        ValueError: If the thresholds violate the ordering constraint
            (``warn < crit < stop``).
    """
    from pydantic import ValidationError  # noqa: PLC0415

    from synthorg.budget.config import BudgetAlertConfig  # noqa: PLC0415

    try:
        return BudgetAlertConfig(warn_at=warn, critical_at=crit, hard_stop_at=stop)
    except ValidationError as exc:
        logger.warning(
            SETTINGS_VALIDATION_FAILED,
            namespace="budget",
            key="_alerts",
            reason="threshold_ordering",
            exc_info=True,
        )
        msg = "Budget alert thresholds must satisfy warn < critical < hard_stop"
        raise ValueError(msg) from exc


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
    msg = "Value is not a recognized boolean string"
    raise ValueError(msg)
