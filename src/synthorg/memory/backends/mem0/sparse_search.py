"""Qdrant sparse vector operations for BM25 hybrid search.

Pure functions operating on a ``QdrantClient`` reference.  These
handle the sparse vector lifecycle: field creation, upsert alongside
dense vectors, and sparse-only retrieval.  Qdrant's ``Modifier.IDF``
applies IDF scoring server-side -- only term frequencies are stored.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from synthorg.core.types import NotBlankStr
from synthorg.memory.models import MemoryEntry, MemoryMetadata
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_SPARSE_FIELD_ENSURED,
    MEMORY_SPARSE_SEARCH_COMPLETE,
    MEMORY_SPARSE_SEARCH_FAILED,
    MEMORY_SPARSE_UPSERT_COMPLETE,
)

if TYPE_CHECKING:
    from synthorg.memory.sparse import SparseVector

logger = get_logger(__name__)

_DEFAULT_FIELD_NAME = "bm25"
_SYNTHORG_PREFIX = "_synthorg_"


def ensure_sparse_field(
    client: Any,
    collection_name: str,
    field_name: str = _DEFAULT_FIELD_NAME,
) -> None:
    """Add a sparse vector field to an existing Qdrant collection.

    Idempotent -- skips if the field already exists.  Uses
    ``Modifier.IDF`` so Qdrant applies IDF scoring server-side.

    Args:
        client: ``QdrantClient`` instance.
        collection_name: Target Qdrant collection.
        field_name: Name for the sparse vector field.
    """
    from qdrant_client import models  # noqa: PLC0415

    info = client.get_collection(collection_name)
    existing_sparse = info.config.params.sparse_vectors
    if existing_sparse is not None and field_name in existing_sparse:
        logger.debug(
            MEMORY_SPARSE_FIELD_ENSURED,
            collection=collection_name,
            field_name=field_name,
            action="skipped",
        )
        return

    client.update_collection(
        collection_name=collection_name,
        sparse_vectors_config={
            field_name: models.SparseVectorParams(
                modifier=models.Modifier.IDF,
            ),
        },
    )
    logger.info(
        MEMORY_SPARSE_FIELD_ENSURED,
        collection=collection_name,
        field_name=field_name,
        action="created",
    )


def upsert_sparse_vector(
    client: Any,
    collection_name: str,
    point_id: str,
    sparse_vector: SparseVector,
    field_name: str = _DEFAULT_FIELD_NAME,
) -> None:
    """Attach a sparse vector to an existing Qdrant point.

    Skips empty vectors silently.  Uses ``update_vectors`` to add
    the sparse field without replacing the existing dense vector.

    Args:
        client: ``QdrantClient`` instance.
        collection_name: Target Qdrant collection.
        point_id: UUID of the existing point.
        sparse_vector: BM25 term-frequency sparse vector.
        field_name: Name of the sparse vector field.
    """
    if sparse_vector.is_empty:
        return

    from qdrant_client import models  # noqa: PLC0415

    client.update_vectors(
        collection_name=collection_name,
        points=[
            models.PointVectors(
                id=point_id,
                vector={
                    field_name: models.SparseVector(
                        indices=list(sparse_vector.indices),
                        values=list(sparse_vector.values),
                    ),
                },
            ),
        ],
    )
    logger.debug(
        MEMORY_SPARSE_UPSERT_COMPLETE,
        collection=collection_name,
        point_id=point_id,
        num_terms=len(sparse_vector.indices),
    )


def search_sparse(  # noqa: PLR0913
    client: Any,
    collection_name: str,
    query_vector: SparseVector,
    *,
    user_id_filter: str,
    limit: int,
    field_name: str = _DEFAULT_FIELD_NAME,
) -> list[Any]:
    """Query the sparse vector field for BM25 matches.

    Args:
        client: ``QdrantClient`` instance.
        collection_name: Target Qdrant collection.
        query_vector: BM25-encoded query sparse vector.
        user_id_filter: Filter results to this agent's points.
        limit: Maximum results to return.
        field_name: Name of the sparse vector field.

    Returns:
        List of Qdrant ``ScoredPoint`` objects.
    """
    if query_vector.is_empty:
        return []

    from qdrant_client import models  # noqa: PLC0415

    result = client.query_points(
        collection_name=collection_name,
        query=models.SparseVector(
            indices=list(query_vector.indices),
            values=list(query_vector.values),
        ),
        using=field_name,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id_filter),
                ),
            ],
        ),
        limit=limit,
    )

    logger.debug(
        MEMORY_SPARSE_SEARCH_COMPLETE,
        collection=collection_name,
        user_id=user_id_filter,
        num_results=len(result.points),
    )

    return list(result.points)


def scored_points_to_entries(
    points: list[Any],
    agent_id: NotBlankStr,
) -> tuple[MemoryEntry, ...]:
    """Map Qdrant ``ScoredPoint`` objects to ``MemoryEntry`` instances.

    Skips points with malformed payloads rather than failing the
    entire batch.  Scores are clamped to [0.0, 1.0] for consistency
    with the ranking pipeline.

    Args:
        points: Qdrant scored points from sparse search.
        agent_id: Agent identifier for the entries.

    Returns:
        Tuple of memory entries with relevance scores set.
    """
    entries: list[MemoryEntry] = []
    for point in points:
        try:
            entry = _point_to_entry(point, agent_id)
            entries.append(entry)
        except Exception:
            logger.warning(
                MEMORY_SPARSE_SEARCH_FAILED,
                point_id=str(getattr(point, "id", "unknown")),
                reason="malformed payload",
                exc_info=True,
            )
    return tuple(entries)


def _point_to_entry(point: Any, agent_id: NotBlankStr) -> MemoryEntry:
    """Convert a single Qdrant point to a MemoryEntry."""
    from synthorg.core.enums import MemoryCategory  # noqa: PLC0415

    payload = point.payload
    metadata_raw = payload.get("metadata", {})

    category_str = metadata_raw.get(f"{_SYNTHORG_PREFIX}category", "episodic")
    try:
        category = MemoryCategory(category_str)
    except ValueError:
        category = MemoryCategory.EPISODIC

    confidence = metadata_raw.get(f"{_SYNTHORG_PREFIX}confidence", 1.0)
    source = metadata_raw.get(f"{_SYNTHORG_PREFIX}source")
    tags_raw = metadata_raw.get(f"{_SYNTHORG_PREFIX}tags", [])
    tags = tuple(NotBlankStr(t) for t in tags_raw if t and str(t).strip())

    content = payload.get("data") or payload.get("memory", "")
    created_str = payload.get("created_at")
    created_at = (
        datetime.fromisoformat(created_str) if created_str else datetime.now(UTC)
    )

    score = min(1.0, max(0.0, float(point.score))) if point.score else None

    return MemoryEntry(
        id=NotBlankStr(str(point.id)),
        agent_id=agent_id,
        category=category,
        content=NotBlankStr(content) if content else NotBlankStr("(empty)"),
        metadata=MemoryMetadata(
            confidence=confidence,
            source=NotBlankStr(source) if source else None,
            tags=tags,
        ),
        created_at=created_at,
        relevance_score=score,
    )
