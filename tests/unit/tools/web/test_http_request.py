"""Unit tests for HttpRequestTool."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from synthorg.tools.network_validator import NetworkPolicy
from synthorg.tools.web.http_request import HttpRequestTool


class TestHttpRequestTool:
    """Tests for HTTP request execution."""

    @pytest.mark.unit
    async def test_get_request_success(self, http_tool: HttpRequestTool) -> None:
        mock_response = httpx.Response(200, text="hello world")
        with patch("synthorg.tools.web.http_request.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.request = AsyncMock(return_value=mock_response)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await http_tool.execute(
                arguments={"url": "http://example.com/api"}
            )

        assert result.is_error is False
        assert "hello world" in result.content
        assert result.metadata["status_code"] == 200

    @pytest.mark.unit
    async def test_post_with_body(self, http_tool: HttpRequestTool) -> None:
        mock_response = httpx.Response(201, text="created")
        with patch("synthorg.tools.web.http_request.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.request = AsyncMock(return_value=mock_response)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await http_tool.execute(
                arguments={
                    "url": "http://example.com/api",
                    "method": "POST",
                    "body": '{"key": "value"}',
                }
            )

        assert result.is_error is False
        assert result.metadata["status_code"] == 201

    @pytest.mark.unit
    async def test_timeout_returns_error(self, http_tool: HttpRequestTool) -> None:
        with patch("synthorg.tools.web.http_request.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.request = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await http_tool.execute(
                arguments={"url": "http://example.com/slow"}
            )

        assert result.is_error is True
        assert "timed out" in result.content.lower()

    @pytest.mark.unit
    async def test_http_error_returns_error(self, http_tool: HttpRequestTool) -> None:
        with patch("synthorg.tools.web.http_request.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.request = AsyncMock(
                side_effect=httpx.ConnectError("connection refused")
            )
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await http_tool.execute(
                arguments={"url": "http://example.com/down"}
            )

        assert result.is_error is True
        assert "failed" in result.content.lower()

    @pytest.mark.unit
    async def test_unsupported_method(self, http_tool: HttpRequestTool) -> None:
        result = await http_tool.execute(
            arguments={"url": "http://x.com", "method": "PATCH"}
        )
        assert result.is_error is True
        assert "unsupported" in result.content.lower()

    @pytest.mark.unit
    async def test_response_truncation(self) -> None:
        tool = HttpRequestTool(
            network_policy=NetworkPolicy(block_private_ips=False),
            max_response_bytes=50,
        )
        mock_response = httpx.Response(200, text="x" * 100)
        with patch("synthorg.tools.web.http_request.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.request = AsyncMock(return_value=mock_response)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client

            result = await tool.execute(arguments={"url": "http://example.com/big"})

        assert result.is_error is False
        assert "truncated" in result.content.lower()
        assert result.metadata["truncated"] is True


class TestSsrfPrevention:
    """Tests for SSRF prevention in HttpRequestTool."""

    @pytest.mark.unit
    async def test_private_ip_blocked(self) -> None:
        tool = HttpRequestTool()
        result = await tool.execute(arguments={"url": "http://127.0.0.1/admin"})
        assert result.is_error is True
        assert "blocked" in result.content.lower()

    @pytest.mark.unit
    async def test_file_scheme_blocked(self) -> None:
        tool = HttpRequestTool()
        result = await tool.execute(arguments={"url": "file:///etc/passwd"})
        assert result.is_error is True
        assert "scheme" in result.content.lower()

    @pytest.mark.unit
    async def test_ftp_scheme_blocked(self) -> None:
        tool = HttpRequestTool()
        result = await tool.execute(arguments={"url": "ftp://files.example.com/data"})
        assert result.is_error is True

    @pytest.mark.unit
    async def test_flag_injection_blocked(self) -> None:
        tool = HttpRequestTool()
        result = await tool.execute(arguments={"url": "-http://evil.com"})
        assert result.is_error is True
