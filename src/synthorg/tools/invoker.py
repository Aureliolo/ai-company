"""Tool invoker -- validates and executes tool calls.

Bridges LLM ``ToolCall`` objects with concrete ``BaseTool.execute``
methods.  Recoverable errors are returned as ``ToolResult(is_error=True)``;
non-recoverable errors (``MemoryError``, ``RecursionError``) are logged and
re-raised.  ``BaseException`` subclasses (``KeyboardInterrupt``,
``SystemExit``, ``asyncio.CancelledError``) propagate uncaught.
"""

import asyncio
import copy
from contextlib import nullcontext
from typing import TYPE_CHECKING, Never

import jsonschema
from referencing import Registry as JsonSchemaRegistry
from referencing.exceptions import NoSuchResource

from synthorg.core.enums import ApprovalRiskLevel
from synthorg.observability import get_logger
from synthorg.observability.events.security import (
    SECURITY_INTERCEPTOR_ERROR,
    SECURITY_OUTPUT_SCAN_ERROR,
)
from synthorg.observability.events.tool import (
    TOOL_INVOKE_ALL_COMPLETE,
    TOOL_INVOKE_ALL_START,
    TOOL_INVOKE_DEEPCOPY_ERROR,
    TOOL_INVOKE_EXECUTION_ERROR,
    TOOL_INVOKE_NON_RECOVERABLE,
    TOOL_INVOKE_NOT_FOUND,
    TOOL_INVOKE_PARAMETER_ERROR,
    TOOL_INVOKE_SCHEMA_ERROR,
    TOOL_INVOKE_START,
    TOOL_INVOKE_SUCCESS,
    TOOL_INVOKE_TOOL_ERROR,
    TOOL_INVOKE_VALIDATION_UNEXPECTED,
    TOOL_PERMISSION_DENIED,
    TOOL_SECURITY_DENIED,
    TOOL_SECURITY_ESCALATED,
)
from synthorg.providers.models import ToolCall, ToolResult
from synthorg.security.models import SecurityContext, SecurityVerdictType

from .base import ToolExecutionResult
from .errors import ToolExecutionError, ToolNotFoundError, ToolParameterError
from .invocation_bridge import record_tool_invocation
from .scan_result_handler import handle_sensitive_scan

if TYPE_CHECKING:
    from collections.abc import Iterable

    from synthorg.core.tool_disclosure import ToolL1Metadata, ToolL2Body, ToolL3Resource
    from synthorg.engine.approval_gate_models import EscalationInfo
    from synthorg.providers.models import ToolDefinition
    from synthorg.security.protocol import SecurityInterceptionStrategy
    from synthorg.tools.html_parse_guard import HTMLParseGuard

    from .base import BaseTool
    from .invocation_tracker import ToolInvocationTracker
    from .permissions import ToolPermissionChecker
    from .registry import ToolRegistry

logger = get_logger(__name__)


def _no_remote_retrieve(uri: str) -> Never:
    """Block remote ``$ref`` resolution to prevent SSRF."""
    raise NoSuchResource(uri)


_SAFE_REGISTRY: JsonSchemaRegistry = JsonSchemaRegistry(  # type: ignore[call-arg]
    retrieve=_no_remote_retrieve,
)


