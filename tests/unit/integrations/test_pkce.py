"""Unit tests for PKCE utilities."""

import pytest

from synthorg.integrations.errors import PKCEValidationError
from synthorg.integrations.oauth.pkce import (
    generate_code_challenge,
    generate_code_verifier,
    validate_code_challenge,
    validate_code_verifier,
)


@pytest.mark.unit
class TestCodeVerifier:
    """Tests for code verifier generation and validation."""

    def test_generate_returns_128_chars(self) -> None:
        verifier = generate_code_verifier()
        assert len(verifier) == 128

    def test_generate_uses_unreserved_chars(self) -> None:
        import re

        verifier = generate_code_verifier()
        assert re.match(r"^[A-Za-z0-9\-._~]+$", verifier)

    def test_generate_returns_unique_values(self) -> None:
        v1 = generate_code_verifier()
        v2 = generate_code_verifier()
        assert v1 != v2

    def test_validate_accepts_valid_verifier(self) -> None:
        verifier = generate_code_verifier()
        validate_code_verifier(verifier)

    @pytest.mark.parametrize("size", [42, 129])
    def test_validate_rejects_invalid_lengths(self, size: int) -> None:
        with pytest.raises(PKCEValidationError, match="43-128"):
            validate_code_verifier("a" * size)

    def test_validate_rejects_invalid_chars(self) -> None:
        with pytest.raises(PKCEValidationError, match="invalid"):
            validate_code_verifier("a" * 43 + " ")


@pytest.mark.unit
class TestCodeChallenge:
    """Tests for code challenge generation and validation."""

    def test_challenge_is_base64url(self) -> None:
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        assert "+" not in challenge
        assert "/" not in challenge
        assert "=" not in challenge

    def test_challenge_is_deterministic(self) -> None:
        verifier = generate_code_verifier()
        c1 = generate_code_challenge(verifier)
        c2 = generate_code_challenge(verifier)
        assert c1 == c2

    def test_validate_challenge_succeeds(self) -> None:
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        validate_code_challenge(verifier, challenge)

    def test_validate_challenge_rejects_mismatch(self) -> None:
        verifier = generate_code_verifier()
        with pytest.raises(PKCEValidationError, match="does not match"):
            validate_code_challenge(verifier, "wrong")
