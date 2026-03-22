"""System user -- persistent internal identity for CLI-to-backend auth.

The system user is bootstrapped at application startup and serves as
the JWT subject for CLI commands (``synthorg backup``, ``synthorg wipe``,
etc.).  It cannot be logged into, deleted, or modified through the API.
"""

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from synthorg.api.auth.models import User
from synthorg.api.guards import HumanRole
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_AUTH_SYSTEM_USER_ENSURED

if TYPE_CHECKING:
    from synthorg.api.auth.service import AuthService
    from synthorg.persistence.protocol import PersistenceBackend

logger = get_logger(__name__)

# The ID and username are deliberately identical.  Security gates
# use the ID (via ``is_system_user``), not the username.
SYSTEM_USER_ID: Final[str] = "system"
SYSTEM_USERNAME: Final[str] = "system"


def is_system_user(user_id: str) -> bool:
    """Check whether *user_id* is the system user.

    Args:
        user_id: User identifier to check.

    Returns:
        ``True`` if *user_id* matches the well-known system user ID.
    """
    return user_id == SYSTEM_USER_ID


async def ensure_system_user(
    persistence: PersistenceBackend,
    auth_service: AuthService,
) -> None:
    """Create the system user if it does not already exist.

    Safe to call on every startup.  Under concurrent startup the
    underlying upsert (``ON CONFLICT ... DO UPDATE``) means the
    last writer wins, regenerating the password hash.  This is
    harmless because CLI tokens skip ``pwd_sig`` validation and
    the random plaintext is never persisted.

    The system user receives a random Argon2id password hash
    generated from 64 bytes of ``os.urandom``.  Nobody knows the
    plaintext, preventing login via ``/auth/login``.

    Args:
        persistence: Connected persistence backend.
        auth_service: Authentication service for password hashing.
    """
    existing = await persistence.users.get(SYSTEM_USER_ID)
    if existing is not None:
        logger.debug(
            API_AUTH_SYSTEM_USER_ENSURED,
            action="already_exists",
        )
        return

    # Generate a random password nobody will ever know.
    random_password = os.urandom(64).hex()
    password_hash = auth_service.hash_password(random_password)

    now = datetime.now(UTC)
    user = User(
        id=SYSTEM_USER_ID,
        username=SYSTEM_USERNAME,
        password_hash=password_hash,
        role=HumanRole.SYSTEM,
        must_change_password=False,
        created_at=now,
        updated_at=now,
    )
    await persistence.users.save(user)
    logger.info(
        API_AUTH_SYSTEM_USER_ENSURED,
        action="created",
        user_id=SYSTEM_USER_ID,
    )
