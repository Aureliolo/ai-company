"""Tests for JWT secret resolution."""

from unittest.mock import patch

import pytest

from synthorg.api.auth.secret import resolve_jwt_secret


@pytest.mark.unit
class TestResolveJwtSecret:
    def test_env_var_returns_secret(self) -> None:
        secret = "env-secret-that-is-at-least-32-characters!!"
        with patch.dict("os.environ", {"SYNTHORG_JWT_SECRET": secret}):
            result = resolve_jwt_secret()

        assert result == secret

    def test_env_var_whitespace_stripped(self) -> None:
        secret = "  env-secret-that-is-at-least-32-characters!!  "
        with patch.dict("os.environ", {"SYNTHORG_JWT_SECRET": secret}):
            result = resolve_jwt_secret()

        assert result == secret.strip()

    def test_env_var_too_short_raises(self) -> None:
        with (
            patch.dict("os.environ", {"SYNTHORG_JWT_SECRET": "short"}),
            pytest.raises(ValueError, match="at least 32 characters"),
        ):
            resolve_jwt_secret()

    def test_missing_env_var_raises(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(ValueError, match="is not set"),
        ):
            resolve_jwt_secret()

    def test_empty_env_var_raises(self) -> None:
        with (
            patch.dict("os.environ", {"SYNTHORG_JWT_SECRET": ""}),
            pytest.raises(ValueError, match="is not set"),
        ):
            resolve_jwt_secret()

    def test_whitespace_only_env_var_raises(self) -> None:
        with (
            patch.dict("os.environ", {"SYNTHORG_JWT_SECRET": "   "}),
            pytest.raises(ValueError, match="is not set"),
        ):
            resolve_jwt_secret()
