"""OntologyBackend protocol -- re-exported from the persistence layer.

Canonical definition now lives at
``synthorg.persistence.ontology_protocol``; this shim keeps existing
imports working while the rest of the subsystem is folded in.
Lifecycle methods (connect/disconnect/health_check/is_connected/
get_db) have moved to :class:`PersistenceBackend`.
"""

from synthorg.persistence.ontology_protocol import (
    OntologyBackend,
    OntologyDriftReportRepository,
    OntologyEntityRepository,
)

__all__ = [
    "OntologyBackend",
    "OntologyDriftReportRepository",
    "OntologyEntityRepository",
]
