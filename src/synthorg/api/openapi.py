"""OpenAPI schema post-processor for RFC 9457 dual-format error responses.

Litestar auto-generates the OpenAPI schema from controller return types,
but exception handlers (which perform content negotiation between
``application/json`` envelopes and ``application/problem+json`` bare
bodies) are invisible to the generator.

This module provides :func:`inject_rfc9457_responses` which transforms
the Litestar-generated schema dict to:

1. Add the ``ProblemDetail`` schema (RFC 9457 bare response body)
2. Define reusable error responses with dual content types
3. Inject error response references into every operation
4. Replace Litestar's default 400 schema with the actual envelope
5. Document content negotiation in ``info.description``

Called by ``scripts/export_openapi.py`` after schema generation.
"""

import copy
from typing import Any, Final

from synthorg.api.dto import ProblemDetail
from synthorg.api.errors import (
    CATEGORY_TITLES,
    ErrorCategory,
    ErrorCode,
    category_type_uri,
)

# ── Constants ─────────────────────────────────────────────────

_PROBLEM_JSON: Final[str] = "application/problem+json"
_APP_JSON: Final[str] = "application/json"

# Paths that skip authentication (no 401/403 injected).
_PUBLIC_PATH_SUFFIXES: Final[tuple[str, ...]] = (
    "/health",
    "/auth/setup",
    "/auth/login",
)

# HTTP methods that accept a request body (get 400/409 injected).
_WRITE_METHODS: Final[frozenset[str]] = frozenset({"post", "put", "patch", "delete"})

# Envelope schema ref (Litestar-generated name for ApiResponse[None]).
_ENVELOPE_REF: Final[str] = "#/components/schemas/ApiResponse_NoneType_"

# ProblemDetail schema ref (we add this).
_PROBLEM_DETAIL_REF: Final[str] = "#/components/schemas/ProblemDetail"

_EXAMPLE_INSTANCE_ID: Final[str] = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# ── Error response definitions ────────────────────────────────

# (status_code, key, description, error_code, error_category, detail, retryable)
_ERROR_RESPONSES: Final[
    tuple[tuple[int, str, str, ErrorCode, ErrorCategory, str, bool], ...]
] = (
    (
        400,
        "BadRequest",
        "Validation error — request body or parameters are invalid.",
        ErrorCode.REQUEST_VALIDATION_ERROR,
        ErrorCategory.VALIDATION,
        "Validation error",
        False,
    ),
    (
        401,
        "Unauthorized",
        "Authentication required — missing or invalid credentials.",
        ErrorCode.UNAUTHORIZED,
        ErrorCategory.AUTH,
        "Authentication required",
        False,
    ),
    (
        403,
        "Forbidden",
        "Insufficient permissions for this operation.",
        ErrorCode.FORBIDDEN,
        ErrorCategory.AUTH,
        "Forbidden",
        False,
    ),
    (
        404,
        "NotFound",
        "Requested resource does not exist.",
        ErrorCode.RECORD_NOT_FOUND,
        ErrorCategory.NOT_FOUND,
        "Resource not found",
        False,
    ),
    (
        409,
        "Conflict",
        "Resource conflict — duplicate or invalid state transition.",
        ErrorCode.RESOURCE_CONFLICT,
        ErrorCategory.CONFLICT,
        "Resource conflict",
        False,
    ),
    (
        429,
        "TooManyRequests",
        "Rate limit exceeded — back off and retry.",
        ErrorCode.RATE_LIMITED,
        ErrorCategory.RATE_LIMIT,
        "Rate limit exceeded",
        True,
    ),
    (
        500,
        "InternalError",
        "Internal server error.",
        ErrorCode.INTERNAL_ERROR,
        ErrorCategory.INTERNAL,
        "Internal server error",
        False,
    ),
    (
        503,
        "ServiceUnavailable",
        "Required service is temporarily unavailable.",
        ErrorCode.SERVICE_UNAVAILABLE,
        ErrorCategory.INTERNAL,
        "Service unavailable",
        True,
    ),
)

