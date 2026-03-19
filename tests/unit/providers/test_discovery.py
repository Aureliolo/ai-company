"""Tests for provider model auto-discovery."""

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from synthorg.providers.discovery import discover_models

if TYPE_CHECKING:
    pass

pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]


def _mock_response(json_data: Any, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://test"),
    )


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
            client = AsyncMock()
            client.get.return_value = response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

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
            client = AsyncMock()
            client.get.return_value = response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert result == ()

    async def test_connection_refused(self) -> None:
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get.side_effect = httpx.ConnectError("refused")
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert result == ()

    async def test_timeout(self) -> None:
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get.side_effect = httpx.ReadTimeout("timeout")
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert result == ()

    async def test_unexpected_structure(self) -> None:
        response = _mock_response({"unexpected": "data"})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get.return_value = response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await discover_models(
                "http://localhost:11434",
                "ollama",
            )

        assert result == ()

    async def test_uses_ollama_endpoint(self) -> None:
        response = _mock_response({"models": []})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get.return_value = response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            await discover_models(
                "http://localhost:11434",
                "ollama",
            )

            client.get.assert_called_once_with(
                "http://localhost:11434/api/tags",
            )


class TestDiscoverOpenAICompatible:
    """Tests for OpenAI-compatible model discovery (LM Studio, vLLM)."""

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
            client = AsyncMock()
            client.get.return_value = response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

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
            client = AsyncMock()
            client.get.return_value = response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            await discover_models(
                "http://localhost:1234/v1",
                "lm-studio",
            )

            client.get.assert_called_once_with(
                "http://localhost:1234/v1/models",
            )

    async def test_unknown_preset_uses_openai_endpoint(self) -> None:
        response = _mock_response({"data": []})
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.get.return_value = response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
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
            client = AsyncMock()
            bad_response = httpx.Response(
                status_code=200,
                content=b"not json",
                request=httpx.Request("GET", "http://test"),
            )
            client.get.return_value = bad_response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await discover_models(
                "http://localhost:1234/v1",
                "lm-studio",
            )

        assert result == ()

    async def test_http_error(self) -> None:
        with patch("synthorg.providers.discovery.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            error_response = httpx.Response(
                status_code=500,
                request=httpx.Request("GET", "http://test"),
            )
            client.get.return_value = error_response
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await discover_models(
                "http://localhost:1234/v1",
                "vllm",
            )

        assert result == ()
