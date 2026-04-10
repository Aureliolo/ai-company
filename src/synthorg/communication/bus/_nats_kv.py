"""JetStream KV bucket operations for channel persistence.

Handles reading, writing, and scanning the KV bucket that stores
channel definitions so they are discoverable across processes.
"""

import asyncio
import json
from typing import Any

from synthorg.communication.bus._nats_state import _NatsState  # noqa: TC001
from synthorg.communication.bus._nats_utils import decode_token, encode_token
from synthorg.communication.bus.errors import BusStreamError
from synthorg.communication.channel import Channel
from synthorg.communication.errors import ChannelAlreadyExistsError
from synthorg.observability import get_logger
from synthorg.observability.events.communication import (
    COMM_BUS_KV_READ_FAILED,
    COMM_BUS_KV_WRITE_FAILED,
)

logger = get_logger(__name__)


async def create_channel_in_kv(
    state: _NatsState,
    channel: Channel,
) -> None:
    """Atomically create a channel entry in KV (fails if it exists).

    Uses the KV ``create`` API which is an atomic create-if-not-exists.

    Raises:
        ChannelAlreadyExistsError: If the key already exists.
        BusStreamError: If a transport error prevents the write.
    """
    from nats.js.errors import (  # noqa: PLC0415
        KeyWrongLastSequenceError,
    )

    if state.kv is None:
        return
    key = encode_token(channel.name)
    value = channel.model_dump_json().encode("utf-8")
    try:
        await state.kv.create(key, value)
    except KeyWrongLastSequenceError:
        msg = f"Channel already exists in KV: {channel.name}"
        raise ChannelAlreadyExistsError(
            msg, context={"channel": channel.name}
        ) from None
    except Exception as exc:
        logger.warning(
            COMM_BUS_KV_WRITE_FAILED,
            channel=channel.name,
            error=str(exc),
        )
        msg = f"KV create failed for channel {channel.name!r}: {exc}"
        raise BusStreamError(msg, context={"channel": channel.name}) from exc


async def write_channel_to_kv(state: _NatsState, channel: Channel) -> None:
    """Persist a Channel definition to the KV bucket (best-effort update).

    Used for subscription changes and direct channel updates where
    local state is authoritative and KV persistence is secondary.
    Logs failures but does not raise.
    """
    if state.kv is None:
        return
    key = encode_token(channel.name)
    value = channel.model_dump_json().encode("utf-8")
    try:
        await state.kv.put(key, value)
    except Exception as exc:
        logger.warning(
            COMM_BUS_KV_WRITE_FAILED,
            channel=channel.name,
            error=str(exc),
        )


async def load_channel_from_kv(
    state: _NatsState,
    channel_name: str,
) -> Channel | None:
    """Load a Channel definition from the KV bucket, if present."""
    entry = await fetch_kv_entry(state, channel_name)
    if entry is None:
        return None
    return decode_kv_channel(channel_name, entry)


async def fetch_kv_entry(
    state: _NatsState,
    channel_name: str,
) -> Any | None:
    """Fetch a raw KV entry, logging transport errors and returning None."""
    from nats.js.errors import KeyNotFoundError  # noqa: PLC0415

    if state.kv is None:
        return None
    key = encode_token(channel_name)
    try:
        entry = await state.kv.get(key)
    except KeyNotFoundError:
        return None
    except Exception as exc:
        logger.warning(
            COMM_BUS_KV_READ_FAILED,
            channel=channel_name,
            error=str(exc),
        )
        msg = f"KV transport error for channel {channel_name!r}: {exc}"
        raise BusStreamError(msg, context={"channel": channel_name}) from exc
    if entry is None or entry.value is None:
        return None
    return entry


def decode_kv_channel(
    channel_name: str,
    entry: Any,
) -> Channel | None:
    """Decode a KV entry into a Channel, logging parse failures."""
    try:
        data = json.loads(entry.value.decode("utf-8"))
        channel = Channel.model_validate(data)
    except json.JSONDecodeError as exc:
        logger.warning(
            COMM_BUS_KV_READ_FAILED,
            channel=channel_name,
            error=str(exc),
        )
        return None
    except ValueError as exc:
        logger.warning(
            COMM_BUS_KV_READ_FAILED,
            channel=channel_name,
            error=str(exc),
        )
        return None
    if channel.name != channel_name:
        logger.warning(
            COMM_BUS_KV_READ_FAILED,
            channel=channel_name,
            error=(
                f"KV entry name mismatch: expected {channel_name!r}, "
                f"got {channel.name!r}"
            ),
        )
        return None
    return channel


async def scan_kv_channels(state: _NatsState) -> list[Channel]:
    """Scan the KV bucket for all persisted channels.

    Raises:
        BusStreamError: If the KV bucket cannot be listed.
    """
    if state.kv is None:
        return []
    from nats.js.errors import NoKeysError  # noqa: PLC0415

    try:
        keys = await state.kv.keys()
    except NoKeysError:
        return []
    except Exception as exc:
        logger.warning(
            COMM_BUS_KV_READ_FAILED,
            channel="*",
            error=str(exc),
            phase="list_channels_scan",
        )
        msg = f"KV scan failed: {exc}"
        raise BusStreamError(msg, context={"phase": "list_channels_scan"}) from exc

    decoded_keys: list[tuple[str, str]] = []
    for key in keys:
        try:
            decoded_keys.append((key, decode_token(key)))
        except Exception as exc:
            logger.warning(
                COMM_BUS_KV_READ_FAILED,
                channel=key,
                error=str(exc),
                phase="decode_token",
            )

    entries = await asyncio.gather(
        *(fetch_kv_entry(state, name) for _, name in decoded_keys),
    )
    channels: list[Channel] = []
    for (_, decoded_name), entry in zip(decoded_keys, entries, strict=True):
        if entry is None:
            continue
        ch = decode_kv_channel(decoded_name, entry)
        if ch is not None:
            channels.append(ch)
    return channels
