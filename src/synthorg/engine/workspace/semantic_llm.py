"""LLM-based semantic conflict analyzer.

Uses an LLM provider to review merged code for semantic conflicts
that AST analysis cannot detect. Intended for use when conflict
escalation is REVIEW_AGENT and a provider is configured. The gating
logic resides in the workspace strategy layer.
"""

import asyncio
from typing import TYPE_CHECKING

from synthorg.engine.workspace.semantic_analyzer import filter_files
from synthorg.engine.workspace.semantic_llm_prompt import (
    build_review_message,
    build_semantic_review_tool,
    build_system_message,
    parse_tool_call_response,
)
from synthorg.observability import get_logger
from synthorg.observability.events.workspace import (
    WORKSPACE_SEMANTIC_ANALYSIS_COMPLETE,
    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
    WORKSPACE_SEMANTIC_ANALYSIS_START,
)
from synthorg.providers.models import (
    ChatMessage,
    CompletionConfig,
    ToolDefinition,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from synthorg.engine.workspace.config import SemanticAnalysisConfig
    from synthorg.engine.workspace.models import MergeConflict, Workspace
    from synthorg.providers.protocol import CompletionProvider

logger = get_logger(__name__)


class LlmSemanticAnalyzer:
    """LLM-based semantic conflict analyzer.

    Sends merged code diff to an LLM for semantic review. Parses
    the response via tool calls (preferred) or JSON content fallback.
    Retries on parse failure up to ``max_retries`` times.

    Args:
        provider: LLM completion provider.
        model: Model identifier for semantic review.
        config: Optional semantic analysis configuration.
    """

    __slots__ = ("_config", "_model", "_provider")

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model: str,
        config: SemanticAnalysisConfig | None = None,
    ) -> None:
        if not model or not model.strip():
            msg = "model must be a non-blank string"
            raise ValueError(msg)
        self._provider = provider
        self._model = model

        if config is None:
            from synthorg.engine.workspace.config import (  # noqa: PLC0415
                SemanticAnalysisConfig,
            )

            config = SemanticAnalysisConfig()
        self._config = config

    async def analyze(
        self,
        *,
        workspace: Workspace,
        changed_files: tuple[str, ...],
        repo_root: str,
        base_sources: Mapping[str, str],
    ) -> tuple[MergeConflict, ...]:
        """Analyze merged files using an LLM for semantic conflicts.

        Args:
            workspace: The workspace that was just merged.
            changed_files: Paths of files modified by the merge.
            repo_root: Absolute path to the repository root.
            base_sources: Mapping of file path to source content
                before the merge.

        Returns:
            Tuple of semantic MergeConflict instances from LLM review.
        """
        logger.info(
            WORKSPACE_SEMANTIC_ANALYSIS_START,
            workspace_id=workspace.workspace_id,
            analyzer="llm",
            file_count=len(changed_files),
        )

        result = await self._prepare_review_context(
            changed_files,
            repo_root,
            base_sources,
        )
        if result is None:
            return ()
        messages, tool_def, comp_config = result

        return await self._call_with_retry(
            workspace=workspace,
            messages=messages,
            tool_def=tool_def,
            comp_config=comp_config,
            max_retries=self._config.llm_max_retries,
        )

    async def _prepare_review_context(
        self,
        changed_files: tuple[str, ...],
        repo_root: str,
        base_sources: Mapping[str, str],
    ) -> tuple[list[ChatMessage], ToolDefinition, CompletionConfig] | None:
        """Filter files, read contents, and build LLM messages.

        Returns:
            Tuple of (messages, tool_def, comp_config) or ``None``
            when there is nothing to review.
        """
        from pathlib import Path  # noqa: PLC0415

        py_files = filter_files(changed_files, self._config)
        if not py_files:
            return None

        root = Path(repo_root)
        merged_contents = await asyncio.to_thread(
            _read_file_contents,
            root,
            py_files,
            self._config.max_file_bytes,
        )
        if not merged_contents:
            return None

        diff_summary = _build_diff_summary(
            merged_contents,
            base_sources,
        )
        messages = [
            build_system_message(),
            build_review_message(
                diff_summary=diff_summary,
                changed_files=merged_contents,
            ),
        ]
        tool_def = build_semantic_review_tool()
        comp_config = CompletionConfig(
            temperature=self._config.llm_temperature,
            max_tokens=self._config.llm_max_tokens,
        )
        return messages, tool_def, comp_config

    async def _call_with_retry(
        self,
        *,
        workspace: Workspace,
        messages: list[ChatMessage],
        tool_def: ToolDefinition,
        comp_config: CompletionConfig,
        max_retries: int = 2,
    ) -> tuple[MergeConflict, ...]:
        """Call LLM with retry on parse failure.

        Args:
            workspace: Workspace for logging context.
            messages: Chat messages to send.
            tool_def: Tool definition for structured output.
            comp_config: Completion configuration.
            max_retries: Maximum retry attempts on parse failure.

        Returns:
            Parsed conflicts, or empty tuple on exhaustion/error.
        """
        for attempt in range(1 + max_retries):
            try:
                response = await self._provider.complete(
                    messages,
                    self._model,
                    tools=[tool_def],
                    config=comp_config,
                )
                conflicts = parse_tool_call_response(response)
            except ValueError:
                if attempt < max_retries:
                    logger.debug(
                        WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                        workspace_id=workspace.workspace_id,
                        analyzer="llm",
                        attempt=attempt,
                        reason="parse_error",
                    )
                    continue
                logger.warning(
                    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                    workspace_id=workspace.workspace_id,
                    analyzer="llm",
                    reason="parse_exhausted",
                )
                return ()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning(
                    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                    workspace_id=workspace.workspace_id,
                    analyzer="llm",
                    reason="provider_error",
                    exc_info=True,
                )
                return ()
            else:
                logger.info(
                    WORKSPACE_SEMANTIC_ANALYSIS_COMPLETE,
                    workspace_id=workspace.workspace_id,
                    analyzer="llm",
                    conflicts=len(conflicts),
                    attempt=attempt,
                )
                return conflicts

        return ()  # pragma: no cover


