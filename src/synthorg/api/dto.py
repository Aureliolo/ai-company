"""Request/response DTOs and envelope models.

Response envelopes wrap all API responses in a consistent structure.
Request DTOs define write-operation payloads (separate from domain
models because they omit server-generated fields).
"""

import re
from typing import Self
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from synthorg.api.errors import ErrorCategory, ErrorCode  # noqa: TC001
from synthorg.budget.currency import DEFAULT_CURRENCY
from synthorg.config.schema import ProviderConfig, ProviderModelConfig  # noqa: TC001
from synthorg.core.enums import (
    ApprovalRiskLevel,
    Complexity,
    Priority,
    TaskStatus,
    TaskType,
)
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.core.validation import is_valid_action_type
from synthorg.providers.enums import AuthType

DEFAULT_LIMIT: int = 50
MAX_LIMIT: int = 200

_MAX_METADATA_KEYS: int = 20
_MAX_METADATA_STR_LEN: int = 256


# ── Structured error detail (RFC 9457) ─────────────────────────


def _check_retry_after(*, retryable: bool, retry_after: int | None) -> None:
    """Validate ``retry_after``/``retryable`` consistency.

    Shared by ``ErrorDetail`` and ``ProblemDetail``.
    """
    if not retryable and retry_after is not None:
        msg = "retry_after must be None when retryable is False"
        raise ValueError(msg)


class ErrorDetail(BaseModel):
    """Structured error metadata (RFC 9457).

    Self-contained so agents can parse it without referencing
    the parent envelope.

    Attributes:
        detail: Human-readable occurrence-specific explanation.
        error_code: Machine-readable error code (by convention, 4-digit
            category-grouped; see ``ErrorCode``).
        error_category: High-level error category.
        retryable: Whether the client should retry the request.
        retry_after: Seconds to wait before retrying (``None``
            when not applicable).
        instance: Request correlation ID for log tracing.
        title: Static per-category title (e.g. "Authentication Error").
        type: Documentation URI for the error category.
    """

    model_config = ConfigDict(frozen=True)

    detail: NotBlankStr
    error_code: ErrorCode
    error_category: ErrorCategory
    retryable: bool = False
    retry_after: int | None = Field(default=None, ge=0)
    instance: NotBlankStr
    title: NotBlankStr
    type: NotBlankStr

    @model_validator(mode="after")
    def _validate_retry_after_consistency(self) -> Self:
        """``retry_after`` must be ``None`` when ``retryable`` is ``False``."""
        _check_retry_after(retryable=self.retryable, retry_after=self.retry_after)
        return self


class ProblemDetail(BaseModel):
    """Bare RFC 9457 ``application/problem+json`` response body.

    Returned when the client sends ``Accept: application/problem+json``.

    Attributes:
        type: Documentation URI for the error category.
        title: Static per-category title.
        status: HTTP status code.
        detail: Human-readable occurrence-specific explanation.
        instance: Request correlation ID for log tracing.
        error_code: Machine-readable 4-digit error code.
        error_category: High-level error category.
        retryable: Whether the client should retry the request.
        retry_after: Seconds to wait before retrying (``None``
            when not applicable).
    """

    model_config = ConfigDict(frozen=True)

    type: NotBlankStr
    title: NotBlankStr
    status: int = Field(ge=400, le=599)
    detail: NotBlankStr
    instance: NotBlankStr
    error_code: ErrorCode
    error_category: ErrorCategory
    retryable: bool = False
    retry_after: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_retry_after_consistency(self) -> Self:
        """``retry_after`` must be ``None`` when ``retryable`` is ``False``."""
        _check_retry_after(retryable=self.retryable, retry_after=self.retry_after)
        return self


# ── Response envelopes ──────────────────────────────────────────


