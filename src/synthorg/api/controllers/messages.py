"""Message controller -- read-only access via MessageRepository."""

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002

from synthorg.api.dto import ApiResponse, PaginatedResponse
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import CursorLimit, CursorParam, paginate_cursor
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.communication.channel import Channel  # noqa: TC001
from synthorg.communication.message import Message  # noqa: TC001
from synthorg.observability import get_logger

logger = get_logger(__name__)


class MessageController(Controller):
    """Read-only access to message history."""

    path = "/messages"
    tags = ("messages",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_messages(
        self,
        state: State,
        channel: str | None = None,
        cursor: CursorParam = None,
        limit: CursorLimit = 50,
    ) -> PaginatedResponse[Message]:
        """List messages, optionally filtered by channel.

        When no ``channel`` filter is provided, returns an empty
        list -- use ``GET /messages/channels`` to discover available
        channels first.

        Args:
            state: Application state.
            channel: Filter by channel name.
            cursor: Opaque pagination cursor from the previous page.
            limit: Page size.

        Returns:
            Paginated message list.
        """
        app_state: AppState = state.app_state
        if channel is not None:
            messages = await app_state.persistence.messages.get_history(
                channel,
            )
        else:
            messages = ()
        page, meta = paginate_cursor(
            messages,
            limit=limit,
            cursor=cursor,
            secret=app_state.cursor_secret,
        )
        return PaginatedResponse(data=page, pagination=meta)

    @get("/channels")
    async def list_channels(
        self,
        state: State,
    ) -> ApiResponse[tuple[Channel, ...]]:
        """List available message bus channels.

        Args:
            state: Application state.

        Returns:
            Channel list envelope.
        """
        app_state: AppState = state.app_state
        channels = await app_state.message_bus.list_channels()
        return ApiResponse(data=channels)
