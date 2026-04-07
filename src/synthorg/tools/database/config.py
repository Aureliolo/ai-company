"""Configuration models for database tools."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def _validate_default_connection(self) -> Self:
        """Ensure default_connection is a key in connections (when non-empty)."""
        if self.connections and self.default_connection not in self.connections:
            msg = (
                f"default_connection {self.default_connection!r} not found "
                f"in connections: {sorted(self.connections)}"
            )
            raise ValueError(msg)
        return self
