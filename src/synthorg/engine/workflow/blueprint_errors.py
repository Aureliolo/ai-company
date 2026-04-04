"""Blueprint-specific error types."""


class BlueprintNotFoundError(Exception):
    """Raised when a workflow blueprint cannot be found."""


class BlueprintValidationError(Exception):
    """Raised when a blueprint YAML fails schema validation."""
