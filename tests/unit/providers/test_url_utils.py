"""Tests for provider URL utilities."""

import pytest

from synthorg.providers.url_utils import is_self_url

pytestmark = pytest.mark.unit


class TestIsSelfUrl:
    """Tests for is_self_url self-connection detection."""

    @pytest.mark.parametrize(
        ("url", "backend_port", "expected"),
        [
            pytest.param(
                "http://localhost:8000/v1",
                8000,
                True,
                id="localhost-match",
            ),
            pytest.param(
                "http://127.0.0.1:8000/v1",
                8000,
                True,
                id="loopback-match",
            ),
            pytest.param(
                "http://host.docker.internal:8000/v1",
                8000,
                True,
                id="docker-internal-match",
            ),
            pytest.param(
                "http://172.17.0.1:8000/v1",
                8000,
                True,
                id="docker-bridge-match",
            ),
            pytest.param(
                "http://0.0.0.0:8000/v1",
                8000,
                True,
                id="wildcard-match",
            ),
            pytest.param(
                "http://[::1]:8000/v1",
                8000,
                True,
                id="ipv6-loopback-match",
            ),
            pytest.param(
                "http://localhost:3001/v1",
                3001,
                True,
                id="custom-port-match",
            ),
            pytest.param(
                "http://localhost:5000/v1",
                8000,
                False,
                id="different-port",
            ),
            pytest.param(
                "http://example.com:8000/v1",
                8000,
                False,
                id="remote-host-not-self",
            ),
            pytest.param(
                "http://localhost/v1",
                8000,
                False,
                id="no-port",
            ),
            pytest.param(
                "not-a-url",
                8000,
                False,
                id="malformed-url",
            ),
            pytest.param(
                "http://localhost:abc/v1",
                8000,
                False,
                id="non-numeric-port",
            ),
            pytest.param(
                "http://localhost.:8000/v1",
                8000,
                True,
                id="trailing-dot-normalized",
            ),
            pytest.param(
                "http://LOCALHOST:8000/v1",
                8000,
                True,
                id="uppercase-normalized",
            ),
            pytest.param(
                "http://127.0.0.2:8000/v1",
                8000,
                True,
                id="loopback-range-127.0.0.2",
            ),
            pytest.param(
                "http://127.255.255.1:8000/v1",
                8000,
                True,
                id="loopback-range-high",
            ),
        ],
    )
    def test_detection(
        self,
        url: str,
        backend_port: int,
        *,
        expected: bool,
    ) -> None:
        """Correctly identifies URLs pointing at the backend itself."""
        assert is_self_url(url, backend_port=backend_port) is expected