_INFO_DESCRIPTION: Final[str] = """\
SynthOrg REST API for managing synthetic organizations \u2014 autonomous \
AI agents orchestrated as a virtual company.

## Error Handling (RFC 9457)

All error responses support content negotiation between two formats:

- **`application/json`** (default): Standard `ApiResponse` envelope with \
`error`, `error_detail`, and `success` fields
- **`application/problem+json`**: Bare RFC 9457 Problem Detail body \u2014 \
send `Accept: application/problem+json`

Every error includes machine-readable metadata: `error_code` \
(4-digit category-grouped), `error_category`, `retryable`, and \
`retry_after` (seconds).

See the [Error Reference](https://synthorg.io/docs/errors) for the \
full error taxonomy and retry guidance.\
"""


# ── Helpers ───────────────────────────────────────────────────


def _build_problem_detail_schema() -> dict[str, Any]:
    """Generate the ``ProblemDetail`` JSON Schema from the Pydantic model.

    Rewrites internal ``$defs`` references to point at
    ``#/components/schemas/`` so they resolve correctly when placed
    inside the OpenAPI ``components.schemas`` section.

    Returns:
        A two-tuple-style dict: the schema itself has ``$defs``
        stripped and ``$ref`` paths rewritten.
    """
    raw = ProblemDetail.model_json_schema(mode="serialization")

    # Strip $defs — they'll be merged separately.
    raw.pop("$defs", None)

    # Rewrite $ref from '#/$defs/X' to '#/components/schemas/X'.
    result: dict[str, Any] = _rewrite_refs(raw)
    return result