def _read_file_contents(
    root: Path,
    files: list[str],
    max_file_bytes: int,
) -> dict[str, str]:
    """Read file contents, skipping unreadable files with logging.

    Unlike ``_read_sources`` in :mod:`semantic_analyzer`, this logs
    read errors at WARNING because LLM ingestion failures are
    operationally more significant, and enforces ``max_file_bytes``
    to avoid exceeding LLM token limits.
    """
    resolved_root = root.resolve()
    contents: dict[str, str] = {}
    for file_path in files:
        try:
            target = (root / file_path).resolve()
            if not target.is_relative_to(resolved_root):
                logger.warning(
                    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                    file=file_path,
                    reason="path_traversal",
                )
                continue
            stat = target.stat()
            if stat.st_size > max_file_bytes:
                logger.debug(
                    WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                    file=file_path,
                    reason="file_too_large",
                    size=stat.st_size,
                    limit=max_file_bytes,
                )
                continue
            contents[file_path] = target.read_text(
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning(
                WORKSPACE_SEMANTIC_ANALYSIS_FAILED,
                file=file_path,
                reason="read_error",
                error=f"{type(exc).__name__}: {exc}",
            )
    return contents


def _build_diff_summary(
    merged_contents: dict[str, str],
    base_sources: Mapping[str, str],
) -> str:
    """Build a change-type summary (NEW FILE / MODIFIED) for each file."""
    parts: list[str] = []
    for path, merged in merged_contents.items():
        base = base_sources.get(path)
        if base is None:
            parts.append(f"NEW FILE: {path}")
        elif base != merged:
            parts.append(f"MODIFIED: {path}")
    return "\n".join(parts) if parts else "No changes"
