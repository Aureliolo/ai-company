"""Tool-based memory injection strategy.

Provides ``search_memory`` and ``recall_memory`` tool definitions
that agents invoke on-demand during execution.  Implements the
``MemoryInjectionStrategy`` protocol with tool-based retrieval.
"""

import builtins
import copy
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from synthorg.core.enums import MemoryCategory
from synthorg.core.types import NotBlankStr
from synthorg.memory.errors import MemoryError as DomainMemoryError
from synthorg.memory.models import MemoryEntry, MemoryQuery
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_REFORMULATION_EXHAUSTED,
    MEMORY_REFORMULATION_FAILED,
    MEMORY_REFORMULATION_ROUND,
    MEMORY_REFORMULATION_SUFFICIENT,
    MEMORY_RETRIEVAL_COMPLETE,
    MEMORY_RETRIEVAL_DEGRADED,
    MEMORY_RETRIEVAL_START,
    MEMORY_SUFFICIENCY_CHECK_FAILED,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage, ToolDefinition

if TYPE_CHECKING:
    from synthorg.memory.protocol import MemoryBackend
    from synthorg.memory.reformulation import (
        QueryReformulator,
        SufficiencyChecker,
    )
    from synthorg.memory.retrieval_config import MemoryRetrievalConfig

logger = get_logger(__name__)

SEARCH_MEMORY_TOOL_NAME = "search_memory"
RECALL_MEMORY_TOOL_NAME = "recall_memory"

# Error message constants.  ``memory/tools.py`` performs PREFIX matching
# on these exact strings to detect user-facing tool errors.  All error
# messages start with ``ERROR_PREFIX`` so the matcher can check via
# ``startswith(ERROR_PREFIX)`` rather than substring matching.  Do not
# rename, reorder, or drop the prefix without updating the matcher.
ERROR_PREFIX = "Error:"
SEARCH_UNAVAILABLE = f"{ERROR_PREFIX} Memory search is temporarily unavailable."
SEARCH_UNEXPECTED = f"{ERROR_PREFIX} Memory search encountered an unexpected error."
RECALL_UNAVAILABLE = f"{ERROR_PREFIX} Memory recall is temporarily unavailable."
RECALL_UNEXPECTED = f"{ERROR_PREFIX} Memory recall encountered an unexpected error."
RECALL_NOT_FOUND_PREFIX = f"{ERROR_PREFIX} Memory not found:"

_INSTRUCTION = (
    "You have access to memory recall tools. Use search_memory "
    "when you need to recall past context, decisions, or learned "
    "information. Use recall_memory to fetch a specific memory by ID."
)

SEARCH_MEMORY_SCHEMA: Final[MappingProxyType[str, Any]] = MappingProxyType(
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query.",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional category filter "
                    "(working, episodic, semantic, procedural, social)."
                ),
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default 10).",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["query"],
    }
)

_MAX_MEMORY_ID_LEN: Final[int] = 256

RECALL_MEMORY_SCHEMA: Final[MappingProxyType[str, Any]] = MappingProxyType(
    {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "Exact memory ID to recall.",
                "maxLength": _MAX_MEMORY_ID_LEN,
            },
        },
        "required": ["memory_id"],
    }
)


def _format_entries(entries: tuple[MemoryEntry, ...]) -> str:
    """Format memory entries as human-readable text."""
    if not entries:
        return "No memories found."
    parts: list[str] = []
    for entry in entries:
        score = (
            f" (relevance: {entry.relevance_score:.2f})"
            if entry.relevance_score is not None
            else ""
        )
        parts.append(f"[{entry.category.value}]{score} {entry.content}")
    return "\n".join(parts)


