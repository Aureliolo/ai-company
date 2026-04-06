"""Configuration models for database tools."""

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class DatabaseConnectionConfig(BaseModel):
    """Connection configuration for a database backend.

    Attributes:
        database_path: Path to the SQLite database file.
        query_timeout: Maximum query execution time in seconds.
        read_only: Whether the connection is read-only by default.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    database_path: NotBlankStr = Field(
        description="Path to the SQLite database file",
    )
    query_timeout: float = Field(
        default=30.0,
        gt=0,
        le=300.0,
        description="Maximum query execution time (seconds)",
    )
    read_only: bool = Field(
        default=True,
        description="Whether the connection is read-only",
    )


class DatabaseConfig(BaseModel):
    """Top-level database tool configuration.

    Attributes:
        connections: Named database connections.
        default_connection: Name of the default connection.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    connections: dict[str, DatabaseConnectionConfig] = Field(
        default_factory=dict,
        description="Named database connections",
    )
    default_connection: NotBlankStr = Field(
        default="default",
        description="Name of the default connection",
    )
