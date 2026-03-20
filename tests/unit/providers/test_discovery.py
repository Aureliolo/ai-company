"""Tests for provider model auto-discovery."""

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from synthorg.providers.discovery import (
    _validate_discovery_url,
    discover_models,
)

pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]


def _mock_response(json_data: Any, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://test"),
    )


def _mock_client(
    response: httpx.Response | None = None,
    *,
    side_effect: Exception | None = None,
) -> AsyncMock:
    """Build a mock httpx.AsyncClient with async context manager support."""
    client = AsyncMock()
    if side_effect:
        client.get.side_effect = side_effect
    else:
        client.get.return_value = response
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestDiscoverOllama:
    """Tests for Ollama model discovery."""

    async def test_parses_response(self) -> None:
        response = _mock_response(
            {
                "models": [
                    {"name": "llama3.2:latest"},
                    {"name": "codellama:7b"},
                ],
            }
        )
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert len(result) == 2
        assert result[0].id == "ollama/llama3.2:latest"
        assert result[1].id == "ollama/codellama:7b"

    async def test_empty_models_list(self) -> None:
        response = _mock_response({"models": []})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert result == ()

    async def test_connection_refused(self) -> None:
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(
                side_effect=httpx.ConnectError("refused"),
            )

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert result == ()

    async def test_timeout(self) -> None:
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(
                side_effect=httpx.ReadTimeout("timeout"),
            )

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert result == ()

    async def test_unexpected_structure(self) -> None:
        response = _mock_response({"unexpected": "data"})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert result == ()

    async def test_uses_ollama_endpoint(self) -> None:
        response = _mock_response({"models": []})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = _mock_client(response)
            mock_cls.return_value = client

            await discover_models(
                "http://localhost:11434",
                "ollama",
            )

            client.get.assert_called_once_with(
                "http://localhost:11434/api/tags",
            )

    async def test_trailing_slash_normalized(self) -> None:
        response = _mock_response({"models": []})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = _mock_client(response)
            mock_cls.return_value = client

            await discover_models(
                "http://localhost:11434/",
                "ollama",
            )

            client.get.assert_called_once_with(
                "http://localhost:11434/api/tags",
            )

    async def test_malformed_entries_skipped(self) -> None:
        """Valid models returned even when some entries are malformed."""
        response = _mock_response(
            {
                "models": [
                    {"name": "valid-model"},
                    "not-a-dict",
                    {"name": ""},
                    {"no-name-key": True},
                    {"name": "also-valid"},
                ],
            }
        )
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert len(result) == 2
        assert result[0].id == "ollama/valid-model"
        assert result[1].id == "ollama/also-valid"


class TestDiscoverStandardApi:
    """Tests for standard /models endpoint discovery (LM Studio, vLLM)."""

    async def test_parses_response(self) -> None:
        response = _mock_response(
            {
                "data": [
                    {"id": "model-a"},
                    {"id": "model-b"},
                ],
            }
        )
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)

            result = await discover_models(
                "http://localhost:1234/v1",
                "lm-studio",
            )

        assert len(result) == 2
        assert result[0].id == "model-a"
        assert result[1].id == "model-b"

    async def test_uses_models_endpoint(self) -> None:
        response = _mock_response({"data": []})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = _mock_client(response)
            mock_cls.return_value = client

            await discover_models(
                "http://localhost:1234/v1",
                "lm-studio",
            )

            client.get.assert_called_once_with(
                "http://localhost:1234/v1/models",
            )

    async def test_unknown_preset_uses_standard_endpoint(self) -> None:
        response = _mock_response({"data": []})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = _mock_client(response)
            mock_cls.return_value = client

            await discover_models(
                "http://localhost:9999",
                None,
            )

            client.get.assert_called_once_with(
                "http://localhost:9999/models",
            )

    async def test_malformed_json(self) -> None:
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            bad_response = httpx.Response(
                status_code=200,
                content=b"not json",
                request=httpx.Request("GET", "http://test"),
            )
            mock_cls.return_value = _mock_client(bad_response)

            result = await discover_models(
                "http://localhost:1234/v1",
                "lm-studio",
            )

        assert result == ()

    async def test_http_error(self) -> None:
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            error_response = httpx.Response(
                status_code=500,
                request=httpx.Request("GET", "http://test"),
            )
            mock_cls.return_value = _mock_client(error_response)

            result = await discover_models(
                "http://localhost:1234/v1",
                "vllm",
            )

        assert result == ()

    async def test_malformed_entries_skipped(self) -> None:
        """Valid models returned even when some entries are malformed."""
        response = _mock_response(
            {
                "data": [
                    {"id": "valid"},
                    42,
                    {"id": "  "},
                    {"id": "also-valid"},
                ],
            }
        )
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)

            result = await discover_models(
                "http://localhost:1234/v1",
                "lm-studio",
            )

        assert len(result) == 2
        assert result[0].id == "valid"
        assert result[1].id == "also-valid"

    async def test_non_dict_json_returns_empty(self) -> None:
        """JSON array response (not a dict) returns empty tuple."""
        response = _mock_response([{"id": "model-a"}])
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _mock_client(response)

            result = await discover_models(
                "http://localhost:1234/v1",
                "lm-studio",
            )

        assert result == ()


class TestValidateDiscoveryUrl:
    """Tests for SSRF URL validation."""

    @pytest.mark.parametrize(
        ("url", "expected_safe"),
        [
            ("http://localhost:11434", True),
            ("https://api.example.com/v1", True),
            ("http://192.168.1.1:11434", False),
            ("http://10.0.0.1:8000", False),
            ("http://127.0.0.1:11434", False),
            ("http://169.254.169.254/latest", False),
            ("ftp://example.com", False),
            ("file:///etc/passwd", False),
            ("http://172.16.0.1:8000", False),
        ],
    )
    def test_url_validation(self, url: str, *, expected_safe: bool) -> None:
        result = _validate_discovery_url(url)
        if expected_safe:
            assert result is None, f"Expected {url} to be safe, got error: {result}"
        else:
            assert result is not None, f"Expected {url} to be blocked"

    async def test_blocked_url_returns_empty(self) -> None:
        """SSRF-blocked URL returns empty tuple without making HTTP call."""
        result = await discover_models(
            "http://169.254.169.254/latest",
            "ollama",
        )
        assert result == ()


class TestInferPresetHint:
    """Tests for _infer_preset_hint port-based heuristic."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("http://localhost:11434", "ollama"),
            ("http://localhost:1234/v1", "lm-studio"),
            ("http://localhost:8000", "vllm"),
            ("http://localhost:9999", None),
            ("http://example.com", None),
            ("http://localhost:11434/api", "ollama"),
        ],
    )
    def test_port_mapping(self, url: str, expected: str | None) -> None:
        from synthorg.providers.management.service import _infer_preset_hint

        assert _infer_preset_hint(url) == expected
