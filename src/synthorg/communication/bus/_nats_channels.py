"""Channel management: creation, resolution, listing, and subject helpers.

Handles the mapping between SynthOrg channel names and JetStream
subject tokens, as well as channel creation/resolution backed by the
KV bucket for multi-process discovery.
"""

from synthorg.communication.bus._nats_kv import (
    load_channel_from_kv,
    scan_kv_channels,
    write_channel_to_kv,
)
from synthorg.communication.bus._nats_state import _NatsState  # noqa: TC001
from synthorg.communication.bus._nats_utils import (
    SUBJECT_CHANNEL_TOKEN,
    SUBJECT_DIRECT_TOKEN,
    encode_token,
    raise_channel_not_found,
    require_running,
)
from synthorg.communication.channel import Channel
from synthorg.communication.enums import ChannelType
from synthorg.communication.errors import ChannelAlreadyExistsError
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMM_CHANNEL_ALREADY_EXISTS,
    COMM_CHANNEL_CREATED,
)

logger = get_logger(__name__)


def channel_subject(prefix: str, channel_name: str) -> str:
    """Compute the stream subject for a TOPIC/BROADCAST channel."""
    pfx = prefix.lower()
    return f"{pfx}.bus.{SUBJECT_CHANNEL_TOKEN}.{encode_token(channel_name)}"


def direct_subject(prefix: str, channel_name: str) -> str:
    """Compute the stream subject for a DIRECT channel."""
    pfx = prefix.lower()
    return f"{pfx}.bus.{SUBJECT_DIRECT_TOKEN}.{encode_token(channel_name)}"


def subject_for_channel(prefix: str, ch: Channel) -> str:
    """Pick the correct subject based on channel type."""
    if ch.type == ChannelType.DIRECT:
        return direct_subject(prefix, ch.name)
    return channel_subject(prefix, ch.name)


def durable_name(channel_name: str, subscriber_id: str) -> str:
    """Compute a safe durable consumer name."""
    return f"{encode_token(channel_name)}__{encode_token(subscriber_id)}"


async def ensure_direct_channel(
    state: _NatsState,
    channel_name: str,
    pair: tuple[str, str],
) -> None:
    """Create DIRECT channel locally and in KV bucket if needed.

    Args:
        state: Shared bus state.
        channel_name: Deterministic direct-channel name (``@a:b``).
        pair: Sorted tuple of the two participant agent IDs.

    Must be called under ``state.lock``.
    """
    if channel_name in state.channels:
        current = state.channels[channel_name]
        pair_set = set(pair)
        if not pair_set.issubset(set(current.subscribers)):
            new_subs = tuple(sorted(set(current.subscribers) | pair_set))
            updated = current.model_copy(
                update={"subscribers": new_subs},
            )
            await write_channel_to_kv(state, updated)
            state.channels[channel_name] = updated
        return

    ch = Channel(
        name=channel_name,
        type=ChannelType.DIRECT,
        subscribers=pair,
    )
    await write_channel_to_kv(state, ch)
    state.channels[channel_name] = ch
    logger.info(
        COMM_CHANNEL_CREATED,
        channel=channel_name,
        type=str(ChannelType.DIRECT),
        backend="nats",
    )


async def create_channel(state: _NatsState, ch: Channel) -> Channel:
    """Create a new channel.

    Uses an optimistic check-then-act pattern: local cache, then KV
    bucket, then local cache again. Two processes creating the same
    channel concurrently may both succeed at the KV write (last-write
    wins). A future improvement could use KV CAS/revision checks for
    cross-process atomicity.

    Raises:
        MessageBusNotRunningError: If not running.
        ChannelAlreadyExistsError: If the channel already exists.
    """
    async with state.lock:
        require_running(state)
        if ch.name in state.channels:
            logger.warning(
                COMM_CHANNEL_ALREADY_EXISTS,
                channel=ch.name,
            )
            msg = f"Channel already exists: {ch.name}"
            raise ChannelAlreadyExistsError(
                msg,
                context={"channel": ch.name},
            )
    kv_existing = await load_channel_from_kv(state, ch.name)
    if kv_existing is not None:
        async with state.lock:
            if ch.name not in state.channels:
                state.channels[ch.name] = kv_existing
        logger.warning(
            COMM_CHANNEL_ALREADY_EXISTS,
            channel=ch.name,
            source="kv",
        )
        msg = f"Channel already exists (peer-created): {ch.name}"
        raise ChannelAlreadyExistsError(
            msg,
            context={"channel": ch.name},
        )
    async with state.lock:
        require_running(state)
        if ch.name in state.channels:
            logger.warning(
                COMM_CHANNEL_ALREADY_EXISTS,
                channel=ch.name,
            )
            msg = f"Channel already exists: {ch.name}"
            raise ChannelAlreadyExistsError(
                msg,
                context={"channel": ch.name},
            )
        await write_channel_to_kv(state, ch)
        state.channels[ch.name] = ch
    logger.info(
        COMM_CHANNEL_CREATED,
        channel=ch.name,
        type=str(ch.type),
        backend="nats",
    )
    return ch


async def resolve_channel_or_raise(
    state: _NatsState,
    channel_name: str,
) -> Channel:
    """Return a Channel from local cache or JetStream KV.

    Shared by multiple public methods so a second process can observe
    channels created by another process on the same stream.
    """
    async with state.lock:
        cached = state.channels.get(channel_name)
    if cached is not None:
        return cached

    loaded = await load_channel_from_kv(state, channel_name)
    if loaded is None:
        raise_channel_not_found(channel_name)

    async with state.lock:
        existing = state.channels.get(channel_name)
        if existing is not None:
            return existing
        state.channels[channel_name] = loaded
        return loaded


async def list_channels(state: _NatsState) -> tuple[Channel, ...]:
    """List all channels, including those created by peer processes."""
    kv_channels = await scan_kv_channels(state)
    async with state.lock:
        for ch in kv_channels:
            if ch.name not in state.channels:
                state.channels[ch.name] = ch
        return tuple(state.channels.values())
