"""PKCE (RFC 7636) utilities for OAuth 2.1 authorization code flows.

Provides code verifier generation and SHA-256 code challenge
computation per the PKCE specification.
"""

import base64
import hashlib
import re
import secrets

from synthorg.integrations.errors import PKCEValidationError

_UNRESERVED_RE = re.compile(r"^[A-Za-z0-9\-._~]+$")
_VERIFIER_LENGTH = 128
_MIN_VERIFIER_LENGTH = 43
_MAX_VERIFIER_LENGTH = 128


def generate_code_verifier() -> str:
    """Generate a PKCE code verifier.

    Returns a 128-character string using only unreserved characters
    (``[A-Za-z0-9-._~]``) as required by RFC 7636 section 4.1.

    Returns:
        A random code verifier string.
    """
    raw = secrets.token_urlsafe(_VERIFIER_LENGTH)
    return raw[:_VERIFIER_LENGTH]


def generate_code_challenge(verifier: str) -> str:
    """Compute a PKCE S256 code challenge from a verifier.

    Args:
        verifier: A valid PKCE code verifier.

    Returns:
        Base64url-encoded SHA-256 digest (no padding).

    Raises:
        PKCEValidationError: If the verifier is invalid.
    """
    validate_code_verifier(verifier)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def validate_code_verifier(verifier: str) -> None:
    """Validate a PKCE code verifier.

    Args:
        verifier: The verifier to validate.

    Raises:
        PKCEValidationError: If the verifier does not meet RFC 7636
            requirements.
    """
    length = len(verifier)
    if length < _MIN_VERIFIER_LENGTH or length > _MAX_VERIFIER_LENGTH:
        msg = (
            f"Code verifier must be {_MIN_VERIFIER_LENGTH}-"
            f"{_MAX_VERIFIER_LENGTH} characters, got {length}"
        )
        raise PKCEValidationError(msg)
    if not _UNRESERVED_RE.match(verifier):
        msg = "Code verifier contains invalid characters"
        raise PKCEValidationError(msg)


def validate_code_challenge(verifier: str, challenge: str) -> None:
    """Validate a PKCE code challenge against its verifier.

    Args:
        verifier: The original code verifier.
        challenge: The challenge to validate.

    Raises:
        PKCEValidationError: If the challenge does not match.
    """
    expected = generate_code_challenge(verifier)
    if not secrets.compare_digest(expected, challenge):
        msg = "Code challenge does not match verifier"
        raise PKCEValidationError(msg)