class ApiResponse[T](BaseModel):
    """Standard API response envelope.

    Attributes:
        data: Response payload (``None`` on error).
        error: Error message (``None`` on success).
        error_detail: Structured error metadata (``None`` on success).
        success: Whether the request succeeded (computed from ``error``).
    """

    model_config = ConfigDict(frozen=True)

    data: T | None = None
    error: str | None = None
    error_detail: ErrorDetail | None = None

    @model_validator(mode="after")
    def _validate_error_detail_consistency(self) -> Self:
        """``error_detail`` must not appear on a successful response."""
        if self.error_detail is not None and self.error is None:
            msg = "error_detail requires error to be set"
            raise ValueError(msg)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        """Whether the request succeeded (derived from ``error``)."""
        return self.error is None


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses.

    Attributes:
        total: Total number of items matching the query.
        offset: Starting offset of the returned page.
        limit: Maximum items per page.
    """

    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0, description="Total matching items")
    offset: int = Field(ge=0, description="Starting offset")
    limit: int = Field(ge=1, description="Maximum items per page")


class PaginatedResponse[T](BaseModel):
    """Paginated API response envelope.

    Attributes:
        data: Page of items.
        error: Error message (``None`` on success).
        error_detail: Structured error metadata (``None`` on success).
        pagination: Pagination metadata.
        success: Whether the request succeeded (computed from ``error``).
    """

    model_config = ConfigDict(frozen=True)

    data: tuple[T, ...] = ()
    error: str | None = None
    error_detail: ErrorDetail | None = None
    pagination: PaginationMeta

    @model_validator(mode="after")
    def _validate_error_detail_consistency(self) -> Self:
        """Ensure ``error`` and ``error_detail`` are set together."""
        if self.error_detail is not None and self.error is None:
            msg = "error_detail requires error to be set"
            raise ValueError(msg)
        if self.error is not None and self.error_detail is None:
            msg = "error must be accompanied by error_detail"
            raise ValueError(msg)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        """Whether the request succeeded (derived from ``error``)."""
        return self.error is None


# ── Task request DTOs ───────────────────────────────────────────


class CreateTaskRequest(BaseModel):
    """Payload for creating a new task.

    Attributes:
        title: Short task title.
        description: Detailed task description.
        type: Task work type.
        priority: Task priority level.
        project: Project ID.
        created_by: Agent name of the creator.
        assigned_to: Optional assignee agent ID.
        estimated_complexity: Complexity estimate.
        budget_limit: Maximum spend in USD (base currency).
    """

    model_config = ConfigDict(frozen=True)

    title: NotBlankStr = Field(max_length=256)
    description: NotBlankStr = Field(max_length=4096)
    type: TaskType
    priority: Priority = Priority.MEDIUM
    project: NotBlankStr
    created_by: NotBlankStr
    assigned_to: NotBlankStr | None = None
    estimated_complexity: Complexity = Complexity.MEDIUM
    budget_limit: float = Field(default=0.0, ge=0.0)


class UpdateTaskRequest(BaseModel):
    """Payload for updating task fields.

    All fields are optional -- only provided fields are updated.

    Attributes:
        title: New title.
        description: New description.
        priority: New priority.
        assigned_to: New assignee.
        budget_limit: New budget limit.
        expected_version: Optimistic concurrency guard.
    """

    model_config = ConfigDict(frozen=True)

    title: NotBlankStr | None = Field(default=None, max_length=256)
    description: NotBlankStr | None = Field(default=None, max_length=4096)
    priority: Priority | None = None
    assigned_to: NotBlankStr | None = None
    budget_limit: float | None = Field(default=None, ge=0.0)
    expected_version: int | None = Field(
        default=None,
        ge=1,
        description="Optimistic concurrency version guard",
    )


class TransitionTaskRequest(BaseModel):
    """Payload for a task status transition.

    Attributes:
        target_status: The desired target status.
        assigned_to: Optional assignee override for the transition.
        expected_version: Optimistic concurrency guard.
    """

    model_config = ConfigDict(frozen=True)

    target_status: TaskStatus = Field(description="Desired target status")
    assigned_to: NotBlankStr | None = None
    expected_version: int | None = Field(
        default=None,
        ge=1,
        description="Optimistic concurrency version guard",
    )


class CancelTaskRequest(BaseModel):
    """Payload for cancelling a task.

    Attributes:
        reason: Reason for cancellation.
    """

    model_config = ConfigDict(frozen=True)

    reason: NotBlankStr = Field(
        max_length=4096,
        description="Reason for cancellation",
    )


# ── Approval request DTOs ──────────────────────────────────────


class CreateApprovalRequest(BaseModel):
    """Payload for creating a new approval item.

    Attributes:
        action_type: Kind of action requiring approval
            (``category:action`` format).
        title: Short summary.
        description: Detailed explanation.
        risk_level: Assessed risk level.
        ttl_seconds: Optional time-to-live in seconds
            (min 60, max 604 800 = 7 days).
        task_id: Optional associated task.
        metadata: Additional key-value pairs.
    """

    model_config = ConfigDict(frozen=True)

    action_type: NotBlankStr = Field(max_length=128)
    title: NotBlankStr = Field(max_length=256)
    description: NotBlankStr = Field(max_length=4096)
    risk_level: ApprovalRiskLevel
    ttl_seconds: int | None = Field(default=None, ge=60, le=604800)
    task_id: NotBlankStr | None = Field(default=None, max_length=128)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("action_type")
    @classmethod
    def _validate_action_type_format(cls, v: str) -> str:
        if not is_valid_action_type(v):
            msg = "action_type must use 'category:action' format"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _validate_metadata_bounds(self) -> Self:
        """Limit metadata size to prevent memory abuse."""
        if len(self.metadata) > _MAX_METADATA_KEYS:
            msg = f"metadata must have at most {_MAX_METADATA_KEYS} keys"
            raise ValueError(msg)
        for k, v in self.metadata.items():
            if len(k) > _MAX_METADATA_STR_LEN:
                msg = f"metadata key must be at most {_MAX_METADATA_STR_LEN} characters"
                raise ValueError(msg)
            if len(v) > _MAX_METADATA_STR_LEN:
                msg = (
                    f"metadata value must be at most {_MAX_METADATA_STR_LEN} characters"
                )
                raise ValueError(msg)
        return self


class ApproveRequest(BaseModel):
    """Payload for approving an approval item.

    Attributes:
        comment: Optional comment explaining the approval.
    """

    model_config = ConfigDict(frozen=True)

    comment: NotBlankStr | None = Field(default=None, max_length=4096)


class RejectRequest(BaseModel):
    """Payload for rejecting an approval item.

    Attributes:
        reason: Mandatory reason for rejection.
    """

    model_config = ConfigDict(frozen=True)

    reason: NotBlankStr = Field(max_length=4096)


# ── Coordination request/response DTOs ────────────────────────


class CoordinateTaskRequest(BaseModel):
    """Payload for triggering multi-agent coordination on a task.

    Attributes:
        agent_names: Agent names to coordinate with (``None`` = all active).
            When provided, must be non-empty and unique.
        max_subtasks: Maximum subtasks for decomposition.
        max_concurrency_per_wave: Override for max concurrency per wave.
        fail_fast: Override for fail-fast behaviour (``None`` = use
            section config default).
    """

    model_config = ConfigDict(frozen=True)

    agent_names: tuple[NotBlankStr, ...] | None = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="Agent names to coordinate with (None = all active)",
    )
    max_subtasks: int = Field(default=10, ge=1, le=50)
    max_concurrency_per_wave: int | None = Field(
        default=None,
        ge=1,
        le=50,
    )
    fail_fast: bool | None = None

    @model_validator(mode="after")
    def _validate_unique_agent_names(self) -> Self:
        """Reject duplicate agent names."""
        if self.agent_names is not None:
            seen: set[str] = set()
            for name in self.agent_names:
                lower = name.lower()
                if lower in seen:
                    msg = f"Duplicate agent name: {name!r}"
                    raise ValueError(msg)
                seen.add(lower)
        return self


class CoordinationPhaseResponse(BaseModel):
    """Response model for a single coordination phase.

    Attributes:
        phase: Phase name.
        success: Whether the phase completed successfully.
        duration_seconds: Wall-clock duration of the phase.
        error: Error description if the phase failed.
    """

    model_config = ConfigDict(frozen=True)

    phase: NotBlankStr
    success: bool
    duration_seconds: float = Field(ge=0.0)
    error: NotBlankStr | None = None

    @model_validator(mode="after")
    def _validate_success_error_consistency(self) -> Self:
        """Ensure success and error fields are consistent."""
        if self.success and self.error is not None:
            msg = "successful phase must not have an error"
            raise ValueError(msg)
        if not self.success and self.error is None:
            msg = "failed phase must have an error description"
            raise ValueError(msg)
        return self


class CoordinationResultResponse(BaseModel):
    """Response model for a complete coordination run.

    Attributes:
        parent_task_id: ID of the parent task.
        topology: Resolved coordination topology.
        total_duration_seconds: Total wall-clock duration.
        total_cost_usd: Total cost across all waves.
        phases: Phase results in execution order.
        wave_count: Number of execution waves.
        is_success: Whether all phases succeeded (computed).
    """

    model_config = ConfigDict(frozen=True)

    parent_task_id: NotBlankStr = Field(max_length=128)
    topology: NotBlankStr
    total_duration_seconds: float = Field(ge=0.0)
    total_cost_usd: float = Field(ge=0.0)
    currency: str = Field(
        default=DEFAULT_CURRENCY,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )
    phases: tuple[CoordinationPhaseResponse, ...] = Field(min_length=1)
    wave_count: int = Field(ge=0)

    @computed_field(  # type: ignore[prop-decorator]
        description="Whether all phases succeeded",
    )
    @property
    def is_success(self) -> bool:
        """True when every phase completed successfully."""
        return all(p.success for p in self.phases)


# ── Provider management DTOs ────────────────────────────────

_PROVIDER_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")
_RESERVED_PROVIDER_NAMES: frozenset[str] = frozenset(
    {"presets", "from-preset", "probe-preset", "discovery-policy"},
)


def _validate_provider_name(v: str) -> str:
    """Validate a provider name against naming rules.

    Args:
        v: Candidate provider name.

    Returns:
        The validated name.

    Raises:
        ValueError: If the name is invalid or reserved.
    """
    if not _PROVIDER_NAME_PATTERN.match(v):
        msg = (
            "Provider name must be 2-64 chars, lowercase "
            "alphanumeric and hyphens, starting/ending with "
            "alphanumeric"
        )
        raise ValueError(msg)
    if v in _RESERVED_PROVIDER_NAMES:
        msg = f"Provider name {v!r} is reserved"
        raise ValueError(msg)
    return v


def _validate_base_url(v: str | None) -> str | None:
    """Validate that a base URL uses http or https scheme."""
    if v is None:
        return v
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https"):
        msg = f"base_url must use http or https scheme, got {parsed.scheme!r}"
        raise ValueError(msg)
    if not parsed.netloc:
        msg = "base_url must include a host"
        raise ValueError(msg)
    return v


class CreateProviderRequest(BaseModel):
    """Payload for creating a new provider.

    Attributes:
        name: Unique provider name (2-64 chars, lowercase alphanumeric + hyphens).
        driver: Driver backend name (default ``"litellm"``).
        litellm_provider: LiteLLM routing identifier override.
        auth_type: Authentication mechanism for this provider.
        api_key: API key credential (optional, depends on auth_type).
        subscription_token: Bearer token for subscription-based auth.
        tos_accepted: Whether the user accepted the subscription ToS warning.
        base_url: Provider API base URL.
        models: Pre-configured model definitions.
    """

    model_config = ConfigDict(frozen=True)

    name: NotBlankStr = Field(max_length=64)
    driver: NotBlankStr = "litellm"
    litellm_provider: NotBlankStr | None = None
    auth_type: AuthType = AuthType.API_KEY
    api_key: NotBlankStr | None = None
    subscription_token: NotBlankStr | None = None
    tos_accepted: bool = False
    base_url: NotBlankStr | None = None
    oauth_token_url: NotBlankStr | None = None
    oauth_client_id: NotBlankStr | None = None
    oauth_client_secret: NotBlankStr | None = None
    oauth_scope: NotBlankStr | None = None
    custom_header_name: NotBlankStr | None = None
    custom_header_value: NotBlankStr | None = None
    models: tuple[ProviderModelConfig, ...] = ()

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return _validate_provider_name(v)

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str | None) -> str | None:
        return _validate_base_url(v)


class UpdateProviderRequest(BaseModel):
    """Payload for updating a provider (partial update).

    All fields are optional -- only provided fields are updated.
    ``tos_accepted``: only ``True`` re-stamps the timestamp;
    ``False`` and ``None`` are no-ops (acceptance cannot be retracted).
    """

    model_config = ConfigDict(frozen=True)

    driver: NotBlankStr | None = None
    litellm_provider: NotBlankStr | None = None
    auth_type: AuthType | None = None
    api_key: NotBlankStr | None = None
    clear_api_key: bool = False
    subscription_token: NotBlankStr | None = None
    clear_subscription_token: bool = False
    tos_accepted: bool | None = None
    base_url: NotBlankStr | None = None
    oauth_token_url: NotBlankStr | None = None
    oauth_client_id: NotBlankStr | None = None
    oauth_client_secret: NotBlankStr | None = None
    oauth_scope: NotBlankStr | None = None
    custom_header_name: NotBlankStr | None = None
    custom_header_value: NotBlankStr | None = None
    models: tuple[ProviderModelConfig, ...] | None = None

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str | None) -> str | None:
        return _validate_base_url(v)

    @model_validator(mode="after")
    def _validate_credential_clear_consistency(self) -> Self:
        """Reject simultaneous set and clear for credential fields."""
        if self.api_key is not None and self.clear_api_key:
            msg = "api_key and clear_api_key are mutually exclusive"
            raise ValueError(msg)
        if self.subscription_token is not None and self.clear_subscription_token:
            msg = (
                "subscription_token and clear_subscription_token are mutually exclusive"
            )
            raise ValueError(msg)
        return self


class TestConnectionRequest(BaseModel):
    """Payload for testing a provider connection.

    Attributes:
        model: Model to test (defaults to first model in config).
    """

    model_config = ConfigDict(frozen=True)

    model: NotBlankStr | None = None


class TestConnectionResponse(BaseModel):
    """Result of a provider connection test.

    Attributes:
        success: Whether the connection test succeeded.
        latency_ms: Round-trip latency in milliseconds.
        error: Error message on failure.
        model_tested: Model ID that was tested.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    latency_ms: float | None = None
    error: NotBlankStr | None = None
    model_tested: NotBlankStr | None = None

    @model_validator(mode="after")
    def _validate_success_error_consistency(self) -> Self:
        """Ensure success and error fields are consistent."""
        if self.success and self.error is not None:
            msg = "successful test must not have an error"
            raise ValueError(msg)
        if not self.success and self.error is None:
            msg = "failed test must have an error message"
            raise ValueError(msg)
        return self


