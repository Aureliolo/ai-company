"""Webhooks API controller.

Receives webhook events from external services, verifies
signatures, and publishes to the message bus.
"""

import json
from typing import TYPE_CHECKING

from litestar import Controller, Response, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter
from litestar.request import Request  # noqa: TC002

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_read_access
from synthorg.integrations.webhooks.event_bus_bridge import (
    publish_webhook_event,
)
from synthorg.integrations.webhooks.replay_protection import ReplayProtector
from synthorg.integrations.webhooks.verifiers.factory import get_verifier
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    WEBHOOK_ACCEPTED,
    WEBHOOK_RECEIVED,
    WEBHOOK_REJECTED,
)

if TYPE_CHECKING:
    from synthorg.integrations.connections.models import WebhookReceipt

logger = get_logger(__name__)

_replay_protector = ReplayProtector(window_seconds=300)


class WebhooksController(Controller):
    """Webhook receiver and activity log endpoints."""

    path = "/api/v1/webhooks"
    tags = ["Integrations"]  # noqa: RUF012

    @post(
        "/{connection_name:str}/{event_type:str}",
        summary="Receive a webhook event",
        status_code=202,
    )
    async def receive_webhook(
        self,
        state: State,
        request: Request,
        connection_name: str,
        event_type: str,
    ) -> Response:
        """Receive and verify a webhook event.

        Returns 202 Accepted on success, 401 on signature failure,
        409 on replay detection.
        """
        catalog = state["app_state"].connection_catalog
        conn = await catalog.get(connection_name)
        if conn is None:
            return Response(
                content={"error": "connection not found"},
                status_code=404,
            )

        logger.info(
            WEBHOOK_RECEIVED,
            connection_name=connection_name,
            event_type=event_type,
        )

        body = await request.body()
        headers = {k.lower(): v for k, v in request.headers.items()}

        # Signature verification
        verifier = get_verifier(conn.connection_type)
        credentials = await catalog.get_credentials(connection_name)
        signing_secret = credentials.get(
            "signing_secret",
            credentials.get("webhook_secret", ""),
        )

        if signing_secret:
            valid = await verifier.verify(
                body=body,
                headers=headers,
                secret=signing_secret,
            )
            if not valid:
                logger.warning(
                    WEBHOOK_REJECTED,
                    connection_name=connection_name,
                    reason="signature verification failed",
                )
                return Response(
                    content={"error": "signature verification failed"},
                    status_code=401,
                )

        # Replay protection
        nonce = headers.get("x-nonce") or headers.get(
            "x-request-id",
        )
        timestamp_str = headers.get("x-timestamp", "")
        timestamp = float(timestamp_str) if timestamp_str else None
        if not _replay_protector.check(
            nonce=nonce,
            timestamp=timestamp,
        ):
            logger.warning(
                WEBHOOK_REJECTED,
                connection_name=connection_name,
                reason="replay detected",
            )
            return Response(
                content={"error": "replay detected"},
                status_code=409,
            )

        # Parse payload
        try:
            payload = json.loads(body)
        except json.JSONDecodeError, UnicodeDecodeError:
            payload = {"raw": body.decode("utf-8", errors="replace")}

        # Publish to message bus
        bus = state["app_state"].message_bus
        await publish_webhook_event(
            bus=bus,
            connection_name=connection_name,
            event_type=event_type,
            payload=payload if isinstance(payload, dict) else {"data": payload},
        )

        logger.info(
            WEBHOOK_ACCEPTED,
            connection_name=connection_name,
            event_type=event_type,
        )
        return Response(
            content={"status": "accepted", "event_type": event_type},
            status_code=202,
        )

    @get(
        "/{connection_name:str}/activity",
        guards=[require_read_access],
        summary="List webhook activity for a connection",
    )
    async def list_activity(
        self,
        state: State,
        connection_name: str,
        limit: int = Parameter(
            default=100,
            ge=1,
            le=500,
            description="Max results",
        ),
    ) -> ApiResponse[tuple[WebhookReceipt, ...]]:
        """List recent webhook receipts for a connection."""
        persistence = state["app_state"].persistence
        receipts = await persistence.webhook_receipts.get_by_connection(
            connection_name,
            limit=limit,
        )
        return ApiResponse(data=receipts)