def _parse_categories(
    raw: Any,
    *,
    agent_id: str | None = None,
) -> tuple[frozenset[MemoryCategory] | None, tuple[str, ...]]:
    """Parse category filter from LLM arguments.

    Invalid category values are logged at WARNING (so operators can
    see the agent's hallucinated categories) and returned in the
    rejected tuple so callers can surface them back to the LLM for
    self-correction.

    Malformed shapes (e.g. a bare string like ``"episodic"`` instead
    of ``["episodic"]``) are treated the same way: the raw value is
    returned in ``rejected_values`` and parsed_categories is ``None``
    so the search does NOT silently broaden to all categories.

    Args:
        raw: Raw value from tool arguments (expected list[str]).
        agent_id: Optional agent identifier for log context.

    Returns:
        Tuple of ``(parsed_categories, rejected_values)``.
        ``parsed_categories`` is ``None`` when input is absent.  When
        the input is present but malformed, ``rejected_values`` carries
        the raw value so callers can surface it.
    """
    if raw is None:
        return None, ()
    if not isinstance(raw, list):
        malformed = str(raw)
        logger.warning(
            MEMORY_RETRIEVAL_DEGRADED,
            source="category_parse",
            agent_id=agent_id,
            invalid_category=malformed,
            reason="categories must be a list, surfaced for self-correction",
        )
        return None, (malformed,)
    if not raw:
        return None, ()
    categories: list[MemoryCategory] = []
    rejected: list[str] = []
    for val in raw:
        try:
            categories.append(MemoryCategory(val))
        except ValueError:
            rejected_value = str(val)
            rejected.append(rejected_value)
            logger.warning(
                MEMORY_RETRIEVAL_DEGRADED,
                source="category_parse",
                agent_id=agent_id,
                invalid_category=rejected_value,
                reason="unknown category value, surfaced for self-correction",
            )
    parsed = frozenset(categories) if categories else None
    return parsed, tuple(rejected)


def _merge_results(
    existing: tuple[MemoryEntry, ...],
    new: tuple[MemoryEntry, ...],
) -> tuple[MemoryEntry, ...]:
    """Merge two entry tuples by ID and re-sort by relevance.

    De-duplicates by ``entry.id``, keeping the higher ``relevance_score``
    copy when the same id appears in both inputs (``None`` treated as
    ``0.0``).  The returned tuple is sorted by relevance descending so
    that later reformulation rounds can actually surface better matches
    even when the first round already hit the tool's ``limit`` -- if we
    preserved first-round order, later unseen results would always land
    past the final truncation and Search-and-Ask would have no effect.
    Ties are broken by first-seen order for determinism.

    Args:
        existing: Current entries.
        new: New entries to merge in.

    Returns:
        Merged tuple sorted by relevance (highest first).
    """

    def _rel(entry: MemoryEntry) -> float:
        return entry.relevance_score if entry.relevance_score is not None else 0.0

    merged: dict[str, MemoryEntry] = {}
    first_seen: dict[str, int] = {}
    for idx, entry in enumerate(existing):
        merged[entry.id] = entry
        first_seen.setdefault(entry.id, idx)

    offset = len(existing)
    for idx, entry in enumerate(new):
        if entry.id in merged:
            if _rel(entry) > _rel(merged[entry.id]):
                merged[entry.id] = entry
            continue
        merged[entry.id] = entry
        first_seen[entry.id] = offset + idx

    return tuple(
        sorted(
            merged.values(),
            key=lambda e: (-_rel(e), first_seen[e.id]),
        )
    )


def _truncate_entries(
    entries: tuple[MemoryEntry, ...],
    limit: int,
) -> tuple[MemoryEntry, ...]:
    """Truncate a cumulative result list to the caller-requested limit.

    The Search-and-Ask loop can accumulate more than ``limit`` entries
    when later rounds add unseen results; the tool contract promises
    ``limit`` entries, so truncate on return regardless of how many
    rounds ran.
    """
    if limit < 1 or len(entries) <= limit:
        return entries
    return entries[:limit]


