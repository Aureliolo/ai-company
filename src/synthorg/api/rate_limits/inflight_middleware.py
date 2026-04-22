"""Per-operation inflight middleware (#1489, SEC-2).

``PerOpConcurrencyMiddleware`` reads a route-handler ``opt`` annotation
(``{"per_op_concurrency": (operation, max_inflight, key_policy)}``)
and caps simultaneous inflight requests for the (operation, subject)
bucket.  Denials raise :class:`ConcurrencyLimitExceededError`, which
flows through the existing RFC 9457 exception handler to a 429
response with ``Retry-After`` set.

Wired innermost in the middleware stack (see ``middleware_factory``)
so auth-populated ``scope["user"]`` is already available and the
permit is held only during actual handler execution.
"""

from typing import Any, Final

from litestar.connection import ASGIConnection
from litestar.enums import ScopeType
from litestar.middleware import ASGIMiddleware
from litestar.types import ASGIApp, Receive, Scope, Send  # noqa: TC002

from synthorg.api.errors import ServiceUnavailableError
from synthorg.api.rate_limits._subject import (
    STATE_KEY_INFLIGHT_CONFIG,
    STATE_KEY_INFLIGHT_STORE,
    extract_subject_key,
)
from synthorg.api.rate_limits.inflight_config import (
    PerOpConcurrencyConfig,  # noqa: TC001
)
from synthorg.api.rate_limits.inflight_protocol import InflightStore  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_APP_STARTUP

logger = get_logger(__name__)

# Route-handler ``opt`` key inspected for the annotation tuple.
# Public because callers splat ``per_op_concurrency(...)`` into
# ``opt={}``; the literal must be stable across releases.
OPT_KEY: Final[str] = "per_op_concurrency"


class PerOpConcurrencyMiddleware(ASGIMiddleware):
    """Wrap handlers that declare ``opt[per_op_concurrency] = (...)``.

    No-op for HTTP requests whose route handler lacks the annotation;
    non-HTTP scopes are filtered out by the ``scopes`` class attribute.
    When the annotation is present: read the inflight store + config
    from app state, resolve the subject key, attempt to acquire a
    permit via the store's async context manager, and run the inner
    app under the permit.
    """

    # Only intercept HTTP scopes; websockets and ASGI-raw scopes bypass
    # entirely so a websocket handler's ``opt`` (with a different shape)
    # cannot accidentally match the per_op_concurrency key.
    scopes: tuple[ScopeType, ...] = (ScopeType.HTTP,)

    async def handle(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        next_app: ASGIApp,
    ) -> None:
        """Dispatch: permit-wrap HTTP requests that opted in."""
        route_handler = scope.get("route_handler")
        opt = getattr(route_handler, "opt", None) or {}
        policy = opt.get(OPT_KEY)
        if policy is None:
            await next_app(scope, receive, send)
            return

        operation, default_max_inflight, key_policy = policy

        app = scope.get("app")
        state = getattr(app, "state", None) if app is not None else None
        config: PerOpConcurrencyConfig | None = getattr(
            state,
            STATE_KEY_INFLIGHT_CONFIG,
            None,
        )
        store: InflightStore | None = getattr(
            state,
            STATE_KEY_INFLIGHT_STORE,
            None,
        )

        # Master switch: opt-out short-circuits the middleware.
        if config is not None and not config.enabled:
            await next_app(scope, receive, send)
            return

        # Missing store/config is a wiring error -- fail loud and closed.
        # 503 is semantically correct (deployment misconfiguration, not
        # a per-user throttle); matches the sibling per_op_rate_limit
        # guard's behaviour in the same failure mode.
        if store is None or config is None:
            logger.error(
                API_APP_STARTUP,
                guard="per_op_concurrency",
                operation=operation,
                missing_store=store is None,
                missing_config=config is None,
                error=(
                    "per-op inflight limiter not wired; refusing request "
                    "to avoid silently uncapped endpoints"
                ),
            )
            msg = (
                f"Inflight guard for operation {operation!r} is not wired. "
                "This is a deployment error; see logs for context."
            )
            raise ServiceUnavailableError(msg)

        override = config.overrides.get(operation)
        max_inflight = override if override is not None else default_max_inflight
        if max_inflight <= 0:
            # Operator disabled this operation via override (0 or
            # negative was rejected at config load).
            await next_app(scope, receive, send)
            return

        connection: ASGIConnection[Any, Any, Any, Any] = ASGIConnection(
            scope,
            receive,
            send,
        )
        subject = extract_subject_key(
            connection,
            key_policy,
            guard_name="per_op_concurrency",
        )
        bucket_key = f"{operation}:{subject}"

        async with store.acquire(bucket_key, max_inflight=max_inflight):
            await next_app(scope, receive, send)
