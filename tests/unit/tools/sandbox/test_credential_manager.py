"""Tests for SandboxCredentialManager."""

import pytest

from synthorg.tools.sandbox.credential_manager import SandboxCredentialManager

pytestmark = pytest.mark.unit


class TestSanitizeEnv:
    """Tests for SandboxCredentialManager.sanitize_env()."""

    def test_strips_api_key_vars(self) -> None:
        mgr = SandboxCredentialManager()
        env = {"EXAMPLE_API_KEY": "sk-secret", "PATH": "/usr/bin"}
        result = mgr.sanitize_env(env)
        assert "EXAMPLE_API_KEY" not in result
        assert result["PATH"] == "/usr/bin"

    def test_strips_secret_vars(self) -> None:
        mgr = SandboxCredentialManager()
        env = {"MY_SECRET": "hidden", "HOME": "/home/user"}
        result = mgr.sanitize_env(env)
        assert "MY_SECRET" not in result
        assert result["HOME"] == "/home/user"

    def test_strips_token_vars(self) -> None:
        mgr = SandboxCredentialManager()
        env = {"AUTH_TOKEN": "tok-123", "LANG": "en_US.UTF-8"}
        result = mgr.sanitize_env(env)
        assert "AUTH_TOKEN" not in result
        assert result["LANG"] == "en_US.UTF-8"

    def test_strips_password_vars(self) -> None:
        mgr = SandboxCredentialManager()
        env = {"DB_PASSWORD": "pass123"}
        result = mgr.sanitize_env(env)
        assert "DB_PASSWORD" not in result

    def test_strips_credential_vars(self) -> None:
        mgr = SandboxCredentialManager()
        env = {"SOME_CREDENTIAL": "cred"}
        result = mgr.sanitize_env(env)
        assert "SOME_CREDENTIAL" not in result

    def test_strips_private_key_vars(self) -> None:
        mgr = SandboxCredentialManager()
        env = {"SSH_PRIVATE_KEY": "key-data"}
        result = mgr.sanitize_env(env)
        assert "SSH_PRIVATE_KEY" not in result

    def test_keeps_safe_vars(self) -> None:
        mgr = SandboxCredentialManager()
        env = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "LANG": "en_US.UTF-8",
            "TZ": "UTC",
            "PYTHONPATH": "/app",
        }
        result = mgr.sanitize_env(env)
        assert result == env

    def test_empty_env_returns_empty(self) -> None:
        mgr = SandboxCredentialManager()
        result = mgr.sanitize_env({})
        assert result == {}

    def test_case_insensitive_matching(self) -> None:
        mgr = SandboxCredentialManager()
        env = {"test_provider_api_key": "sk-secret", "Api_Key": "val"}
        result = mgr.sanitize_env(env)
        assert "test_provider_api_key" not in result
        assert "Api_Key" not in result

    def test_returns_new_dict(self) -> None:
        mgr = SandboxCredentialManager()
        env = {"PATH": "/usr/bin"}
        result = mgr.sanitize_env(env)
        assert result is not env

    @pytest.mark.parametrize(
        ("key", "description"),
        [
            ("CLOUD_ACCESS_KEY", "access_key pattern"),
            ("APP_SIGNING_KEY", "signing_key pattern"),
            ("DATA_ENCRYPTION_KEY", "encryption_key pattern"),
            ("GPG_PASSPHRASE", "passphrase pattern"),
            ("POSTGRES_CONNECTION_STRING", "connection_string pattern"),
            ("BACKEND_DATABASE_URL", "database_url pattern"),
            ("auth", "auth word boundary pattern"),
            ("dsn", "dsn word boundary pattern"),
        ],
    )
    def test_strips_remaining_credential_patterns(
        self,
        key: str,
        description: str,
    ) -> None:
        """Cover all 14 credential regex families ({description})."""
        mgr = SandboxCredentialManager()
        env = {key: "sensitive-value", "PATH": "/usr/bin"}
        result = mgr.sanitize_env(env)
        assert key not in result, f"{key} ({description}) should be stripped"
        assert result["PATH"] == "/usr/bin"

    def test_reports_stripped_keys(self) -> None:
        mgr = SandboxCredentialManager()
        env = {
            "EXAMPLE_API_KEY": "sk-secret",
            "MY_SECRET": "hidden",
            "PATH": "/usr/bin",
        }
        result, stripped = mgr.sanitize_env_with_report(env)
        assert "EXAMPLE_API_KEY" in stripped
        assert "MY_SECRET" in stripped
        assert "PATH" not in stripped
        assert len(result) == 1
