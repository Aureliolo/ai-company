"""Tests for SettingsChangeDispatcher."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from synthorg.communication.channel import Channel
from synthorg.communication.enums import ChannelType, MessageType
from synthorg.communication.message import Message, MessageMetadata
from synthorg.communication.subscription import DeliveryEnvelope
from synthorg.settings.dispatcher import SettingsChangeDispatcher

# ── Helpers ──────────────────────────────────────────────────────


def _settings_message(
    namespace: str,
    key: str,
    restart_required: bool = False,
) -> Message:
    """Build a #settings channel message matching SettingsService format."""
    return Message(
        timestamp=datetime.now(UTC),
        sender="system",
        to="#settings",
        type=MessageType.ANNOUNCEMENT,
        channel="#settings",
        content=f"Setting changed: {namespace}/{key}",
        metadata=MessageMetadata(
            extra=(
                ("namespace", namespace),
                ("key", key),
                ("restart_required", str(restart_required)),
            ),
        ),
    )


def _envelope(msg: Message) -> DeliveryEnvelope:
    return DeliveryEnvelope(
        message=msg,
        channel_name="#settings",
        delivered_at=datetime.now(UTC),
    )


class _FakeSubscriber:
    """Test subscriber that records calls."""

    def __init__(
        self,
        name: str,
        keys: frozenset[tuple[str, str]],
    ) -> None:
        self._name = name
        self._keys = keys
        self.calls: list[tuple[str, str]] = []

    @property
    def watched_keys(self) -> frozenset[tuple[str, str]]:
        return self._keys

    @property
    def subscriber_name(self) -> str:
        return self._name

    async def on_settings_changed(self, namespace: str, key: str) -> None:
        self.calls.append((namespace, key))


class _ErrorSubscriber(_FakeSubscriber):
    """Subscriber that raises on every call."""

    async def on_settings_changed(self, namespace: str, key: str) -> None:
        msg = f"boom from {self._name}"
        raise RuntimeError(msg)


