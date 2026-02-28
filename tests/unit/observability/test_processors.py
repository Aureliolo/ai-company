"""Tests for custom structlog processors."""

import pytest

from ai_company.observability.processors import sanitize_sensitive_fields

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestSanitizeSensitiveFields:
    """Tests for the sanitize_sensitive_fields processor."""

    def test_redacts_password(self) -> None:
        event = {"event": "login", "password": "s3cret"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["password"] == "**REDACTED**"
        assert result["event"] == "login"

    def test_redacts_api_key(self) -> None:
        event = {"api_key": "abc123", "event": "request"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["api_key"] == "**REDACTED**"

    def test_redacts_api_secret(self) -> None:
        event = {"api_secret": "xyz", "event": "call"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["api_secret"] == "**REDACTED**"

    def test_redacts_token(self) -> None:
        event = {"auth_token": "jwt.stuff", "event": "auth"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["auth_token"] == "**REDACTED**"

    def test_redacts_authorization(self) -> None:
        event = {"authorization": "Bearer xyz", "event": "header"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["authorization"] == "**REDACTED**"

    def test_redacts_secret(self) -> None:
        event = {"client_secret": "shh", "event": "oauth"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["client_secret"] == "**REDACTED**"

    def test_redacts_credential(self) -> None:
        event = {"credential": "data", "event": "verify"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["credential"] == "**REDACTED**"

    def test_case_insensitive(self) -> None:
        event = {"PASSWORD": "upper", "Api_Key": "mixed"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["PASSWORD"] == "**REDACTED**"
        assert result["Api_Key"] == "**REDACTED**"

    def test_preserves_non_sensitive_fields(self) -> None:
        event = {"event": "hello", "user": "alice", "count": 42}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result == event

    def test_returns_new_dict(self) -> None:
        event = {"password": "secret", "event": "test"}
        result = sanitize_sensitive_fields(None, "info", event)
        assert result is not event
        assert event["password"] == "secret"

    def test_empty_event_dict(self) -> None:
        result = sanitize_sensitive_fields(None, "info", {})
        assert result == {}

    def test_multiple_sensitive_fields(self) -> None:
        event = {
            "password": "p",
            "api_key": "k",
            "token": "t",
            "event": "multi",
        }
        result = sanitize_sensitive_fields(None, "info", event)
        assert result["password"] == "**REDACTED**"
        assert result["api_key"] == "**REDACTED**"
        assert result["token"] == "**REDACTED**"
        assert result["event"] == "multi"
