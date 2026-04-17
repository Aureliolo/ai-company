"""Tests for `synthorg.notifications.factory`.

Focuses on per-adapter config validation in the factory's private
`_create_*_sink` helpers; `build_notification_dispatcher` is covered
transitively via the integration paths that wire it into the engine.
"""

import pytest

from synthorg.notifications.factory import _create_email_sink

pytestmark = pytest.mark.unit


def _base_email_params() -> dict[str, str]:
    """Return a minimal valid email sink params dict.

    Kept as a factory so individual tests can mutate a copy without
    cross-test leakage.
    """
    return {
        "host": "smtp.example.test",
        "to_addrs": "alerts@example.test",
        "from_addr": "synthorg@example.test",
    }


class TestCreateEmailSink:
    """`_create_email_sink` parameter validation."""

    def test_valid_params_returns_sink(self) -> None:
        sink = _create_email_sink(_base_email_params())
        assert sink is not None

    def test_missing_host_returns_none(self) -> None:
        params = _base_email_params()
        del params["host"]
        assert _create_email_sink(params) is None

    def test_empty_host_returns_none(self) -> None:
        params = _base_email_params()
        params["host"] = ""
        assert _create_email_sink(params) is None

    def test_missing_to_addrs_returns_none(self) -> None:
        params = _base_email_params()
        del params["to_addrs"]
        assert _create_email_sink(params) is None

    def test_empty_to_addrs_returns_none(self) -> None:
        params = _base_email_params()
        params["to_addrs"] = ""
        assert _create_email_sink(params) is None

    def test_invalid_port_returns_none(self) -> None:
        params = _base_email_params()
        params["port"] = "not-a-port"
        assert _create_email_sink(params) is None

    def test_missing_from_addr_returns_none(self) -> None:
        """Email sink must not silently default ``from_addr``.

        Production SMTP relays reject messages sent from ambiguous
        hostnames; defaulting to ``synthorg@localhost`` produced a
        footgun where local development worked and prod bounced. An
        explicit ``from_addr`` is now a hard requirement.
        """
        params = _base_email_params()
        del params["from_addr"]
        assert _create_email_sink(params) is None

    def test_empty_from_addr_returns_none(self) -> None:
        params = _base_email_params()
        params["from_addr"] = ""
        assert _create_email_sink(params) is None

    def test_whitespace_from_addr_returns_none(self) -> None:
        params = _base_email_params()
        params["from_addr"] = "   "
        assert _create_email_sink(params) is None

    @pytest.mark.parametrize(
        "injected",
        [
            "ops@example.test\r\nBcc: attacker@evil.test",
            "ops@example.test\nBcc: attacker@evil.test",
            "ops@example.test\rBcc: attacker@evil.test",
        ],
    )
    def test_from_addr_with_crlf_is_rejected(self, injected: str) -> None:
        """CR/LF in ``from_addr`` would let a config-edit-capable
        operator inject arbitrary extra headers (Bcc, Reply-To, ...)
        because the stdlib ``email`` package does not sanitize
        header values.
        """
        params = _base_email_params()
        params["from_addr"] = injected
        assert _create_email_sink(params) is None

    def test_from_addr_trimmed_and_accepted(self) -> None:
        """Leading / trailing whitespace around ``from_addr`` is
        tolerated but the underlying value must be non-empty."""
        params = _base_email_params()
        params["from_addr"] = "  ops@example.test  "
        sink = _create_email_sink(params)
        assert sink is not None