class _FakeBus:
    """Controllable message bus for dispatcher tests.

    Feed messages via ``enqueue(envelope)``; the dispatcher's polling
    loop will consume them in order.
    """

    def __init__(self) -> None:
        self._running = True
        self._queue: asyncio.Queue[DeliveryEnvelope | None] = asyncio.Queue()
        self._channels_created: list[str] = []
        self._subscriptions: list[tuple[str, str]] = []
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()

    def enqueue(self, envelope: DeliveryEnvelope) -> None:
        self._queue.put_nowait(envelope)

    async def subscribe(self, channel_name: str, subscriber_id: str) -> Any:
        self._subscriptions.append((channel_name, subscriber_id))
        return None

    async def unsubscribe(self, channel_name: str, subscriber_id: str) -> None:
        pass

    async def receive(
        self,
        channel_name: str,
        subscriber_id: str,
        *,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> DeliveryEnvelope | None:
        try:
            return await asyncio.wait_for(
                self._queue.get(),
                timeout=timeout,
            )
        except TimeoutError:
            return None

    async def create_channel(self, channel: Channel) -> Channel:
        self._channels_created.append(channel.name)
        return channel

    async def get_channel(self, channel_name: str) -> Channel:
        return Channel(name=channel_name, type=ChannelType.TOPIC)

    async def list_channels(self) -> tuple[Channel, ...]:
        return ()

    async def publish(self, message: Message) -> None:
        pass

    async def send_direct(self, message: Message, *, recipient: str) -> None:
        pass

    async def get_channel_history(
        self, channel_name: str, *, limit: int | None = None
    ) -> tuple[Message, ...]:
        return ()


@pytest.fixture
def bus() -> _FakeBus:
    return _FakeBus()


@pytest.fixture
def provider_sub() -> _FakeSubscriber:
    return _FakeSubscriber(
        "provider-sub",
        frozenset({("providers", "routing_strategy")}),
    )


@pytest.fixture
def memory_sub() -> _FakeSubscriber:
    return _FakeSubscriber(
        "memory-sub",
        frozenset({("memory", "backend"), ("memory", "default_level")}),
    )


@pytest.fixture
def dispatcher(
    bus: _FakeBus,
    provider_sub: _FakeSubscriber,
    memory_sub: _FakeSubscriber,
) -> SettingsChangeDispatcher:
    return SettingsChangeDispatcher(
        message_bus=bus,
        subscribers=(provider_sub, memory_sub),
    )


async def _drain(
    dispatcher: SettingsChangeDispatcher,
    bus: _FakeBus,
    count: int,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
) -> None:
    """Wait until all enqueued messages have been processed."""
    # Give the poll loop time to process messages
    deadline = asyncio.get_event_loop().time() + timeout
    while bus._queue.qsize() > 0:
        if asyncio.get_event_loop().time() > deadline:
            msg = "Drain timed out"
            raise TimeoutError(msg)
        await asyncio.sleep(0.05)
    # Extra sleep to let the dispatcher finish processing the last message
    await asyncio.sleep(0.1)


# ── Lifecycle Tests ──────────────────────────────────────────────


@pytest.mark.unit
class TestDispatcherLifecycle:
    async def test_start_subscribes_to_settings_channel(
        self,
        dispatcher: SettingsChangeDispatcher,
        bus: _FakeBus,
    ) -> None:
        await dispatcher.start()
        try:
            assert ("#settings", "__settings_dispatcher__") in bus._subscriptions
        finally:
            await dispatcher.stop()

    async def test_double_start_raises(
        self,
        dispatcher: SettingsChangeDispatcher,
    ) -> None:
        await dispatcher.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                await dispatcher.start()
        finally:
            await dispatcher.stop()

    async def test_stop_is_idempotent(
        self,
        dispatcher: SettingsChangeDispatcher,
    ) -> None:
        await dispatcher.start()
        await dispatcher.stop()
        await dispatcher.stop()  # should not raise

    async def test_stop_without_start(
        self,
        dispatcher: SettingsChangeDispatcher,
    ) -> None:
        # Should not raise
        await dispatcher.stop()


# ── Dispatch Tests ───────────────────────────────────────────────


@pytest.mark.unit
class TestDispatchRouting:
    async def test_dispatches_to_matching_subscriber(
        self,
        dispatcher: SettingsChangeDispatcher,
        bus: _FakeBus,
        provider_sub: _FakeSubscriber,
    ) -> None:
        await dispatcher.start()
        try:
            msg = _settings_message("providers", "routing_strategy")
            bus.enqueue(_envelope(msg))
            await _drain(dispatcher, bus, 1)
            assert ("providers", "routing_strategy") in provider_sub.calls
        finally:
            await dispatcher.stop()

    async def test_does_not_dispatch_to_non_matching_subscriber(
        self,
        dispatcher: SettingsChangeDispatcher,
        bus: _FakeBus,
        provider_sub: _FakeSubscriber,
        memory_sub: _FakeSubscriber,
    ) -> None:
        await dispatcher.start()
        try:
            msg = _settings_message("providers", "routing_strategy")
            bus.enqueue(_envelope(msg))
            await _drain(dispatcher, bus, 1)
            assert len(memory_sub.calls) == 0
        finally:
            await dispatcher.stop()

    async def test_dispatches_to_multiple_matching_subscribers(
        self,
        bus: _FakeBus,
    ) -> None:
        sub_a = _FakeSubscriber("a", frozenset({("ns", "k")}))
        sub_b = _FakeSubscriber("b", frozenset({("ns", "k")}))
        d = SettingsChangeDispatcher(
            message_bus=bus,
            subscribers=(sub_a, sub_b),
        )
        await d.start()
        try:
            bus.enqueue(_envelope(_settings_message("ns", "k")))
            await _drain(d, bus, 1)
            assert ("ns", "k") in sub_a.calls
            assert ("ns", "k") in sub_b.calls
        finally:
            await d.stop()

    async def test_skips_restart_required_settings(
        self,
        dispatcher: SettingsChangeDispatcher,
        bus: _FakeBus,
        memory_sub: _FakeSubscriber,
    ) -> None:
        await dispatcher.start()
        try:
            msg = _settings_message("memory", "backend", restart_required=True)
            bus.enqueue(_envelope(msg))
            await _drain(dispatcher, bus, 1)
            assert len(memory_sub.calls) == 0
        finally:
            await dispatcher.stop()

    async def test_dispatches_non_restart_required_memory_settings(
        self,
        dispatcher: SettingsChangeDispatcher,
        bus: _FakeBus,
        memory_sub: _FakeSubscriber,
    ) -> None:
        await dispatcher.start()
        try:
            msg = _settings_message("memory", "default_level", restart_required=False)
            bus.enqueue(_envelope(msg))
            await _drain(dispatcher, bus, 1)
            assert ("memory", "default_level") in memory_sub.calls
        finally:
            await dispatcher.stop()


# ── Error Isolation Tests ────────────────────────────────────────


@pytest.mark.unit
class TestDispatcherErrorIsolation:
    async def test_continues_after_subscriber_error(
        self,
        bus: _FakeBus,
    ) -> None:
        """A failing subscriber does not prevent others from being notified."""
        error_sub = _ErrorSubscriber("boom", frozenset({("ns", "k")}))
        good_sub = _FakeSubscriber("ok", frozenset({("ns", "k")}))
        d = SettingsChangeDispatcher(
            message_bus=bus,
            subscribers=(error_sub, good_sub),
        )
        await d.start()
        try:
            bus.enqueue(_envelope(_settings_message("ns", "k")))
            await _drain(d, bus, 1)
            assert ("ns", "k") in good_sub.calls
        finally:
            await d.stop()

    async def test_poll_loop_survives_subscriber_error(
        self,
        bus: _FakeBus,
    ) -> None:
        """After one error, the loop keeps processing subsequent messages."""
        error_sub = _ErrorSubscriber("boom", frozenset({("ns", "k")}))
        good_sub = _FakeSubscriber("ok", frozenset({("ns", "k")}))
        d = SettingsChangeDispatcher(
            message_bus=bus,
            subscribers=(error_sub, good_sub),
        )
        await d.start()
        try:
            bus.enqueue(_envelope(_settings_message("ns", "k")))
            await _drain(d, bus, 1)
            good_sub.calls.clear()

            bus.enqueue(_envelope(_settings_message("ns", "k")))
            await _drain(d, bus, 1)
            assert ("ns", "k") in good_sub.calls
        finally:
            await d.stop()


# ── Metadata Extraction Tests ────────────────────────────────────


@pytest.mark.unit
class TestMetadataExtraction:
    async def test_ignores_message_with_missing_metadata(
        self,
        dispatcher: SettingsChangeDispatcher,
        bus: _FakeBus,
        provider_sub: _FakeSubscriber,
    ) -> None:
        """Messages without namespace/key in metadata are skipped."""
        msg = Message(
            timestamp=datetime.now(UTC),
            sender="system",
            to="#settings",
            type=MessageType.ANNOUNCEMENT,
            channel="#settings",
            content="bad message",
            metadata=MessageMetadata(extra=()),
        )
        await dispatcher.start()
        try:
            bus.enqueue(_envelope(msg))
            await _drain(dispatcher, bus, 1)
            assert len(provider_sub.calls) == 0
        finally:
            await dispatcher.stop()