def _rewrite_refs(obj: Any) -> Any:
    """Recursively rewrite ``$ref`` paths from Pydantic to OpenAPI."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref: str = obj["$ref"]
            if ref.startswith("#/$defs/"):
                return {"$ref": f"#/components/schemas/{ref.removeprefix('#/$defs/')}"}
        return {k: _rewrite_refs(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rewrite_refs(item) for item in obj]
    return obj


def _envelope_example(
    *,
    detail: str,
    error_code: ErrorCode,
    error_category: ErrorCategory,
    retryable: bool,
) -> dict[str, Any]:
    """Build an ``ApiResponse`` envelope example for an error response."""
    title = CATEGORY_TITLES[error_category]
    type_uri = category_type_uri(error_category)
    return {
        "data": None,
        "error": detail,
        "error_detail": {
            "detail": detail,
            "error_code": error_code.value,
            "error_category": error_category.value,
            "retryable": retryable,
            "retry_after": None,
            "instance": _EXAMPLE_INSTANCE_ID,
            "title": title,
            "type": type_uri,
        },
        "success": False,
    }


def _problem_detail_example(
    *,
    status: int,
    detail: str,
    error_code: ErrorCode,
    error_category: ErrorCategory,
    retryable: bool,
) -> dict[str, Any]:
    """Build a bare RFC 9457 ``ProblemDetail`` example."""
    title = CATEGORY_TITLES[error_category]
    type_uri = category_type_uri(error_category)
    return {
        "type": type_uri,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": _EXAMPLE_INSTANCE_ID,
        "error_code": error_code.value,
        "error_category": error_category.value,
        "retryable": retryable,
        "retry_after": None,
    }


def _build_reusable_response(  # noqa: PLR0913
    *,
    status: int,
    description: str,
    error_code: ErrorCode,
    error_category: ErrorCategory,
    detail: str,
    retryable: bool,
) -> dict[str, Any]:
    """Build a reusable response object with dual content types."""
    return {
        "description": description,
        "content": {
            _APP_JSON: {
                "schema": {"$ref": _ENVELOPE_REF},
                "example": _envelope_example(
                    detail=detail,
                    error_code=error_code,
                    error_category=error_category,
                    retryable=retryable,
                ),
            },
            _PROBLEM_JSON: {
                "schema": {"$ref": _PROBLEM_DETAIL_REF},
                "example": _problem_detail_example(
                    status=status,
                    detail=detail,
                    error_code=error_code,
                    error_category=error_category,
                    retryable=retryable,
                ),
            },
        },
    }


def _is_public_path(path: str) -> bool:
    """Check whether a path is unauthenticated (no 401/403)."""
    return any(path.endswith(suffix) for suffix in _PUBLIC_PATH_SUFFIXES)


def _has_path_params(path: str) -> bool:
    """Check whether a path contains ``{param}`` segments."""
    return "{" in path


def _response_ref(key: str) -> dict[str, str]:
    """Build a ``$ref`` to a reusable response."""
    return {"$ref": f"#/components/responses/{key}"}


# ── Response-to-operation mapping ─────────────────────────────

# Maps response keys to the condition under which they are injected.
# Condition signature: (path: str, method: str, operation: dict) -> bool


def _should_inject(
    key: str,
    path: str,
    method: str,
    operation: dict[str, Any],
) -> bool:
    """Decide whether to inject a response reference into an operation.

    Returns ``True`` when the given error response *key* is applicable
    to the *path*/*method* combination.
    """
    is_public = _is_public_path(path)
    is_write = method in _WRITE_METHODS
    has_params = _has_path_params(path)

    checks: dict[str, bool] = {
        "InternalError": True,
        "ServiceUnavailable": not is_public,
        "Unauthorized": not is_public,
        "Forbidden": not is_public and is_write,
        # Inject on write methods or replace Litestar's incorrect default.
        "BadRequest": is_write or "400" in operation.get("responses", {}),
        "NotFound": has_params,
        "Conflict": method in {"post", "put", "patch"},
        "TooManyRequests": not is_public,
    }
    return checks.get(key, False)


# ── Main function ─────────────────────────────────────────────


def inject_rfc9457_responses(schema: dict[str, Any]) -> dict[str, Any]:
    """Inject RFC 9457 dual-format error responses into an OpenAPI schema.

    Takes the raw schema dict produced by Litestar's
    ``app.openapi_schema.to_schema()`` and returns a **new** dict with:

    - ``ProblemDetail`` added to ``components.schemas``
    - Reusable error responses (dual content types) in
      ``components.responses``
    - Error response refs injected into every operation
    - ``info.description`` updated with RFC 9457 documentation

    Args:
        schema: OpenAPI schema dict (not modified).

    Returns:
        Enhanced copy of the schema.
    """
    result = copy.deepcopy(schema)

    components = result.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    responses = components.setdefault("responses", {})

    # 1. Add ProblemDetail schema.
    if "ProblemDetail" not in schemas:
        schemas["ProblemDetail"] = _build_problem_detail_schema()

    # 2. Build reusable responses with dual content types.
    response_keys: list[str] = []
    for (
        status,
        key,
        description,
        error_code,
        error_category,
        detail,
        retryable,
    ) in _ERROR_RESPONSES:
        responses[key] = _build_reusable_response(
            status=status,
            description=description,
            error_code=error_code,
            error_category=error_category,
            detail=detail,
            retryable=retryable,
        )
        response_keys.append(key)

    # 3. Inject into operations.
    status_for_key = {key: str(status) for status, key, *_ in _ERROR_RESPONSES}

    for path, path_item in result.get("paths", {}).items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            op_responses = operation["responses"]

            for key in response_keys:
                status_code = status_for_key[key]
                if not _should_inject(key, path, method, operation):
                    continue
                # Always replace 400 (Litestar's default is incorrect).
                if status_code == "400" or status_code not in op_responses:
                    op_responses[status_code] = _response_ref(key)

    # 4. Update info.description.
    result.setdefault("info", {})["description"] = _INFO_DESCRIPTION

    return result
