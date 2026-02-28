"""Custom exception hierarchy for template errors."""

from ai_company.config.errors import ConfigError, ConfigLocation


class TemplateError(ConfigError):
    """Base exception for template errors."""


class TemplateNotFoundError(TemplateError):
    """Raised when a template cannot be found."""


class TemplateRenderError(TemplateError):
    """Raised when Jinja2 rendering fails or a required variable is missing."""


class TemplateValidationError(TemplateError):
    """Raised when a rendered template fails validation.

    Attributes:
        field_errors: Per-field error messages as
            ``(key_path, message)`` pairs.
    """

    def __init__(
        self,
        message: str,
        locations: tuple[ConfigLocation, ...] = (),
        field_errors: tuple[tuple[str, str], ...] = (),
    ) -> None:
        super().__init__(message, locations)
        self.field_errors = field_errors