class ProviderResponse(BaseModel):
    """Safe provider config for API responses -- secrets stripped.

    Non-secret auth fields are included for frontend edit form UX.
    Boolean ``has_*`` indicators signal credential presence without
    exposing values.

    Attributes:
        driver: Driver backend name.
        litellm_provider: LiteLLM routing identifier override.
        auth_type: Authentication mechanism.
        base_url: Provider API base URL.
        models: Configured model definitions.
        has_api_key: Whether an API key is set.
        has_oauth_credentials: Whether OAuth credentials are configured.
        has_custom_header: Whether a custom auth header is configured.
        has_subscription_token: Whether a subscription token is set.
        tos_accepted_at: ISO timestamp of ToS acceptance (or ``None``).
    """

    model_config = ConfigDict(frozen=True)

    driver: NotBlankStr
    litellm_provider: NotBlankStr | None = None
    auth_type: AuthType
    base_url: NotBlankStr | None
    models: tuple[ProviderModelConfig, ...]
    has_api_key: bool
    has_oauth_credentials: bool
    has_custom_header: bool
    has_subscription_token: bool = False
    tos_accepted_at: str | None = None
    oauth_token_url: NotBlankStr | None = None
    oauth_client_id: NotBlankStr | None = None
    oauth_scope: NotBlankStr | None = None
    custom_header_name: NotBlankStr | None = None


