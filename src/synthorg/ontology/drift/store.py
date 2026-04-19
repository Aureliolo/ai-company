"""Drift report store protocol and SQLite re-export.

Canonical definitions now live in the persistence layer:

- Protocol:  ``synthorg.persistence.ontology_protocol.OntologyDriftReportRepository``
- SQLite:    ``synthorg.persistence.sqlite.ontology_drift_repo``
- Postgres:  ``synthorg.persistence.postgres.ontology_drift_repo``

This shim keeps existing import paths working while callers migrate
to the new locations.
"""

from synthorg.persistence.ontology_protocol import (
    OntologyDriftReportRepository as DriftReportStore,
)
from synthorg.persistence.sqlite.ontology_drift_repo import (
    SQLiteOntologyDriftReportRepository as SQLiteDriftReportStore,
)

__all__ = ["DriftReportStore", "SQLiteDriftReportStore"]
