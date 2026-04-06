"""HTTP request tool -- execute HTTP requests with SSRF prevention.

Supports GET, POST, PUT, and DELETE methods.  URLs are validated
against the ``NetworkPolicy`` before requests are made.  Response
bodies are truncated at ``max_response_bytes`` to prevent memory
exhaustion.
"""

from typing import Any, Final

import httpx

from synthorg.core.enums import ActionType
from synthorg.observability import get_logger
from synthorg.observability.events.web import (
    WEB_REQUEST_FAILED,
    WEB_REQUEST_START,
    WEB_REQUEST_SUCCESS,
    WEB_REQUEST_TIMEOUT,
    WEB_SSRF_BLOCKED,
)
from synthorg.tools.base import ToolExecutionResult
from synthorg.tools.network_validator import (  # noqa: TC001
    DnsValidationOk,
    NetworkPolicy,
)
from synthorg.tools.web.base_web_tool import BaseWebTool

logger = get_logger(__name__)

_ALLOWED_METHODS: Final[frozenset[str]] = frozenset(
    {
        "GET",
        "POST",
        "PUT",
        "DELETE",
    }
)

_PARAMETERS_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "The URL to request",
        },
        "method": {
            "type": "string",
            "enum": ["GET", "POST", "PUT", "DELETE"],
            "description": "HTTP method (default: GET)",
            "default": "GET",
        },
        "headers": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "Optional request headers",
        },
        "body": {
            "type": "string",
            "description": "Optional request body (for POST/PUT)",
        },
        "timeout": {
            "type": "number",
            "description": "Request timeout in seconds",
            "minimum": 0,
            "maximum": 300,
        },
    },
    "required": ["url"],
    "additionalProperties": False,
}


class HttpRequestTool(BaseWebTool):
    """Execute HTTP requests (GET/POST/PUT/DELETE).

    Validates URLs against the network policy before making requests
    to prevent SSRF attacks.  Response bodies are truncated at
    ``max_response_bytes``.

    Examples:
        Make a GET request::

            tool = HttpRequestTool()
            result = await tool.execute(
                arguments={"url": "https://api.example.com/data"}
            )
    """

    def __init__(
        self,
        *,
        network_policy: NetworkPolicy | None = None,
        max_response_bytes: int = 1_048_576,
        request_timeout: float = 30.0,
    ) -> None:
        """Initialize the HTTP request tool.

        Args:
            network_policy: Network policy for SSRF prevention.
            max_response_bytes: Maximum response body size to return.
            request_timeout: Default request timeout in seconds.
        """
        super().__init__(
            name="http_request",
            description=(
                "Execute HTTP requests (GET, POST, PUT, DELETE). "
                "URLs are validated against SSRF policies."
            ),
            parameters_schema=dict(_PARAMETERS_SCHEMA),
            action_type=ActionType.COMMS_EXTERNAL,
            network_policy=network_policy,
            request_timeout=request_timeout,
        )
        self._max_response_bytes = max_response_bytes

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute an HTTP request.

        Args:
            arguments: Must contain ``url``; optionally ``method``,
                ``headers``, ``body``, ``timeout``.

        Returns:
            A ``ToolExecutionResult`` with the response body or error.
        """
        url: str = arguments["url"]
        method: str = arguments.get("method", "GET").upper()
        headers: dict[str, str] = arguments.get("headers") or {}
        body: str | None = arguments.get("body")
        timeout: float = arguments.get("timeout") or self._request_timeout

        if method not in _ALLOWED_METHODS:
            return ToolExecutionResult(
                content=f"Unsupported HTTP method: {method!r}",
                is_error=True,
            )

        # SSRF validation
        validation = await self._validate_url(url)
        if isinstance(validation, str):
            logger.warning(WEB_SSRF_BLOCKED, url=url, reason=validation)
            return ToolExecutionResult(
                content=f"URL blocked: {validation}",
                is_error=True,
            )

        logger.info(
            WEB_REQUEST_START,
            method=method,
            url=url,
            has_body=body is not None,
        )

        return await self._perform_request(
            url, method, headers, body, timeout, validation
        )

    async def _perform_request(  # noqa: PLR0913
        self,
        url: str,
        method: str,
        headers: dict[str, str],
        body: str | None,
        timeout: float,  # noqa: ASYNC109  -- passed to httpx, not asyncio
        validation: DnsValidationOk,  # noqa: ARG002  -- reserved for IP pinning
    ) -> ToolExecutionResult:
        """Perform the HTTP request after validation.

        Args:
            url: Validated URL.
            method: HTTP method.
            headers: Request headers.
            body: Request body.
            timeout: Request timeout.
            validation: DNS validation result (unused for now,
                reserved for IP pinning).

        Returns:
            A ``ToolExecutionResult`` with the response.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                    timeout=timeout,
                    follow_redirects=True,
                )
        except httpx.TimeoutException:
            logger.warning(WEB_REQUEST_TIMEOUT, url=url, timeout=timeout)
            return ToolExecutionResult(
                content=f"Request timed out after {timeout}s: {url}",
                is_error=True,
            )
        except httpx.HTTPError as exc:
            logger.warning(WEB_REQUEST_FAILED, url=url, error=str(exc))
            return ToolExecutionResult(
                content=f"HTTP request failed: {exc}",
                is_error=True,
            )

        content = response.text
        truncated = False
        if len(content) > self._max_response_bytes:
            content = content[: self._max_response_bytes]
            truncated = True

        logger.info(
            WEB_REQUEST_SUCCESS,
            url=url,
            method=method,
            status_code=response.status_code,
            content_length=len(content),
            truncated=truncated,
        )

        if truncated:
            content += (
                f"\n\n[Truncated: response exceeded {self._max_response_bytes:,} bytes]"
            )

        return ToolExecutionResult(
            content=content,
            metadata={
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "truncated": truncated,
                "url": url,
            },
        )
