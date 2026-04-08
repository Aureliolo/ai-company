"""Tests for communication tool configuration models."""

import pytest
from pydantic import ValidationError

from synthorg.tools.communication.config import (
    CommunicationToolsConfig,
    EmailConfig,
)


@pytest.mark.unit
class TestEmailConfig:
    """Tests for EmailConfig."""

    def test_required_fields(self) -> None:
        config = EmailConfig(
            host="smtp.example.com",
            from_address="test@example.com",
        )
        assert config.host == "smtp.example.com"
        assert config.port == 587
        assert config.from_address == "test@example.com"
        assert config.use_tls is True
        assert config.username is None
        assert config.password is None

    def test_frozen(self) -> None:
        config = EmailConfig(
            host="smtp.example.com",
            from_address="test@example.com",
        )
        with pytest.raises(ValidationError):
            config.host = "other"  # type: ignore[misc]

    def test_port_range(self) -> None:
        with pytest.raises(ValidationError):
            EmailConfig(
                host="smtp.example.com",
                from_address="test@example.com",
                port=0,
            )
        with pytest.raises(ValidationError):
            EmailConfig(
                host="smtp.example.com",
                from_address="test@example.com",
                port=70000,
            )

    def test_blank_host_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EmailConfig(host="  ", from_address="test@example.com")

    def test_password_not_in_repr(self) -> None:
        config = EmailConfig(
            host="smtp.example.com",
            from_address="test@example.com",
            username="user",
            password="secret",
        )
        assert "secret" not in repr(config)

    def test_partial_credentials_rejected(self) -> None:
        with pytest.raises(ValidationError, match="username and password"):
            EmailConfig(
                host="smtp.example.com",
                from_address="test@example.com",
                username="user",
                # password missing
            )

    def test_partial_credentials_password_only_rejected(self) -> None:
        with pytest.raises(ValidationError, match="username and password"):
            EmailConfig(
                host="smtp.example.com",
                from_address="test@example.com",
                password="secret",
                # username missing
            )

    def test_both_credentials_accepted(self) -> None:
        config = EmailConfig(
            host="smtp.example.com",
            from_address="test@example.com",
            username="user",
            password="secret",
        )
        assert config.username == "user"

    def test_no_credentials_accepted(self) -> None:
        config = EmailConfig(
            host="smtp.example.com",
            from_address="test@example.com",
        )
        assert config.username is None
        assert config.password is None

    def test_tls_mutual_exclusivity(self) -> None:
        with pytest.raises(ValidationError, match="mutually exclusive"):
            EmailConfig(
                host="smtp.example.com",
                from_address="test@example.com",
                use_tls=True,
                use_implicit_tls=True,
            )


@pytest.mark.unit
class TestCommunicationToolsConfig:
    """Tests for CommunicationToolsConfig."""

    def test_default_values(self) -> None:
        config = CommunicationToolsConfig()
        assert config.email is None
        assert config.max_recipients == 100

    def test_frozen(self) -> None:
        config = CommunicationToolsConfig()
        with pytest.raises(ValidationError):
            config.max_recipients = 50  # type: ignore[misc]

    def test_with_email(self) -> None:
        email = EmailConfig(
            host="smtp.example.com",
            from_address="test@example.com",
        )
        config = CommunicationToolsConfig(email=email)
        assert config.email is not None
        assert config.email.host == "smtp.example.com"

    def test_max_recipients_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            CommunicationToolsConfig(max_recipients=0)

    def test_max_recipients_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            CommunicationToolsConfig(max_recipients=1001)

    def test_rejects_nan(self) -> None:
        with pytest.raises(ValidationError):
            CommunicationToolsConfig(max_recipients=float("nan"))  # type: ignore[arg-type]
