"""Channel domain model."""

from collections import Counter
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.communication.enums import ChannelType
from ai_company.core.types import (
    NotBlankStr,  # noqa: TC001 -- required at runtime by Pydantic
)


class Channel(BaseModel):
    """A named communication channel that agents can subscribe to.

    Attributes:
        name: Channel name (e.g. ``"#engineering"``).
        type: Channel delivery semantics.
        subscribers: Agent IDs subscribed to this channel.
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr = Field(description="Channel name")
    type: ChannelType = Field(
        default=ChannelType.TOPIC,
        description="Channel delivery semantics",
    )
    subscribers: tuple[str, ...] = Field(
        default=(),
        description="Agent IDs subscribed to this channel",
    )

    @model_validator(mode="after")
    def _validate_subscribers(self) -> Self:
        """Ensure subscriber entries are non-blank and unique."""
        for sub in self.subscribers:
            if not sub.strip():
                msg = "Empty or whitespace-only entry in subscribers"
                raise ValueError(msg)
        if len(self.subscribers) != len(set(self.subscribers)):
            dupes = sorted(s for s, c in Counter(self.subscribers).items() if c > 1)
            msg = f"Duplicate entries in subscribers: {dupes}"
            raise ValueError(msg)
        return self