class CreateFromPresetRequest(BaseModel):
    """Payload for creating a provider from a preset.

    Attributes:
        preset_name: Name of the preset to create from.
        name: Unique provider name (2-64 chars, lowercase alphanumeric + hyphens).
        auth_type: Override the preset's default auth type (optional).
        subscription_token: Bearer token for subscription-based auth.
        tos_accepted: Whether the user accepted the subscription ToS warning.
        base_url: Override the preset's default base URL (optional).
    """

    model_config = ConfigDict(frozen=True)

    preset_name: NotBlankStr
    name: NotBlankStr = Field(max_length=64)
    auth_type: AuthType | None = None
    api_key: NotBlankStr | None = None
    subscription_token: NotBlankStr | None = None
    tos_accepted: bool = False
    base_url: NotBlankStr | None = None
    models: tuple[ProviderModelConfig, ...] | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return _validate_provider_name(v)

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str | None) -> str | None:
        return _validate_base_url(v)


class DiscoverModelsResponse(BaseModel):
    """Result of provider model auto-discovery.

    Attributes:
        discovered_models: Models found on the provider endpoint.
        provider_name: Name of the provider that was queried.
    """

    model_config = ConfigDict(frozen=True)

    discovered_models: tuple[ProviderModelConfig, ...]
    provider_name: NotBlankStr


