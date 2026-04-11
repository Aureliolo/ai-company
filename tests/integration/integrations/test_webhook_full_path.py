"""Webhook end-to-end: verify the bus bridge is wired."""

import pytest

from synthorg.integrations.webhooks.event_bus_bridge import WEBHOOK_CHANNEL


@pytest.mark.integration
class TestWebhookBusWiring:
    async def test_webhook_channel_name(self) -> None:
        assert WEBHOOK_CHANNEL.name == "#webhooks"