def _parse_search_args(
    arguments: dict[str, Any],
    config_max_memories: int,
    *,
    agent_id: str | None = None,
) -> tuple[str | None, int, frozenset[MemoryCategory] | None, tuple[str, ...]]:
    """Extract and validate search_memory arguments.

    Args:
        arguments: Raw tool arguments from LLM.
        config_max_memories: System-configured max memories limit.
        agent_id: Optional agent identifier for log context.

    Returns:
        Tuple of ``(query_text, limit, categories, rejected_categories)``.
        ``query_text`` is ``None`` when the query is empty or
        whitespace-only.  ``rejected_categories`` contains raw values
        that failed to parse as ``MemoryCategory`` so the caller can
        surface them back to the LLM for self-correction.
    """
    query_raw = arguments.get("query", "")
    # Reject non-string query shapes up-front so downstream code
    # (``_handle_search`` -> ``len(query_text)``) does not crash on
    # LLM-hallucinated inputs like ``{"query": 123}`` or
    # ``{"query": ["a", "b"]}``.
    if not isinstance(query_raw, str):
        return None, 0, None, ()
    query_text = query_raw.strip()
    if not query_text:
        return None, 0, None, ()

    limit_raw = arguments.get("limit", 10)
    if isinstance(limit_raw, bool) or not isinstance(limit_raw, int | float):
        limit = 10
    else:
        limit = int(limit_raw)
    # Clamp to [1, min(50, config.max_memories)]
    effective_max = min(50, config_max_memories)
    limit = min(max(limit, 1), effective_max)

    categories, rejected = _parse_categories(
        arguments.get("categories"),
        agent_id=agent_id,
    )
    return query_text, limit, categories, rejected


