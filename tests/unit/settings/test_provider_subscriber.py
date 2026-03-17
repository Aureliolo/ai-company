"""Tests for ProviderSettingsSubscriber."""

from unittest.mock import AsyncMock

import pytest

from synthorg.api.approval_store import ApprovalStore
from synthorg.api.state import AppState
from synthorg.config.schema import RootConfig
from synthorg.providers.routing.errors import UnknownStrategyError
from synthorg.providers.routing.router import ModelRouter
from synthorg.settings.enums import SettingNamespace, SettingSource
from synthorg.settings.models import SettingValue
from synthorg.settings.subscriber import SettingsSubscriber
from synthorg.settings.subscribers.provider_subscriber import (
    ProviderSettingsSubscriber,
)


def _setting_value(value: str) -> SettingValue:
    """Build a SettingValue matching SettingsService.get() return type."""
    return SettingValue(
        namespace=SettingNamespace.PROVIDERS,
        key="routing_strategy",
        value=value,
        source=SettingSource.DEFAULT,
    )


def _make_state(config: RootConfig | None = None) -> AppState:
    cfg = config or RootConfig(company_name="test")
    router = ModelRouter(cfg.routing, dict(cfg.providers))
    return AppState(
        config=cfg,
        approval_store=ApprovalStore(),
        model_router=router,
    )


def _make_subscriber(
    config: RootConfig | None = None,
    app_state: AppState | None = None,
    settings_service: AsyncMock | None = None,
) -> tuple[ProviderSettingsSubscriber, AppState]:
    cfg = config or RootConfig(company_name="test")
    state = app_state or _make_state(cfg)
    svc = settings_service or AsyncMock()
    svc.get = AsyncMock(return_value=_setting_value("cost_aware"))
    sub = ProviderSettingsSubscriber(
        config=cfg,
        app_state=state,
        settings_service=svc,
    )
    return sub, state


@pytest.mark.unit
class TestProviderSubscriberProtocol:
    """ProviderSettingsSubscriber conforms to SettingsSubscriber."""

    def test_isinstance_check(self) -> None:
        sub, _ = _make_subscriber()
        assert isinstance(sub, SettingsSubscriber)

    def test_watched_keys(self) -> None:
        sub, _ = _make_subscriber()
        assert ("providers", "routing_strategy") in sub.watched_keys
        assert ("providers", "default_provider") in sub.watched_keys
        assert ("providers", "retry_max_attempts") in sub.watched_keys

    def test_subscriber_name(self) -> None:
        sub, _ = _make_subscriber()
        assert sub.subscriber_name == "provider-settings"


@pytest.mark.unit
class TestProviderSubscriberRebuild:
    """on_settings_changed rebuilds ModelRouter when strategy changes."""

    async def test_routing_strategy_change_swaps_router(self) -> None:
        cfg = RootConfig(company_name="test")
        state = _make_state(cfg)
        old_router = state.model_router

        svc = AsyncMock()
        svc.get = AsyncMock(return_value=_setting_value("cost_aware"))
        sub = ProviderSettingsSubscriber(
            config=cfg,
            app_state=state,
            settings_service=svc,
        )
        await sub.on_settings_changed("providers", "routing_strategy")
        assert state.model_router is not old_router

    async def test_rebuild_failure_propagates(self) -> None:
        """Errors in _rebuild_router propagate to the dispatcher."""
        cfg = RootConfig(company_name="test")
        state = _make_state(cfg)
        old_router = state.model_router

        svc = AsyncMock()
        svc.get = AsyncMock(
            return_value=_setting_value("nonexistent_strategy"),
        )
        sub = ProviderSettingsSubscriber(
            config=cfg,
            app_state=state,
            settings_service=svc,
        )
        # Error propagates (dispatcher catches it for logging)
        with pytest.raises(UnknownStrategyError):
            await sub.on_settings_changed("providers", "routing_strategy")
        # Old router is still in place (swap never called)
        assert state.model_router is old_router

    async def test_default_provider_change_is_noop(self) -> None:
        cfg = RootConfig(company_name="test")
        state = _make_state(cfg)
        old_router = state.model_router

        svc = AsyncMock()
        svc.get = AsyncMock(return_value=_setting_value("some-provider"))
        sub = ProviderSettingsSubscriber(
            config=cfg,
            app_state=state,
            settings_service=svc,
        )
        await sub.on_settings_changed("providers", "default_provider")
        # Router not swapped for advisory-only settings
        assert state.model_router is old_router

    async def test_retry_max_attempts_change_is_noop(self) -> None:
        cfg = RootConfig(company_name="test")
        state = _make_state(cfg)
        old_router = state.model_router

        svc = AsyncMock()
        svc.get = AsyncMock(return_value=_setting_value("5"))
        sub = ProviderSettingsSubscriber(
            config=cfg,
            app_state=state,
            settings_service=svc,
        )
        await sub.on_settings_changed("providers", "retry_max_attempts")
        assert state.model_router is old_router

    async def test_settings_service_failure_preserves_old_router(self) -> None:
        """When SettingsService.get() fails, old router stays in place."""
        cfg = RootConfig(company_name="test")
        state = _make_state(cfg)
        old_router = state.model_router

        svc = AsyncMock()
        svc.get = AsyncMock(side_effect=RuntimeError("db down"))
        sub = ProviderSettingsSubscriber(
            config=cfg,
            app_state=state,
            settings_service=svc,
        )
        with pytest.raises(RuntimeError, match="db down"):
            await sub.on_settings_changed("providers", "routing_strategy")
        assert state.model_router is old_router
