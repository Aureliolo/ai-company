"""Content hash computation for versioned Pydantic models.

Produces a deterministic SHA-256 hex digest from the canonical JSON
serialization of any frozen Pydantic model.  The hash is stable across:

- Field definition order changes (``json.dumps(sort_keys=True)``)
- Pydantic model dump mode (``mode="json"`` gives serializable primitives)
- UUID, date, enum representations (stable under ``mode="json"``)

The same technique is used in ``security/service.py`` for argument
deduplication.
"""

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel


def compute_content_hash(model: BaseModel) -> str:
    """Compute the SHA-256 hex digest of a Pydantic model's canonical JSON.

    The digest is deterministic: identical field values always produce
    the same hash regardless of field definition order in the class.

    Args:
        model: Any Pydantic model instance.

    Returns:
        A 64-character lowercase hexadecimal SHA-256 digest string.
    """
    canonical = json.dumps(
        model.model_dump(mode="json"),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
