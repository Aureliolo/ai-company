"""Configuration models for communication tools."""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class EmailConfig(BaseModel):
    """SMTP email configuration.

    Attributes:
        host: SMTP server hostname.
        port: SMTP server port.
        username: SMTP authentication username.
        password: SMTP authentication password.
        from_address: Sender email address.
        use_tls: Whether to use STARTTLS.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    host: NotBlankStr = Field(description="SMTP server hostname")
    port: int = Field(
        default=587,
        ge=1,
        le=65535,
        description="SMTP server port",
    )
    username: NotBlankStr | None = Field(
        default=None,
        description="SMTP authentication username",
    )
    password: NotBlankStr | None = Field(
        default=None,
        repr=False,
        description="SMTP authentication password",
    )
    from_address: NotBlankStr = Field(
        description="Sender email address",
    )
    use_tls: bool = Field(
        default=True,
        description="Whether to use STARTTLS",
    )


class CommunicationToolsConfig(BaseModel):
    """Top-level configuration for communication tools.

    Attributes:
        email: SMTP email configuration.  ``None`` disables the
            email sender tool.
        max_recipients: Maximum number of recipients per email.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    email: EmailConfig | None = Field(
        default=None,
        description="SMTP email config (None = email tool disabled)",
    )
    max_recipients: int = Field(
        default=100,
        gt=0,
        le=1000,
        description="Maximum recipients per email",
    )
