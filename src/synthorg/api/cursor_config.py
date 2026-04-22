"""Pagination cursor configuration.

Carries the HMAC signing key used by :mod:`synthorg.api.cursor`. The key
is loaded from the ``api.pagination.cursor_secret`` setting (masked in
logs) with fallback to ``SYNTHORG_PAGINATION_CURSOR_SECRET`` for
containerised deployments that prefer secret injection via env vars.

When no key is configured, the cursor module generates an ephemeral
per-process key and logs a WARNING once at boot. Ephemeral keys make
pagination tokens invalid across restarts -- operators must set the
key in any deployment that expects stable cursors.
"""

import os

from pydantic import BaseModel, ConfigDict, Field

_ENV_VAR = "SYNTHORG_PAGINATION_CURSOR_SECRET"


class CursorConfig(BaseModel):
    """Pagination cursor configuration.

    Attributes:
        secret: HMAC key for signing pagination cursors. ``None`` means
            an ephemeral random key is generated at process start;
            tokens become invalid across restarts.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    secret: str | None = Field(
        default=None,
        description=(
            "HMAC key for signing pagination cursors. "
            "When None, an ephemeral random key is generated at boot "
            "and a WARNING is logged. Environment variable override: "
            f"{_ENV_VAR}."
        ),
    )

    @classmethod
    def from_env(cls) -> CursorConfig:
        """Build from the ``SYNTHORG_PAGINATION_CURSOR_SECRET`` env var."""
        raw = os.environ.get(_ENV_VAR, "").strip()
        return cls(secret=raw or None)
