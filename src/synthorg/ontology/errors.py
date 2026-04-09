"""Ontology subsystem error hierarchy."""


class OntologyError(Exception):
    """Base exception for all ontology errors."""


class OntologyConnectionError(OntologyError):
    """Backend connection management failed."""


class OntologyNotFoundError(OntologyError):
    """Requested entity definition does not exist."""


class OntologyDuplicateError(OntologyError):
    """Entity definition with duplicate name."""


class OntologyConfigError(OntologyError):
    """Ontology configuration is invalid."""