class ProbePresetRequest(BaseModel):
    """Request to probe a preset's candidate URLs for reachability.

    Attributes:
        preset_name: Preset identifier to probe.
    """

    model_config = ConfigDict(frozen=True)

    preset_name: NotBlankStr = Field(max_length=64)


class ProbePresetResponse(BaseModel):
    """Result of probing a preset's candidate URLs.

    Attributes:
        url: The first reachable base URL, or ``None`` if none responded.
        model_count: Number of models discovered at the URL.
        candidates_tried: Number of candidate URLs attempted.
    """

    model_config = ConfigDict(frozen=True)

    url: NotBlankStr | None = None
    model_count: int = Field(default=0, ge=0)
    candidates_tried: int = Field(default=0, ge=0)


def to_provider_response(config: ProviderConfig) -> ProviderResponse:
    """Convert a ProviderConfig to a safe ProviderResponse.

    Strips all secrets and provides boolean credential indicators.

    Args:
        config: Provider configuration (may contain secrets).

    Returns:
        Safe response DTO with secrets stripped.
    """
    tos_str = (
        config.tos_accepted_at.isoformat()
        if config.tos_accepted_at is not None
        else None
    )
    return ProviderResponse(
        driver=config.driver,
        litellm_provider=config.litellm_provider,
        auth_type=config.auth_type,
        base_url=config.base_url,
        models=config.models,
        has_api_key=config.api_key is not None,
        has_oauth_credentials=(
            config.oauth_client_id is not None
            and config.oauth_client_secret is not None
            and config.oauth_token_url is not None
        ),
        has_custom_header=(
            config.custom_header_name is not None
            and config.custom_header_value is not None
        ),
        has_subscription_token=config.subscription_token is not None,
        tos_accepted_at=tos_str,
        oauth_token_url=config.oauth_token_url,
        oauth_client_id=config.oauth_client_id,
        oauth_scope=config.oauth_scope,
        custom_header_name=config.custom_header_name,
    )
