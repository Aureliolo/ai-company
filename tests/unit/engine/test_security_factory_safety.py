"""Tests for safety classifier and uncertainty checker wiring in the factory."""

from unittest.mock import MagicMock

import pytest

from synthorg.security.config import (
    SafetyClassifierConfig,
    SecurityConfig,
    UncertaintyCheckConfig,
)


def _make_provider_infra() -> tuple[MagicMock, dict[str, MagicMock], MagicMock]:
    """Build mock provider registry, configs, and resolver."""
    registry = MagicMock()
    registry.list_providers = MagicMock(return_value=("p-a", "p-b"))

    config_a = MagicMock()
    config_a.family = "family-a"
    config_a.models = (MagicMock(id="m-a-001", alias="small"),)
    config_b = MagicMock()
    config_b.family = "family-b"
    config_b.models = (MagicMock(id="m-b-001", alias="small"),)
    provider_configs = {"p-a": config_a, "p-b": config_b}

    resolver = MagicMock()
    return registry, provider_configs, resolver


@pytest.mark.unit
class TestFactorySafetyClassifierWiring:
    """Factory wires SafetyClassifier when config enabled + providers."""

    def test_wired_when_enabled_and_providers_available(self) -> None:
        from synthorg.engine._security_factory import (
            make_security_interceptor,
        )
        from synthorg.security.audit import AuditLog

        registry, configs, resolver = _make_provider_infra()
        cfg = SecurityConfig(
            safety_classifier=SafetyClassifierConfig(enabled=True),
        )

        svc = make_security_interceptor(
            cfg,
            AuditLog(),
            provider_registry=registry,
            provider_configs=configs,
            model_resolver=resolver,
        )

        assert svc is not None
        assert svc._safety_classifier is not None  # type: ignore[attr-defined]

    def test_not_wired_when_disabled(self) -> None:
        from synthorg.engine._security_factory import (
            make_security_interceptor,
        )
        from synthorg.security.audit import AuditLog

        registry, configs, resolver = _make_provider_infra()
        cfg = SecurityConfig(
            safety_classifier=SafetyClassifierConfig(enabled=False),
        )

        svc = make_security_interceptor(
            cfg,
            AuditLog(),
            provider_registry=registry,
            provider_configs=configs,
            model_resolver=resolver,
        )

        assert svc is not None
        assert svc._safety_classifier is None  # type: ignore[attr-defined]

    def test_not_wired_when_no_providers(self) -> None:
        from synthorg.engine._security_factory import (
            make_security_interceptor,
        )
        from synthorg.security.audit import AuditLog

        cfg = SecurityConfig(
            safety_classifier=SafetyClassifierConfig(enabled=True),
        )

        svc = make_security_interceptor(cfg, AuditLog())

        assert svc is not None
        assert svc._safety_classifier is None  # type: ignore[attr-defined]


@pytest.mark.unit
class TestFactoryUncertaintyCheckerWiring:
    """Factory wires UncertaintyChecker when config + providers + resolver."""

    def test_wired_when_enabled_and_all_deps(self) -> None:
        from synthorg.engine._security_factory import (
            make_security_interceptor,
        )
        from synthorg.security.audit import AuditLog

        registry, configs, resolver = _make_provider_infra()
        cfg = SecurityConfig(
            uncertainty_check=UncertaintyCheckConfig(
                enabled=True,
                model_ref="small",
            ),
        )

        svc = make_security_interceptor(
            cfg,
            AuditLog(),
            provider_registry=registry,
            provider_configs=configs,
            model_resolver=resolver,
        )

        assert svc is not None
        assert svc._uncertainty_checker is not None  # type: ignore[attr-defined]

    def test_not_wired_when_no_resolver(self) -> None:
        from synthorg.engine._security_factory import (
            make_security_interceptor,
        )
        from synthorg.security.audit import AuditLog

        registry, configs, _ = _make_provider_infra()
        cfg = SecurityConfig(
            uncertainty_check=UncertaintyCheckConfig(
                enabled=True,
                model_ref="small",
            ),
        )

        svc = make_security_interceptor(
            cfg,
            AuditLog(),
            provider_registry=registry,
            provider_configs=configs,
            # model_resolver not provided
        )

        assert svc is not None
        assert svc._uncertainty_checker is None  # type: ignore[attr-defined]
