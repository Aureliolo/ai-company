"""Integration test for RFC 9457 OpenAPI schema post-processing.

Exercises :func:`inject_rfc9457_responses` against the real
Litestar-generated schema end-to-end.
"""

from typing import Any

import pytest

from synthorg.api.openapi import inject_rfc9457_responses

_EXPECTED_RESPONSE_KEYS = frozenset(
    {
        "BadRequest",
        "Unauthorized",
        "Forbidden",
        "NotFound",
        "Conflict",
        "TooManyRequests",
        "InternalError",
        "ServiceUnavailable",
    }
)


@pytest.mark.integration
def test_full_app_schema_enhancement() -> None:
    """Enhance the real Litestar-generated schema end-to-end."""
    from synthorg.api.app import create_app

    app = create_app()
    schema: dict[str, Any] = app.openapi_schema.to_schema()
    result = inject_rfc9457_responses(schema)

    # ProblemDetail schema present.
    assert "ProblemDetail" in result["components"]["schemas"]

    # All 8 reusable responses defined (subset check — schema may
    # contain additional non-RFC-9457 reusable responses).
    responses = result["components"]["responses"]
    assert _EXPECTED_RESPONSE_KEYS.issubset(responses.keys())

    # Every RFC 9457 response has dual content types.
    for key in _EXPECTED_RESPONSE_KEYS:
        resp = responses[key]
        content = resp["content"]
        assert "application/json" in content, f"{key} missing application/json"
        assert "application/problem+json" in content, f"{key} missing problem+json"

    # At least one operation has error response refs.
    tasks_get = result["paths"]["/api/v1/tasks"]["get"]["responses"]
    assert "500" in tasks_get
    assert tasks_get["500"] == {
        "$ref": "#/components/responses/InternalError",
    }

    # Public endpoints don't have 401.
    health = result["paths"]["/api/v1/health"]["get"]["responses"]
    assert "401" not in health

    # Info description updated.
    assert "RFC 9457" in result["info"]["description"]