class ToolInvoker:
    """Validate parameters, enforce security policies, and execute tools.

    Recoverable errors are returned as ``ToolResult(is_error=True)``.
    Non-recoverable errors (``MemoryError``, ``RecursionError``) are
    re-raised after logging.

    Examples:
        Invoke a single tool call::

            invoker = ToolInvoker(registry)
            result = await invoker.invoke(tool_call)

        Invoke multiple tool calls concurrently::

            results = await invoker.invoke_all(tool_calls)

        Limit concurrency::

            results = await invoker.invoke_all(tool_calls, max_concurrency=3)
    """

    def __init__(  # noqa: PLR0913
        self,
        registry: ToolRegistry,
        *,
        permission_checker: ToolPermissionChecker | None = None,
        security_interceptor: SecurityInterceptionStrategy | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
        agent_provider_name: str | None = None,
        invocation_tracker: ToolInvocationTracker | None = None,
    ) -> None:
        """Initialize with a tool registry and optional checkers.

        Args:
            registry: Registry to look up tools from.
            permission_checker: Optional checker for access-level gating.
                When ``None``, all registered tools are permitted.
            security_interceptor: Optional pre/post-tool security layer.
            agent_id: Agent ID for security context.
            task_id: Task ID for security context.
            agent_provider_name: Provider name the agent is using,
                for cross-family LLM security evaluation.
            invocation_tracker: Optional tracker for recording
                invocations for the activity timeline.
        """
        self._registry = registry
        self._permission_checker = permission_checker
        self._security_interceptor = security_interceptor
        self._agent_id = agent_id
        self._task_id = task_id
        self._agent_provider_name = agent_provider_name
        self._invocation_tracker = invocation_tracker

        self._pending_escalations: list[EscalationInfo] = []
        self._html_guard: HTMLParseGuard | None = None

    @property
    def registry(self) -> ToolRegistry:
        """Read-only access to the underlying tool registry."""
        return self._registry

    @property
    def pending_escalations(self) -> tuple[EscalationInfo, ...]:
        """Escalations detected during the most recent invoke/invoke_all.

        Populated when a security ESCALATE verdict with a non-``None``
        ``approval_id`` is returned, or when a tool returns
        ``requires_parking`` metadata.  Cleared at the start of every
        ``invoke()`` and ``invoke_all()`` call.
        """
        return tuple(self._pending_escalations)

    def get_permitted_definitions(self) -> tuple[ToolDefinition, ...]:
        """Return tool definitions filtered by the permission checker.

        When no permission checker is set, returns all definitions.

        Returns:
            Tuple of permitted tool definitions, sorted by name.
        """
        if self._permission_checker is None:
            return self._registry.to_definitions()
        return self._permission_checker.filter_definitions(self._registry)

    def get_l1_summaries(self) -> tuple[ToolL1Metadata, ...]:
        """Return L1 metadata for all permitted tools.

        For system prompt injection -- lightweight summaries that
        let the agent discover available tools without loading
        full definitions.  Malformed tools are logged and skipped.

        Returns:
            Sorted tuple of L1 metadata for permitted tools.
        """
        from synthorg.observability.events.tool import (  # noqa: PLC0415
            TOOL_DISCLOSURE_L1_SUMMARY_ERROR,
        )

        result: list[ToolL1Metadata] = []
        for name in self._registry.list_tools():
            try:
                tool = self._registry.get(name)
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    TOOL_DISCLOSURE_L1_SUMMARY_ERROR,
                    tool_name=name,
                    note="registry lookup failed during L1 summary",
                    exc_info=True,
                )
                continue
            if (
                self._permission_checker is not None
                and not self._permission_checker.is_permitted(name, tool.category)
            ):
                continue
            try:
                result.append(tool.to_l1_metadata())
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    TOOL_DISCLOSURE_L1_SUMMARY_ERROR,
                    tool_name=name,
                    note="to_l1_metadata() failed",
                    exc_info=True,
                )
        result.sort(key=lambda m: m.name)
        return tuple(result)

    def get_loaded_definitions(
        self,
        loaded_tools: frozenset[str],
    ) -> tuple[ToolDefinition, ...]:
        """Return full definitions for loaded tools + discovery tools.

        Only tools in ``loaded_tools`` get their full
        ``ToolDefinition`` (with L2 body) included.  The three
        discovery tools (``list_tools``, ``load_tool``,
        ``load_tool_resource``) are always included.

        Args:
            loaded_tools: Tool names with L2 active.

        Returns:
            Sorted tuple of full definitions for loaded and
            discovery tools only.
        """
        from .discovery import _DISCOVERY_NAMES  # noqa: PLC0415

        target_names = set(loaded_tools) | _DISCOVERY_NAMES
        included: list[ToolDefinition] = []
        for name in sorted(target_names):
            try:
                tool = self._registry.get(name)
            except ToolNotFoundError:
                continue
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    TOOL_INVOKE_NOT_FOUND,
                    tool_name=name,
                    note="unexpected error during loaded definition lookup",
                    exc_info=True,
                )
                continue
            # Discovery tools bypass permission checks
            if name not in _DISCOVERY_NAMES and (
                self._permission_checker is not None
                and not self._permission_checker.is_permitted(name, tool.category)
            ):
                continue
            try:
                included.append(tool.to_definition())
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    TOOL_INVOKE_NOT_FOUND,
                    tool_name=name,
                    note="to_definition() failed during loaded definition lookup",
                    exc_info=True,
                )
        return tuple(included)

    # ── ToolDisclosureManager protocol ────────────────────────────

    def get_l2_body(self, tool_name: str) -> ToolL2Body | None:
        """Return L2 body for a specific permitted tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            The L2 body, or ``None`` if the tool is not found
            or not permitted.
        """
        try:
            tool = self._registry.get(tool_name)
        except ToolNotFoundError:
            logger.debug(
                TOOL_INVOKE_NOT_FOUND,
                tool_name=tool_name,
                note="tool not found during L2 disclosure query",
            )
            return None
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                TOOL_INVOKE_NOT_FOUND,
                tool_name=tool_name,
                note="unexpected error during disclosure lookup",
                exc_info=True,
            )
            return None
        if (
            self._permission_checker is not None
            and not self._permission_checker.is_permitted(tool_name, tool.category)
        ):
            logger.debug(
                TOOL_PERMISSION_DENIED,
                tool_name=tool_name,
                note="permission denied during L2 disclosure query",
            )
            return None
        try:
            return tool.to_l2_body()
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                TOOL_INVOKE_NOT_FOUND,
                tool_name=tool_name,
                note="to_l2_body() failed during disclosure query",
                exc_info=True,
            )
            return None

    def get_l3_resource(
        self,
        tool_name: str,
        resource_id: str,
    ) -> ToolL3Resource | None:
        """Return a specific L3 resource for a permitted tool.

        Args:
            tool_name: Name of the tool.
            resource_id: Identifier of the resource.

        Returns:
            The L3 resource, or ``None`` if not found or
            not permitted.
        """
        try:
            tool = self._registry.get(tool_name)
        except ToolNotFoundError:
            logger.debug(
                TOOL_INVOKE_NOT_FOUND,
                tool_name=tool_name,
                resource_id=resource_id,
                note="tool not found during L3 disclosure query",
            )
            return None
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                TOOL_INVOKE_NOT_FOUND,
                tool_name=tool_name,
                resource_id=resource_id,
                note="unexpected error during disclosure lookup",
                exc_info=True,
            )
            return None
        if (
            self._permission_checker is not None
            and not self._permission_checker.is_permitted(tool_name, tool.category)
        ):
            logger.debug(
                TOOL_PERMISSION_DENIED,
                tool_name=tool_name,
                resource_id=resource_id,
                note="permission denied during L3 disclosure query",
            )
            return None
        try:
            resources = tool.get_l3_resources()
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                TOOL_INVOKE_NOT_FOUND,
                tool_name=tool_name,
                resource_id=resource_id,
                note="get_l3_resources() failed during disclosure query",
                exc_info=True,
            )
            return None
        return next(
            (r for r in resources if r.resource_id == resource_id),
            None,
        )

    def _check_permission(
        self,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> ToolResult | None:
        """Check tool permission.

        Returns ``None`` if permitted, or a ``ToolResult(is_error=True)``
        if denied.
        """
        if self._permission_checker is None:
            return None
        if self._permission_checker.is_permitted(tool.name, tool.category):
            return None
        reason = self._permission_checker.denial_reason(tool.name, tool.category)
        logger.warning(
            TOOL_PERMISSION_DENIED,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            reason=reason,
        )
        return ToolResult(
            tool_call_id=tool_call.id,
            content=f"Permission denied: {reason}",
            is_error=True,
        )

    def _check_sub_constraints(
        self,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> ToolResult | None:
        """Check granular sub-constraints via the permission checker.

        Returns ``None`` if permitted, or a ``ToolResult`` if denied or
        if the action requires approval (escalation).
        """
        if self._permission_checker is None:
            return None
        safe_args = self._safe_deepcopy_args(tool_call)
        if isinstance(safe_args, ToolResult):
            return safe_args
        violation = self._permission_checker.check_sub_constraints(
            tool.name,
            tool.category,
            tool.action_type,
            safe_args,
        )
        if violation is None:
            return None
        if violation.requires_approval:
            from synthorg.engine.approval_gate_models import (  # noqa: PLC0415
                EscalationInfo,
            )

            approval_id = f"sub-constraint-{tool_call.id}"
            self._pending_escalations.append(
                EscalationInfo(
                    approval_id=approval_id,
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    action_type=tool.action_type,
                    risk_level=ApprovalRiskLevel.HIGH,
                    reason=violation.reason,
                ),
            )
            logger.warning(
                TOOL_SECURITY_ESCALATED,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                reason=violation.reason,
                approval_id=approval_id,
            )
            return ToolResult(
                tool_call_id=tool_call.id,
                content=(
                    f"Sub-constraint escalation: {violation.reason}. "
                    f"Human approval required (id={approval_id})"
                ),
                is_error=True,
            )
        logger.warning(
            TOOL_PERMISSION_DENIED,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            reason=violation.reason,
        )
        return ToolResult(
            tool_call_id=tool_call.id,
            content=f"Sub-constraint denied: {violation.reason}",
            is_error=True,
        )

    def _build_security_context(
        self,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> SecurityContext:
        """Build a ``SecurityContext`` for the given tool call."""
        return SecurityContext(
            tool_name=tool.name,
            tool_category=tool.category,
            action_type=tool.action_type,
            arguments=copy.deepcopy(dict(tool_call.arguments)),
            agent_id=self._agent_id,
            task_id=self._task_id,
            agent_provider_name=self._agent_provider_name,
        )

    async def _check_security(
        self,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> tuple[SecurityContext | None, ToolResult | None]:
        """Run the security interceptor (if any) before execution.

        Builds the ``SecurityContext`` inside the fail-closed handler so
        construction errors are also caught.

        Returns ``(context, None)`` if allowed, or ``(context, ToolResult)``
        if denied/escalated.  Returns ``(None, None)`` when no interceptor.
        """
        if self._security_interceptor is None:
            return None, None
        try:
            context = self._build_security_context(tool, tool_call)
            verdict = await self._security_interceptor.evaluate_pre_tool(
                context,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_INTERCEPTOR_ERROR,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
            )
            return None, ToolResult(
                tool_call_id=tool_call.id,
                content=(
                    "Security evaluation failed (fail-closed). Tool execution blocked."
                ),
                is_error=True,
            )
        if verdict.verdict == SecurityVerdictType.ALLOW:
            return context, None
        if verdict.verdict == SecurityVerdictType.ESCALATE:
            logger.warning(
                TOOL_SECURITY_ESCALATED,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                reason=verdict.reason,
                approval_id=verdict.approval_id,
            )
            if verdict.approval_id is not None:
                from synthorg.engine.approval_gate_models import (  # noqa: PLC0415
                    EscalationInfo,
                )

                self._pending_escalations.append(
                    EscalationInfo(
                        approval_id=verdict.approval_id,
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.name,
                        action_type=tool.action_type,
                        risk_level=verdict.risk_level,
                        reason=verdict.reason,
                    ),
                )
            agent_reason = verdict.agent_visible_reason or verdict.reason
            msg = (
                f"Security escalation: {agent_reason}. "
                f"Approval required (id={verdict.approval_id})"
            )
            return context, ToolResult(
                tool_call_id=tool_call.id,
                content=msg,
                is_error=True,
            )
        # DENY
        logger.warning(
            TOOL_SECURITY_DENIED,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            reason=verdict.reason,
        )
        deny_reason = verdict.agent_visible_reason or verdict.reason
        return context, ToolResult(
            tool_call_id=tool_call.id,
            content=f"Security denied: {deny_reason}",
            is_error=True,
        )

    async def _scan_output(
        self,
        tool_call: ToolCall,
        result: ToolExecutionResult,
        context: SecurityContext,
    ) -> ToolExecutionResult:
        """Scan tool output for sensitive data (if interceptor is set).

        When sensitive data is detected (``has_sensitive_data=True``),
        delegates to ``handle_sensitive_scan`` which branches on
        ``outcome`` (``WITHHELD`` vs ``REDACTED``).  When no sensitive
        data is detected (including ``LOG_ONLY`` and ``CLEAN``
        outcomes), the original output passes through unchanged.

        Scanner exceptions are caught and fail-closed -- a generic error
        result is returned to prevent leaking sensitive data.
        """
        if self._security_interceptor is None:
            return result

        try:
            scan_result = await self._security_interceptor.scan_output(
                context,
                result.content,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                SECURITY_OUTPUT_SCAN_ERROR,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
            )
            return ToolExecutionResult(
                content="Output scan failed (fail-closed). Tool output withheld.",
                is_error=True,
                metadata={**result.metadata, "output_scan_failed": True},
            )

        if scan_result.has_sensitive_data:
            return handle_sensitive_scan(tool_call, result, scan_result)
        return result

    async def invoke(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call.

        Steps:
            1. Look up the tool in the registry.
            2. Check permissions against the permission checker (if any).
            3. Check sub-constraints (network, terminal, git, approval).
            4. Validate arguments against the tool's JSON Schema (if any).
            5. Run security interceptor pre-tool check (if any).
            6. Call ``tool.execute(arguments=...)``.
            7. Scan tool output for sensitive data (if interceptor is set).
            8. Return a ``ToolResult`` with the output.

        Recoverable errors produce ``ToolResult(is_error=True)``.
        Non-recoverable errors are re-raised.

        Args:
            tool_call: The tool call from the LLM.

        Returns:
            A ``ToolResult`` with the tool's output or error message.
        """
        self._pending_escalations.clear()
        return await self._invoke_single(tool_call)

    async def _invoke_single(self, tool_call: ToolCall) -> ToolResult:  # noqa: PLR0911
        """Core invoke logic without clearing escalations.

        Used by both ``invoke`` (after clearing) and ``invoke_all``
        (which clears once at the batch level).
        """
        logger.info(
            TOOL_INVOKE_START,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
        )

        tool_or_error = self._lookup_tool(tool_call)
        if isinstance(tool_or_error, ToolResult):
            return tool_or_error

        permission_error = self._check_permission(tool_or_error, tool_call)
        if permission_error is not None:
            return permission_error

        sub_constraint_error = self._check_sub_constraints(tool_or_error, tool_call)
        if sub_constraint_error is not None:
            return sub_constraint_error

        param_error = self._validate_params(tool_or_error, tool_call)
        if param_error is not None:
            return param_error

        # Build security context inside fail-closed handling.
        security_context, security_error = await self._check_security(
            tool_or_error,
            tool_call,
        )
        if security_error is not None:
            return security_error

        exec_result = await self._execute_tool(tool_or_error, tool_call)
        if isinstance(exec_result, ToolResult):
            return exec_result

        # Sanitize HTML in tool output to strip hidden injection vectors
        # (scripts, styles, display:none elements).  Runs before output
        # scanning so the scanner sees only visible content.
        exec_result = self._apply_html_guard(exec_result)

        # Detect parking metadata from tools like request_human_approval.
        # Returns an error ToolResult if tracking fails, preventing the
        # agent from silently bypassing the approval gate.
        parking_error = self._track_parking_metadata(
            exec_result,
            tool_or_error,
            tool_call,
        )
        if parking_error is not None:
            return parking_error

        if security_context is not None:
            exec_result = await self._scan_output(
                tool_call,
                exec_result,
                security_context,
            )

        result = self._build_result(tool_call, exec_result)
        await record_tool_invocation(self, tool_call, result)
        return result

    def _lookup_tool(self, tool_call: ToolCall) -> BaseTool | ToolResult:
        """Look up a tool in the registry, returning an error on miss."""
        try:
            return self._registry.get(tool_call.name)
        except ToolNotFoundError as exc:
            logger.warning(
                TOOL_INVOKE_NOT_FOUND,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
            )
            return ToolResult(
                tool_call_id=tool_call.id,
                content=str(exc),
                is_error=True,
            )

    def _validate_params(
        self,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> ToolResult | None:
        """Validate tool call arguments against JSON Schema.

        Returns ``None`` on success or a ``ToolResult`` on failure.
        """
        schema = tool.parameters_schema
        if schema is None:
            return None
        try:
            jsonschema.validate(
                instance=dict(tool_call.arguments),
                schema=schema,
                registry=_SAFE_REGISTRY,
            )
        except jsonschema.SchemaError as exc:
            return self._schema_error_result(tool_call, exc.message)
        except jsonschema.ValidationError as exc:
            return self._param_error_result(tool_call, exc.message)
        except (MemoryError, RecursionError) as exc:
            logger.exception(
                TOOL_INVOKE_NON_RECOVERABLE,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        except Exception as exc:
            error_msg = str(exc) or f"{type(exc).__name__} (no message)"
            return self._unexpected_validation_result(tool_call, error_msg)
        return None

    def _schema_error_result(
        self,
        tool_call: ToolCall,
        error_msg: str,
    ) -> ToolResult:
        """Build an error result for an invalid tool schema."""
        logger.error(
            TOOL_INVOKE_SCHEMA_ERROR,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            error=error_msg,
        )
        return ToolResult(
            tool_call_id=tool_call.id,
            content=(
                f"Tool {tool_call.name!r} has an invalid parameter schema: {error_msg}"
            ),
            is_error=True,
        )

    def _param_error_result(
        self,
        tool_call: ToolCall,
        error_msg: str,
    ) -> ToolResult:
        """Build an error result for failed parameter validation."""
        logger.warning(
            TOOL_INVOKE_PARAMETER_ERROR,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            error=error_msg,
        )
        param_err = ToolParameterError(
            error_msg,
            context={"tool": tool_call.name},
        )
        return ToolResult(
            tool_call_id=tool_call.id,
            content=str(param_err),
            is_error=True,
        )

    def _unexpected_validation_result(
        self,
        tool_call: ToolCall,
        error_msg: str,
    ) -> ToolResult:
        """Build an error result for unexpected validation failures."""
        logger.exception(
            TOOL_INVOKE_VALIDATION_UNEXPECTED,
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            error=error_msg,
        )
        return ToolResult(
            tool_call_id=tool_call.id,
            content=(
                f"Tool {tool_call.name!r} parameter validation failed: {error_msg}"
            ),
            is_error=True,
        )

    def _safe_deepcopy_args(
        self,
        tool_call: ToolCall,
    ) -> dict[str, object] | ToolResult:
        """Deep-copy tool call arguments for isolation.

        Returns the copied dict on success, or a ``ToolResult`` on
        failure.  Non-recoverable errors propagate after logging.
        """
        try:
            return copy.deepcopy(tool_call.arguments)
        except (MemoryError, RecursionError) as exc:
            logger.exception(
                TOOL_INVOKE_NON_RECOVERABLE,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        except Exception as exc:
            error_msg = str(exc) or f"{type(exc).__name__} (no message)"
            logger.exception(
                TOOL_INVOKE_DEEPCOPY_ERROR,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error=f"Failed to deep-copy arguments: {error_msg}",
            )
            return ToolResult(
                tool_call_id=tool_call.id,
                content=(
                    f"Tool {tool_call.name!r} arguments could not be "
                    f"safely copied: {error_msg}"
                ),
                is_error=True,
            )

    async def _execute_tool(
        self,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> ToolExecutionResult | ToolResult:
        """Deep-copy arguments for isolation, then execute the tool."""
        safe_args = self._safe_deepcopy_args(tool_call)
        if isinstance(safe_args, ToolResult):
            return safe_args
        try:
            return await tool.execute(arguments=safe_args)
        except (MemoryError, RecursionError) as exc:
            logger.exception(
                TOOL_INVOKE_NON_RECOVERABLE,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        except Exception as exc:
            error_msg = str(exc) or f"{type(exc).__name__} (no message)"
            logger.exception(
                TOOL_INVOKE_EXECUTION_ERROR,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error=error_msg,
            )
            exec_err = ToolExecutionError(
                error_msg,
                context={"tool": tool_call.name},
            )
            return ToolResult(
                tool_call_id=tool_call.id,
                content=str(exec_err),
                is_error=True,
            )

    def _track_parking_metadata(
        self,
        result: ToolExecutionResult,
        tool: BaseTool,
        tool_call: ToolCall,
    ) -> ToolResult | None:
        """Detect ``requires_parking`` metadata and add to escalations.

        Tools like ``request_human_approval`` signal parking via
        ``ToolExecutionResult.metadata``.  Only tracks when both
        ``requires_parking=True`` and ``approval_id`` are present.

        Returns:
            ``None`` on success, or an error ``ToolResult`` if tracking
            fails -- ensures the agent does not silently bypass the
            approval gate.
        """
        if result.metadata.get("requires_parking") is not True:
            return None
        if not result.metadata.get("approval_id"):
            logger.error(
                TOOL_INVOKE_EXECUTION_ERROR,
                tool_call_id=tool_call.id,
                tool_name=tool.name,
                note="requires_parking=True but approval_id missing",
            )
            return ToolResult(
                tool_call_id=tool_call.id,
                content=(
                    "Tool signalled requires_parking=True but did not "
                    "provide an approval_id -- cannot track escalation"
                ),
                is_error=True,
            )
        try:
            from synthorg.engine.approval_gate_models import (  # noqa: PLC0415
                EscalationInfo as _EscalationInfo,
            )

            self._pending_escalations.append(
                _EscalationInfo(
                    approval_id=str(result.metadata["approval_id"]),
                    tool_call_id=tool_call.id,
                    tool_name=tool.name,
                    action_type=str(
                        result.metadata.get("action_type", tool.action_type),
                    ),
                    risk_level=ApprovalRiskLevel(
                        result.metadata.get("risk_level", "high"),
                    ),
                    reason="Agent requested human approval",
                ),
            )
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.exception(
                TOOL_INVOKE_EXECUTION_ERROR,
                tool_call_id=tool_call.id,
                tool_name=tool.name,
                note="Failed to track parking metadata",
            )
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Approval escalation tracking failed: {exc}",
                is_error=True,
            )
        return None

    def _build_result(
        self,
        tool_call: ToolCall,
        result: ToolExecutionResult,
    ) -> ToolResult:
        """Map a successful execution result to a ``ToolResult``."""
        if result.is_error:
            logger.warning(
                TOOL_INVOKE_TOOL_ERROR,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                content=result.content,
            )
        else:
            logger.info(
                TOOL_INVOKE_SUCCESS,
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
            )
        return ToolResult(
            tool_call_id=tool_call.id,
            content=result.content,
            is_error=result.is_error,
        )

    def _apply_html_guard(
        self,
        result: ToolExecutionResult,
    ) -> ToolExecutionResult:
        """Apply HTML parse guard to sanitize tool output.

        Strips scripts, styles, hidden elements, and detects
        render-gap injection attacks.  Returns the original result
        unchanged if the output is not HTML or on parse errors.
        """
        if result.is_error or not result.content:
            return result

        if self._html_guard is None:
            from synthorg.tools.html_parse_guard import (  # noqa: PLC0415
                HTMLParseGuard,
            )

            self._html_guard = HTMLParseGuard()

        sanitized = self._html_guard.sanitize(result.content)
        if sanitized.cleaned == result.content:
            return result
        metadata = dict(result.metadata)
        metadata["html_guard"] = {
            "gap_detected": sanitized.gap_detected,
            "gap_ratio": sanitized.gap_ratio,
            "stripped_element_count": sanitized.stripped_element_count,
        }
        return ToolExecutionResult(
            content=sanitized.cleaned,
            is_error=result.is_error,
            metadata=metadata,
        )

    async def _run_guarded(
        self,
        index: int,
        tool_call: ToolCall,
        results: dict[int, ToolResult],
        fatal_errors: list[Exception],
        semaphore: asyncio.Semaphore | None,
    ) -> None:
        """Execute a single tool call, storing fatal errors instead of raising.

        This wrapper ensures that ``MemoryError`` / ``RecursionError`` do not
        cancel sibling tasks inside a ``TaskGroup``.  ``BaseException``
        subclasses (``KeyboardInterrupt``, ``CancelledError``) are not
        intercepted and will cancel the group normally.
        """
        try:
            ctx = semaphore if semaphore is not None else nullcontext()
            async with ctx:
                results[index] = await self._invoke_single(tool_call)
        except (MemoryError, RecursionError) as exc:
            fatal_errors.append(exc)

    @staticmethod
    def _raise_fatal_errors(fatal_errors: list[Exception]) -> None:
        """Re-raise collected fatal errors after all tasks complete."""
        if not fatal_errors:
            return
        if len(fatal_errors) == 1:
            raise fatal_errors[0]
        msg = "multiple non-recoverable tool errors"
        raise ExceptionGroup(msg, fatal_errors)

    async def invoke_all(
        self,
        tool_calls: Iterable[ToolCall],
        *,
        max_concurrency: int | None = None,
    ) -> tuple[ToolResult, ...]:
        """Execute multiple tool calls concurrently.

        Args:
            tool_calls: Tool calls to execute.
            max_concurrency: Max concurrent invocations (``>= 1``).

        Returns:
            Tuple of results in the same order as the input.

        Raises:
            ValueError: If *max_concurrency* < 1.
            MemoryError: Re-raised if a single fatal error occurred.
            RecursionError: Re-raised if a single fatal error occurred.
            ExceptionGroup: If multiple fatal errors occurred.
        """
        self._pending_escalations.clear()

        if max_concurrency is not None and max_concurrency < 1:
            msg = f"max_concurrency must be >= 1, got {max_concurrency}"
            raise ValueError(msg)

        calls = list(tool_calls)
        if not calls:
            return ()

        logger.info(
            TOOL_INVOKE_ALL_START,
            count=len(calls),
            max_concurrency=max_concurrency,
        )

        results: dict[int, ToolResult] = {}
        fatal_errors: list[Exception] = []
        semaphore = (
            asyncio.Semaphore(max_concurrency) if max_concurrency is not None else None
        )

        async with asyncio.TaskGroup() as tg:
            for idx, call in enumerate(calls):
                tg.create_task(
                    self._run_guarded(
                        idx,
                        call,
                        results,
                        fatal_errors,
                        semaphore,
                    ),
                )

        logger.info(
            TOOL_INVOKE_ALL_COMPLETE,
            count=len(calls),
            fatal_count=len(fatal_errors),
        )

        self._raise_fatal_errors(fatal_errors)

        # Sort escalations by tool-call index for deterministic ordering.
        if len(self._pending_escalations) > 1:
            call_id_order = {tc.id: idx for idx, tc in enumerate(calls)}
            self._pending_escalations.sort(
                key=lambda e: call_id_order.get(e.tool_call_id, len(calls)),
            )

        return tuple(results[i] for i in range(len(calls)))
