"""Tests for the email sender tool."""

from unittest.mock import patch

import pytest

from synthorg.core.enums import ActionType, ToolCategory
from synthorg.tools.communication.config import CommunicationToolsConfig
from synthorg.tools.communication.email_sender import EmailSenderTool


@pytest.mark.unit
class TestEmailSenderTool:
    """Tests for EmailSenderTool."""

    def test_category_is_communication(
        self,
        comm_config: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config)
        assert tool.category == ToolCategory.COMMUNICATION

    def test_action_type_is_comms_external(
        self,
        comm_config: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config)
        assert tool.action_type == ActionType.COMMS_EXTERNAL

    def test_name(
        self,
        comm_config: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config)
        assert tool.name == "email_sender"

    async def test_execute_no_email_config_returns_error(
        self,
        comm_config_no_email: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config_no_email)
        result = await tool.execute(
            arguments={
                "to": ["user@example.com"],
                "subject": "Test",
            }
        )
        assert result.is_error
        assert "SMTP configuration" in result.content

    async def test_execute_empty_recipients_returns_error(
        self,
        comm_config: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config)
        result = await tool.execute(arguments={"to": [], "subject": "Test"})
        assert result.is_error
        assert "At least one recipient" in result.content

    async def test_execute_too_many_recipients(self) -> None:
        config = CommunicationToolsConfig(
            email=pytest.importorskip(
                "synthorg.tools.communication.config"
            ).EmailConfig(
                host="smtp.example.com",
                from_address="test@example.com",
            ),
            max_recipients=2,
        )
        tool = EmailSenderTool(config=config)
        result = await tool.execute(
            arguments={
                "to": ["a@ex.com", "b@ex.com", "c@ex.com"],
                "subject": "Test",
            }
        )
        assert result.is_error
        assert "Too many recipients" in result.content

    @patch.object(EmailSenderTool, "_send_sync")
    async def test_execute_success(
        self,
        mock_send: object,
        comm_config: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config)
        result = await tool.execute(
            arguments={
                "to": ["user@example.com"],
                "subject": "Hello",
                "body": "World",
            }
        )
        assert not result.is_error
        assert "sent successfully" in result.content
        assert result.metadata["to"] == ["user@example.com"]

    @patch.object(
        EmailSenderTool,
        "_send_sync",
        side_effect=RuntimeError("SMTP error"),
    )
    async def test_execute_smtp_error(
        self,
        mock_send: object,
        comm_config: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config)
        result = await tool.execute(
            arguments={
                "to": ["user@example.com"],
                "subject": "Test",
            }
        )
        assert result.is_error
        assert "SMTP error" in result.content

    @patch.object(EmailSenderTool, "_send_sync")
    async def test_execute_with_cc_and_bcc(
        self,
        mock_send: object,
        comm_config: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config)
        result = await tool.execute(
            arguments={
                "to": ["a@ex.com"],
                "cc": ["b@ex.com"],
                "bcc": ["c@ex.com"],
                "subject": "Test",
            }
        )
        assert not result.is_error
        assert "3 recipient(s)" in result.content

    def test_parameters_schema_requires_to_and_subject(
        self,
        comm_config: CommunicationToolsConfig,
    ) -> None:
        tool = EmailSenderTool(config=comm_config)
        schema = tool.parameters_schema
        assert schema is not None
        assert "to" in schema["required"]
        assert "subject" in schema["required"]