class ToolBasedInjectionStrategy:
    """Tool-based memory injection -- on-demand retrieval via agent tools.

    Implements ``MemoryInjectionStrategy`` protocol.  Instead of
    pre-loading memories, exposes ``search_memory`` and
    ``recall_memory`` tools for the agent to invoke during execution.

    When ``config.query_reformulation_enabled`` is True and both
    ``reformulator`` and ``sufficiency_checker`` are provided, the
    ``search_memory`` handler runs an iterative Search-and-Ask loop:
    retrieve -> check sufficiency -> reformulate query -> re-retrieve,
    up to ``config.max_reformulation_rounds`` rounds.

    Note: Tool-based strategies expose additional methods
    (``handle_tool_call``, ``get_tool_definitions``) beyond the
    base ``MemoryInjectionStrategy`` protocol.  Callers needing
    tool dispatch should type-narrow or check strategy type.

    Args:
        backend: Memory backend for personal memories.
        config: Retrieval pipeline configuration.
        shared_store: Optional shared knowledge store.
        token_estimator: Ignored -- accepted for constructor parity
            with ``ContextInjectionStrategy`` so both strategies can
            be constructed with the same kwargs.  Tool-based retrieval
            has no token estimation step.
        memory_filter: Ignored -- accepted for constructor parity
            with ``ContextInjectionStrategy``.  Callers needing
            tag-based filtering on tool-based retrieval should wrap
            the backend instead.  Use ``ContextInjectionStrategy``
            when post-ranking filtering is required.
        reformulator: ``QueryReformulator`` that produces a new query
            string given the current query and retrieved entries.
            REQUIRED alongside ``sufficiency_checker`` whenever
            ``config.query_reformulation_enabled`` is True -- the
            constructor raises ``ValueError`` if the flag is set but
            either collaborator is missing (fail-fast at wiring time
            rather than silent no-op at retrieval time).  May be
            ``None`` only when reformulation is disabled.
        sufficiency_checker: ``SufficiencyChecker`` that decides
            whether retrieved entries answer the current query.
            Pairs with ``reformulator`` for Search-and-Ask; subject
            to the same constructor guard.

    Raises:
        ValueError: If ``config.query_reformulation_enabled`` is True
            but either ``reformulator`` or ``sufficiency_checker`` is
            missing.
    """

    __slots__ = (
        "_backend",
        "_config",
        "_reformulator",
        "_shared_store",
        "_sufficiency_checker",
    )

    def __init__(  # noqa: PLR0913
        self,
        *,
        backend: MemoryBackend,
        config: MemoryRetrievalConfig,
        shared_store: Any | None = None,
        token_estimator: Any | None = None,  # noqa: ARG002
        memory_filter: Any | None = None,  # noqa: ARG002
        reformulator: QueryReformulator | None = None,
        sufficiency_checker: SufficiencyChecker | None = None,
    ) -> None:
        if config.query_reformulation_enabled and (
            reformulator is None or sufficiency_checker is None
        ):
            msg = (
                "config.query_reformulation_enabled is True but "
                "reformulator and sufficiency_checker must both be "
                "provided to ToolBasedInjectionStrategy; got "
                f"reformulator={reformulator!r}, "
                f"sufficiency_checker={sufficiency_checker!r}"
            )
            raise ValueError(msg)
        self._backend = backend
        self._config = config
        self._shared_store = shared_store
        self._reformulator = reformulator
        self._sufficiency_checker = sufficiency_checker

    async def prepare_messages(
        self,
        agent_id: NotBlankStr,  # noqa: ARG002
        query_text: NotBlankStr,  # noqa: ARG002
        token_budget: int,
    ) -> tuple[ChatMessage, ...]:
        """Return a brief instruction message about available tools.

        Tool-based strategies inject minimal context up front --
        the agent retrieves memories on-demand via tool calls.

        Args:
            agent_id: The agent requesting memories.
            query_text: Text for semantic retrieval (unused).
            token_budget: Maximum tokens for memory content.

        Returns:
            Single instruction message, or empty if budget is zero.
        """
        if token_budget <= 0:
            return ()
        return (
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=_INSTRUCTION,
            ),
        )

    def get_tool_definitions(self) -> tuple[ToolDefinition, ...]:
        """Return search_memory and recall_memory tool definitions.

        Returns:
            Two tool definitions with JSON Schema parameters.
        """
        # ToolDefinition.parameters_schema expects a plain ``dict``,
        # not ``MappingProxyType``.  dict() unwraps the proxy so each
        # ToolDefinition gets an independent mutable copy -- callers
        # that mutate the schema in-place won't affect the module-level
        # template or other tool definitions built from it.
        return (
            ToolDefinition(
                name=NotBlankStr(SEARCH_MEMORY_TOOL_NAME),
                description=(
                    "Search agent memory for relevant past context, "
                    "decisions, or learned information."
                ),
                parameters_schema=copy.deepcopy(dict(SEARCH_MEMORY_SCHEMA)),
            ),
            ToolDefinition(
                name=NotBlankStr(RECALL_MEMORY_TOOL_NAME),
                description="Recall a specific memory entry by its ID.",
                parameters_schema=copy.deepcopy(dict(RECALL_MEMORY_SCHEMA)),
            ),
        )

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        agent_id: str,
    ) -> str:
        """Dispatch a tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool being called.
            arguments: Tool arguments from the LLM.
            agent_id: Agent making the call.

        Returns:
            Formatted text result.

        Raises:
            ValueError: If ``tool_name`` is not recognized.
        """
        if tool_name == SEARCH_MEMORY_TOOL_NAME:
            return await self._handle_search(arguments, agent_id)
        if tool_name == RECALL_MEMORY_TOOL_NAME:
            return await self._handle_recall(arguments, agent_id)
        msg = f"Unknown tool: {tool_name!r}"
        logger.warning(
            MEMORY_RETRIEVAL_DEGRADED,
            source="handle_tool_call",
            agent_id=agent_id,
            tool_name=tool_name,
            error=msg,
        )
        raise ValueError(msg)

    async def _handle_search(
        self,
        arguments: dict[str, Any],
        agent_id: str,
    ) -> str:
        """Handle a search_memory tool call."""
        query_text, limit, categories, rejected_categories = _parse_search_args(
            arguments,
            self._config.max_memories,
            agent_id=agent_id,
        )
        if query_text is None:
            return f"{ERROR_PREFIX} query must be a non-empty string."
        logger.info(
            MEMORY_RETRIEVAL_START,
            agent_id=agent_id,
            tool=SEARCH_MEMORY_TOOL_NAME,
            query_length=len(query_text),
        )
        entries_or_error = await self._safe_search(
            query_text=query_text,
            limit=limit,
            categories=categories,
            agent_id=agent_id,
        )
        if isinstance(entries_or_error, str):
            return entries_or_error
        logger.info(
            MEMORY_RETRIEVAL_COMPLETE,
            agent_id=agent_id,
            tool=SEARCH_MEMORY_TOOL_NAME,
            ranked_count=len(entries_or_error),
        )
        formatted = _format_entries(entries_or_error)
        if rejected_categories:
            formatted += (
                f"\n\n(Ignored invalid categories: {', '.join(rejected_categories)})"
            )
        return formatted

    async def _safe_search(
        self,
        *,
        query_text: str,
        limit: int,
        categories: frozenset[MemoryCategory] | None,
        agent_id: str,
    ) -> tuple[MemoryEntry, ...] | str:
        """Run the search with error isolation.

        Returns the entries on success, or a user-facing error string
        on ``DomainMemoryError`` / unexpected ``Exception``.  System
        errors (``MemoryError``, ``RecursionError``) propagate.
        """
        try:
            return await self._retrieve_with_reformulation(
                query_text=query_text,
                limit=limit,
                categories=categories,
                agent_id=agent_id,
            )
        except builtins.MemoryError, RecursionError:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source=SEARCH_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                query_length=len(query_text),
                limit=limit,
                error_type="system",
                reason="system_error_in_search",
                exc_info=True,
            )
            raise
        except DomainMemoryError as exc:
            logger.warning(
                MEMORY_RETRIEVAL_DEGRADED,
                source=SEARCH_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return SEARCH_UNAVAILABLE
        except Exception as exc:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source=SEARCH_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return SEARCH_UNEXPECTED

    async def _retrieve_with_reformulation(
        self,
        *,
        query_text: str,
        limit: int,
        categories: frozenset[MemoryCategory] | None,
        agent_id: str,
    ) -> tuple[MemoryEntry, ...]:
        """Retrieve memories, optionally with iterative reformulation.

        When ``query_reformulation_enabled`` is True and both the
        reformulator and sufficiency checker are configured, performs
        up to ``max_reformulation_rounds`` rounds of
        ``search -> check sufficiency -> reformulate query``.

        Returns the cumulative merged results across all rounds.
        Duplicates (by entry ID) are deduplicated across rounds,
        keeping the higher-relevance-score version; ``None`` relevance
        is treated as ``0.0``.
        """
        reformulator = self._reformulator
        sufficiency_checker = self._sufficiency_checker
        if (
            not self._config.query_reformulation_enabled
            or reformulator is None
            or sufficiency_checker is None
        ):
            query = MemoryQuery(
                text=query_text,
                limit=limit,
                categories=categories,
            )
            return await self._backend.retrieve(NotBlankStr(agent_id), query)

        return await self._reformulation_loop(
            reformulator=reformulator,
            sufficiency_checker=sufficiency_checker,
            query_text=query_text,
            limit=limit,
            categories=categories,
            agent_id=agent_id,
        )

    async def _reformulation_loop(  # noqa: PLR0913
        self,
        *,
        reformulator: QueryReformulator,
        sufficiency_checker: SufficiencyChecker,
        query_text: str,
        limit: int,
        categories: frozenset[MemoryCategory] | None,
        agent_id: str,
    ) -> tuple[MemoryEntry, ...]:
        """Run the iterative Search-and-Ask reformulation loop.

        Starts with the initial query, retrieves, checks sufficiency,
        reformulates if insufficient, and re-retrieves -- up to
        ``config.max_reformulation_rounds`` rounds.  Results across
        rounds are merged by ID, keeping the higher-relevance version
        of any duplicate and truncating to ``limit`` on return so the
        tool contract is honoured regardless of how many rounds ran.

        Reformulator, sufficiency checker, and mid-loop backend
        retrieve calls are all wrapped in error isolation: if any
        raises a non-system exception, the round helper returns
        ``None`` and the loop returns the current cumulative entries
        rather than propagating.  System errors
        (builtins.MemoryError, RecursionError) still propagate.
        """
        max_rounds = self._config.max_reformulation_rounds
        current_query = query_text
        try:
            entries = await self._backend.retrieve(
                NotBlankStr(agent_id),
                MemoryQuery(text=current_query, limit=limit, categories=categories),
            )
        except builtins.MemoryError, RecursionError:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                agent_id=agent_id,
                round=0,
                query_length=len(current_query),
                limit=limit,
                error_type="system",
                reason="system_error_in_initial_retrieve",
                exc_info=True,
            )
            raise
        for round_idx in range(max_rounds):
            step = await self._run_reformulation_step(
                reformulator=reformulator,
                sufficiency_checker=sufficiency_checker,
                current_query=current_query,
                entries=entries,
                limit=limit,
                categories=categories,
                agent_id=agent_id,
                round_idx=round_idx,
            )
            if step is None:
                return _truncate_entries(entries, limit)
            entries, current_query = step
        logger.info(
            MEMORY_REFORMULATION_EXHAUSTED,
            agent_id=agent_id,
            rounds_exhausted=max_rounds,
            result_count=len(entries),
            reason="max_rounds_reached",
        )
        return _truncate_entries(entries, limit)

    async def _run_reformulation_step(  # noqa: PLR0913
        self,
        *,
        reformulator: QueryReformulator,
        sufficiency_checker: SufficiencyChecker,
        current_query: str,
        entries: tuple[MemoryEntry, ...],
        limit: int,
        categories: frozenset[MemoryCategory] | None,
        agent_id: str,
        round_idx: int,
    ) -> tuple[tuple[MemoryEntry, ...], str] | None:
        """Execute one round of the Search-and-Ask loop.

        Returns ``(new_entries, new_query)`` when the loop should
        continue, or ``None`` when it should terminate with the
        current ``entries`` (sufficiency met, reformulator exhausted,
        or non-system error in any sub-step).
        """
        sufficient = await self._check_sufficiency(
            sufficiency_checker,
            current_query,
            entries,
            agent_id=agent_id,
            round_idx=round_idx,
        )
        if sufficient is None:
            return None
        if sufficient:
            logger.info(
                MEMORY_REFORMULATION_SUFFICIENT,
                agent_id=agent_id,
                round=round_idx,
                result_count=len(entries),
            )
            return None
        new_query = await self._reformulate(
            reformulator,
            current_query,
            entries,
            agent_id=agent_id,
            round_idx=round_idx,
        )
        if new_query is None or new_query == current_query:
            logger.info(
                MEMORY_REFORMULATION_EXHAUSTED,
                agent_id=agent_id,
                round=round_idx + 1,
                result_count=len(entries),
                reason=(
                    "reformulator_stable"
                    if new_query == current_query
                    else "reformulator_gave_up"
                ),
            )
            return None
        logger.info(
            MEMORY_REFORMULATION_ROUND,
            agent_id=agent_id,
            round=round_idx + 1,
            original_length=len(current_query),
            new_length=len(new_query),
        )
        new_entries = await self._retrieve_round(
            agent_id=agent_id,
            query=new_query,
            limit=limit,
            categories=categories,
            round_idx=round_idx,
        )
        if new_entries is None:
            return None
        return _merge_results(entries, new_entries), new_query

    @staticmethod
    async def _check_sufficiency(
        sufficiency_checker: SufficiencyChecker,
        query: str,
        entries: tuple[MemoryEntry, ...],
        *,
        agent_id: str,
        round_idx: int,
    ) -> bool | None:
        """Run the sufficiency checker with error isolation.

        Returns ``True``/``False`` on success, or ``None`` when the
        check raised a non-system exception (caller should exit the
        loop and return current cumulative entries).
        """
        try:
            return await sufficiency_checker.check_sufficiency(query, entries)
        except builtins.MemoryError, RecursionError:
            logger.error(
                MEMORY_SUFFICIENCY_CHECK_FAILED,
                agent_id=agent_id,
                round=round_idx,
                error_type="system",
                reason="system_error_in_sufficiency_check",
                exc_info=True,
            )
            raise
        except Exception as exc:
            logger.warning(
                MEMORY_SUFFICIENCY_CHECK_FAILED,
                agent_id=agent_id,
                round=round_idx,
                error=str(exc),
                error_type=type(exc).__qualname__,
                exc_info=True,
            )
            return None

    @staticmethod
    async def _reformulate(
        reformulator: QueryReformulator,
        current_query: str,
        entries: tuple[MemoryEntry, ...],
        *,
        agent_id: str,
        round_idx: int,
    ) -> str | None:
        """Run the reformulator with error isolation.

        Returns the new query string, ``None`` when the reformulator
        gave up, or ``None`` when it raised a non-system exception
        (caller cannot distinguish these two cases -- both terminate
        the loop).
        """
        try:
            return await reformulator.reformulate(current_query, entries)
        except builtins.MemoryError, RecursionError:
            logger.error(
                MEMORY_REFORMULATION_FAILED,
                agent_id=agent_id,
                round=round_idx,
                error_type="system",
                reason="system_error_in_reformulate",
                exc_info=True,
            )
            raise
        except Exception as exc:
            logger.warning(
                MEMORY_REFORMULATION_FAILED,
                agent_id=agent_id,
                round=round_idx,
                error=str(exc),
                error_type=type(exc).__qualname__,
                exc_info=True,
            )
            return None

    async def _retrieve_round(
        self,
        *,
        agent_id: str,
        query: str,
        limit: int,
        categories: frozenset[MemoryCategory] | None,
        round_idx: int,
    ) -> tuple[MemoryEntry, ...] | None:
        """Retrieve for a reformulated round with error isolation.

        Returns the new entries, or ``None`` on non-system failure so
        the loop can degrade gracefully to the accumulated results.
        """
        try:
            return await self._backend.retrieve(
                NotBlankStr(agent_id),
                MemoryQuery(text=query, limit=limit, categories=categories),
            )
        except builtins.MemoryError, RecursionError:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                agent_id=agent_id,
                round=round_idx + 1,
                query_length=len(query),
                limit=limit,
                error_type="system",
                reason="system_error_in_retrieve_round",
                exc_info=True,
            )
            raise
        except DomainMemoryError as exc:
            logger.warning(
                MEMORY_RETRIEVAL_DEGRADED,
                agent_id=agent_id,
                round=round_idx + 1,
                reason="retrieve_failed_mid_loop",
                error=str(exc),
                error_type=type(exc).__qualname__,
            )
            return None
        except Exception as exc:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                agent_id=agent_id,
                round=round_idx + 1,
                reason="unexpected_retrieve_failure_mid_loop",
                error=str(exc),
                error_type=type(exc).__qualname__,
                exc_info=True,
            )
            return None

    async def _handle_recall(  # noqa: PLR0911
        self,
        arguments: dict[str, Any],
        agent_id: str,
    ) -> str:
        """Handle a recall_memory tool call."""
        memory_id_raw = arguments.get("memory_id", "")
        # Reject non-string shapes up-front rather than calling
        # ``str(...)`` on arbitrary objects -- an LLM-hallucinated
        # ``{"memory_id": 42}`` should fail validation cleanly rather
        # than letting downstream code process a stringified integer.
        if not isinstance(memory_id_raw, str):
            return f"{ERROR_PREFIX} memory_id is required."
        memory_id = memory_id_raw.strip()
        if not memory_id:
            return f"{ERROR_PREFIX} memory_id is required."
        if len(memory_id) > _MAX_MEMORY_ID_LEN:
            return f"{ERROR_PREFIX} memory_id exceeds maximum allowed length."

        logger.info(
            MEMORY_RETRIEVAL_START,
            agent_id=agent_id,
            tool=RECALL_MEMORY_TOOL_NAME,
            memory_id=memory_id,
        )

        try:
            entry = await self._backend.get(
                NotBlankStr(agent_id),
                NotBlankStr(memory_id),
            )
        except builtins.MemoryError, RecursionError:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source=RECALL_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                memory_id=memory_id,
                error_type="system",
                reason="system_error_in_recall",
                exc_info=True,
            )
            raise
        except DomainMemoryError as exc:
            logger.warning(
                MEMORY_RETRIEVAL_DEGRADED,
                source=RECALL_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return RECALL_UNAVAILABLE
        except Exception as exc:
            logger.error(
                MEMORY_RETRIEVAL_DEGRADED,
                source=RECALL_MEMORY_TOOL_NAME,
                agent_id=agent_id,
                error=str(exc),
                exc_info=True,
            )
            return RECALL_UNEXPECTED

        logger.info(
            MEMORY_RETRIEVAL_COMPLETE,
            agent_id=agent_id,
            tool=RECALL_MEMORY_TOOL_NAME,
            found=entry is not None,
        )

        if entry is None:
            safe_id = memory_id[:64]
            return f"{RECALL_NOT_FOUND_PREFIX} {safe_id}"

        return _format_entries((entry,))

    @property
    def strategy_name(self) -> str:
        """Human-readable strategy identifier.

        Returns:
            ``"tool_based"``.
        """
        return "tool_based"
